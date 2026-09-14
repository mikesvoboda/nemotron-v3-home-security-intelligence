"""Unit tests for Frame Extractor Service (TDD Phase 3 - RED).

Tests for the FrameExtractor service that extracts frames from RTSP streams,
performs motion detection, and queues frames for detection pipeline.

These tests are written BEFORE implementation following TDD principles.
All tests should FAIL initially until the FrameExtractor is implemented.

Design:
- 1 FPS extraction for detection
- MOG2 background subtraction for motion detection
- Only saves frames on motion detection
- Saves to /tmp/claude/rtsp_frames/{camera_id}/{timestamp}.jpg
- Queues to detection_queue with DetectionQueuePayload format
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest


class TestFrameExtractorInit:
    """Tests for FrameExtractor initialization."""

    def test_init_accepts_redis_client(self) -> None:
        """FrameExtractor should initialize with redis_client parameter."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)

        assert extractor.redis_client is mock_redis

    def test_init_accepts_motion_sensitivity(self) -> None:
        """FrameExtractor should accept motion_sensitivity parameter (0.0-1.0)."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.7)

        assert extractor.motion_sensitivity == 0.7

    def test_init_default_motion_sensitivity(self) -> None:
        """FrameExtractor should have default motion_sensitivity of 0.5."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)

        assert extractor.motion_sensitivity == 0.5

    def test_init_creates_mog2_background_subtractor(self) -> None:
        """FrameExtractor should create MOG2 background subtractor on init."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        with patch("cv2.createBackgroundSubtractorMOG2") as mock_mog2:
            mock_subtractor = Mock()
            mock_mog2.return_value = mock_subtractor

            extractor = FrameExtractor(redis_client=mock_redis)

            mock_mog2.assert_called_once()
            assert extractor._bg_subtractor is mock_subtractor

    def test_init_validates_motion_sensitivity_range(self) -> None:
        """FrameExtractor should validate motion_sensitivity is between 0.0 and 1.0."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()

        # Test values outside valid range
        with pytest.raises(ValueError, match="motion_sensitivity must be between 0.0 and 1.0"):
            FrameExtractor(redis_client=mock_redis, motion_sensitivity=-0.1)

        with pytest.raises(ValueError, match="motion_sensitivity must be between 0.0 and 1.0"):
            FrameExtractor(redis_client=mock_redis, motion_sensitivity=1.1)

    def test_init_accepts_frame_save_dir(self) -> None:
        """FrameExtractor should accept custom frame_save_dir parameter."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        custom_dir = "/custom/frames"
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=custom_dir)

        assert extractor.frame_save_dir == Path(custom_dir)

    def test_init_default_frame_save_dir(self) -> None:
        """FrameExtractor should use /tmp/claude/rtsp_frames as default save directory."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)

        assert extractor.frame_save_dir == Path("/tmp/claude/rtsp_frames")  # noqa: S108


class TestFrameExtractorMotionDetection:
    """Tests for motion detection functionality."""

    def test_detect_motion_returns_bool(self) -> None:
        """detect_motion should return boolean indicating motion presence."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)

        # Create test frames (simple numpy arrays)
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255

        with patch.object(extractor._bg_subtractor, "apply") as mock_apply:
            # Mock significant motion
            mock_apply.return_value = np.ones((480, 640), dtype=np.uint8) * 255

            result = extractor.detect_motion(frame2, camera_id="camera1")

            assert isinstance(result, bool)

    def test_detect_motion_returns_true_for_significant_changes(self) -> None:
        """detect_motion should return True when significant motion is detected."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.5)

        # Simulate significant motion (50% of frame changed)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply") as mock_apply:
            # Create mask with 50% white pixels (motion detected)
            mask = np.zeros((480, 640), dtype=np.uint8)
            mask[:240, :] = 255  # Half the frame has motion
            mock_apply.return_value = mask

            result = extractor.detect_motion(frame, camera_id="camera1")

            assert result is True

    def test_detect_motion_returns_false_for_static_scenes(self) -> None:
        """detect_motion should return False when no motion is detected."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.5)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply") as mock_apply:
            # No motion - all black mask
            mock_apply.return_value = np.zeros((480, 640), dtype=np.uint8)

            result = extractor.detect_motion(frame, camera_id="camera1")

            assert result is False

    def test_detect_motion_sensitivity_low_filters_more(self) -> None:
        """Low sensitivity (0.0) should require more motion to return True."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.1)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply") as mock_apply:
            # Small amount of motion (5% of frame)
            mask = np.zeros((480, 640), dtype=np.uint8)
            mask[:24, :] = 255  # Only 5% of frame
            mock_apply.return_value = mask

            result = extractor.detect_motion(frame, camera_id="camera1")

            # With low sensitivity, small motion should be filtered out
            assert result is False

    def test_detect_motion_sensitivity_high_filters_less(self) -> None:
        """High sensitivity (1.0) should detect even small motion."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.9)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply") as mock_apply:
            # Very small amount of motion (1% of frame)
            mask = np.zeros((480, 640), dtype=np.uint8)
            mask[:5, :] = 255  # Only 1% of frame
            mock_apply.return_value = mask

            result = extractor.detect_motion(frame, camera_id="camera1")

            # With high sensitivity, even small motion should be detected
            assert result is True

    def test_detect_motion_uses_mog2_background_subtractor(self) -> None:
        """detect_motion should use MOG2 background subtractor."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply") as mock_apply:
            mock_apply.return_value = np.zeros((480, 640), dtype=np.uint8)

            extractor.detect_motion(frame, camera_id="camera1")

            # Verify MOG2 apply was called with the frame
            mock_apply.assert_called_once()
            np.testing.assert_array_equal(mock_apply.call_args[0][0], frame)

    def test_detect_motion_per_camera_background_model(self) -> None:
        """detect_motion should maintain separate background models per camera."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)

        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255

        with patch("cv2.createBackgroundSubtractorMOG2") as mock_mog2_factory:
            mock_subtractor1 = Mock()
            mock_subtractor2 = Mock()
            mock_mog2_factory.side_effect = [mock_subtractor1, mock_subtractor2]

            mock_subtractor1.apply.return_value = np.zeros((480, 640), dtype=np.uint8)
            mock_subtractor2.apply.return_value = np.zeros((480, 640), dtype=np.uint8)

            # First call for camera1 should create first subtractor
            extractor.detect_motion(frame1, camera_id="camera1")
            mock_subtractor1.apply.assert_called_once()

            # Call for camera2 should create second subtractor
            extractor.detect_motion(frame2, camera_id="camera2")
            mock_subtractor2.apply.assert_called_once()

            # Second call to camera1 should reuse first subtractor
            extractor.detect_motion(frame1, camera_id="camera1")
            assert mock_subtractor1.apply.call_count == 2


class TestFrameExtractorSaveFrame:
    """Tests for saving frames to disk."""

    def test_save_frame_creates_camera_directory(self, tmp_path) -> None:
        """save_frame should create camera-specific directory if it doesn't exist."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

            # Verify directory was created
            expected_dir = tmp_path / "camera1"
            assert expected_dir.exists()
            assert expected_dir.is_dir()

    def test_save_frame_returns_file_path(self, tmp_path) -> None:
        """save_frame should return the path to the saved frame."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)

        with patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

            assert isinstance(file_path, str)
            # Should contain camera_id and timestamp
            assert "camera1" in file_path
            assert "2025" in file_path

    def test_save_frame_uses_timestamp_in_filename(self, tmp_path) -> None:
        """save_frame should use ISO timestamp format in filename."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)

        with patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

            # Filename should contain timestamp components
            assert "20250129" in file_path or "2025-01-29" in file_path

    def test_save_frame_saves_as_jpeg(self, tmp_path) -> None:
        """save_frame should save frames in JPEG format."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

            assert file_path.endswith(".jpg") or file_path.endswith(".jpeg")

    def test_save_frame_calls_cv2_imwrite(self, tmp_path) -> None:
        """save_frame should use cv2.imwrite to save the frame."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            extractor.save_frame("camera1", frame, timestamp)

            mock_imwrite.assert_called_once()
            # Verify frame data passed to imwrite
            call_args = mock_imwrite.call_args[0]
            np.testing.assert_array_equal(call_args[1], frame)

    def test_save_frame_raises_on_write_failure(self, tmp_path) -> None:
        """save_frame should raise exception if cv2.imwrite fails."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = False  # Simulate write failure

            with pytest.raises(RuntimeError, match="Failed to save frame"):
                extractor.save_frame("camera1", frame, timestamp)


class TestFrameExtractorQueueDetection:
    """Tests for queueing frames to detection pipeline."""

    @pytest.mark.anyio
    async def test_queue_detection_adds_to_redis_queue(self) -> None:
        """queue_detection should add payload to Redis detection queue."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis)

        file_path = "/tmp/claude/rtsp_frames/camera1/20250129_123045.jpg"  # noqa: S108
        timestamp = datetime(2025, 1, 29, 12, 30, 45)

        await extractor.queue_detection("camera1", file_path, timestamp)

        # Verify redis add_to_queue was called
        mock_redis.add_to_queue.assert_called_once()

    @pytest.mark.anyio
    async def test_queue_detection_uses_detection_queue_payload_format(self) -> None:
        """queue_detection should create payload matching DetectionQueuePayload schema."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis)

        file_path = "/tmp/claude/rtsp_frames/camera1/20250129_123045.jpg"  # noqa: S108
        timestamp = datetime(2025, 1, 29, 12, 30, 45)

        await extractor.queue_detection("camera1", file_path, timestamp)

        # Get the payload from the call
        call_args = mock_redis.add_to_queue.call_args
        queue_name = call_args[0][0]
        payload = call_args[0][1]

        # Verify queue name
        assert queue_name == "detection_queue"

        # Verify payload structure matches DetectionQueuePayload
        assert payload["camera_id"] == "camera1"
        assert payload["file_path"] == file_path
        assert payload["media_type"] == "image"
        assert "timestamp" in payload
        assert "pipeline_start_time" in payload

    @pytest.mark.anyio
    async def test_queue_detection_includes_timestamp_iso_format(self) -> None:
        """queue_detection should include timestamp in ISO format."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis)

        file_path = "/tmp/claude/rtsp_frames/camera1/20250129_123045.jpg"  # noqa: S108
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)

        await extractor.queue_detection("camera1", file_path, timestamp)

        payload = mock_redis.add_to_queue.call_args[0][1]

        # Verify ISO format timestamp
        assert payload["timestamp"] == timestamp.isoformat()

    @pytest.mark.anyio
    async def test_queue_detection_includes_pipeline_start_time(self) -> None:
        """queue_detection should include pipeline_start_time for latency tracking."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis)

        file_path = "/tmp/claude/rtsp_frames/camera1/20250129_123045.jpg"  # noqa: S108
        timestamp = datetime(2025, 1, 29, 12, 30, 45)

        await extractor.queue_detection("camera1", file_path, timestamp)

        payload = mock_redis.add_to_queue.call_args[0][1]

        # pipeline_start_time should be set and in ISO format
        assert "pipeline_start_time" in payload
        assert isinstance(payload["pipeline_start_time"], str)

    @pytest.mark.anyio
    async def test_queue_detection_media_type_is_image(self) -> None:
        """queue_detection should always set media_type to 'image' for frames."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis)

        file_path = "/tmp/claude/rtsp_frames/camera1/20250129_123045.jpg"  # noqa: S108
        timestamp = datetime.now()

        await extractor.queue_detection("camera1", file_path, timestamp)

        payload = mock_redis.add_to_queue.call_args[0][1]
        assert payload["media_type"] == "image"


class TestFrameExtractorExtractFrame:
    """Tests for the main extract_frame method."""

    @pytest.mark.anyio
    async def test_extract_frame_detects_motion(self, tmp_path) -> None:
        """extract_frame should call detect_motion to check for motion."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = False  # No motion

            result = await extractor.extract_frame("camera1", frame, timestamp)

            mock_detect.assert_called_once_with(frame, camera_id="camera1")

    @pytest.mark.anyio
    async def test_extract_frame_saves_frame_on_motion(self, tmp_path) -> None:
        """extract_frame should save frame only when motion is detected."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            with patch.object(extractor, "save_frame") as mock_save:
                mock_detect.return_value = True  # Motion detected
                mock_save.return_value = str(tmp_path / "frame.jpg")

                await extractor.extract_frame("camera1", frame, timestamp)

                mock_save.assert_called_once_with("camera1", frame, timestamp)

    @pytest.mark.anyio
    async def test_extract_frame_skips_save_without_motion(self, tmp_path) -> None:
        """extract_frame should NOT save frame when no motion is detected."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            with patch.object(extractor, "save_frame") as mock_save:
                mock_detect.return_value = False  # No motion

                result = await extractor.extract_frame("camera1", frame, timestamp)

                mock_save.assert_not_called()
                assert result is None

    @pytest.mark.anyio
    async def test_extract_frame_queues_detection_on_motion(self, tmp_path) -> None:
        """extract_frame should queue frame for detection when motion detected."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            with patch.object(extractor, "save_frame") as mock_save:
                with patch.object(extractor, "queue_detection") as mock_queue:
                    mock_detect.return_value = True
                    mock_save.return_value = str(tmp_path / "frame.jpg")

                    await extractor.extract_frame("camera1", frame, timestamp)

                    mock_queue.assert_called_once_with(
                        "camera1", str(tmp_path / "frame.jpg"), timestamp
                    )

    @pytest.mark.anyio
    async def test_extract_frame_returns_file_path_on_motion(self, tmp_path) -> None:
        """extract_frame should return file path when motion detected and frame saved."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            with patch.object(extractor, "save_frame") as mock_save:
                with patch.object(extractor, "queue_detection"):
                    mock_detect.return_value = True
                    mock_save.return_value = str(tmp_path / "frame.jpg")

                    result = await extractor.extract_frame("camera1", frame, timestamp)

                    assert result == str(tmp_path / "frame.jpg")

    @pytest.mark.anyio
    async def test_extract_frame_returns_none_without_motion(self, tmp_path) -> None:
        """extract_frame should return None when no motion detected."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = False

            result = await extractor.extract_frame("camera1", frame, timestamp)

            assert result is None


class TestFrameExtractorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_motion_detection_with_empty_frame(self) -> None:
        """detect_motion should handle empty frames gracefully."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)

        # Empty frame
        frame = np.zeros((0, 0, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply") as mock_apply:
            mock_apply.return_value = np.zeros((0, 0), dtype=np.uint8)

            # Should not crash
            result = extractor.detect_motion(frame, camera_id="camera1")
            assert isinstance(result, bool)

    @pytest.mark.anyio
    async def test_extract_frame_with_none_frame_raises_error(self, tmp_path) -> None:
        """extract_frame should raise error when frame is None."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        timestamp = datetime.now()

        with pytest.raises((ValueError, TypeError)):
            await extractor.extract_frame("camera1", None, timestamp)

    def test_motion_detection_threshold_calculation(self) -> None:
        """Motion threshold should be inversely proportional to sensitivity."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()

        # Low sensitivity = high threshold (less motion detected)
        extractor_low = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.1)
        assert extractor_low._motion_threshold > 0.5

        # High sensitivity = low threshold (more motion detected)
        extractor_high = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.9)
        assert extractor_high._motion_threshold < 0.5

    @pytest.mark.anyio
    async def test_queue_detection_handles_redis_errors(self, tmp_path) -> None:
        """queue_detection should handle Redis connection errors gracefully."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = AsyncMock()
        mock_redis.add_to_queue.side_effect = Exception("Redis connection failed")

        extractor = FrameExtractor(redis_client=mock_redis)

        file_path = str(tmp_path / "frame.jpg")
        timestamp = datetime.now()

        # Should raise or log error appropriately
        with pytest.raises(Exception):
            await extractor.queue_detection("camera1", file_path, timestamp)
