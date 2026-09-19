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
        with patch("cv2.createBackgroundSubtractorMOG2", autospec=True) as mock_mog2:
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
        with pytest.raises(ValueError, match=r"motion_sensitivity must be between 0\.0 and 1\.0"):
            FrameExtractor(redis_client=mock_redis, motion_sensitivity=-0.1)

        with pytest.raises(ValueError, match=r"motion_sensitivity must be between 0\.0 and 1\.0"):
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

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
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

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
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

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
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

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
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

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
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

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
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

        with patch("cv2.createBackgroundSubtractorMOG2", autospec=True) as mock_mog2_factory:
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

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
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

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
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

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
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

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
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

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
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

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
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

        with patch.object(extractor, "detect_motion", autospec=True) as mock_detect:
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

        with patch.object(extractor, "detect_motion", autospec=True) as mock_detect:
            with patch.object(extractor, "save_frame", autospec=True) as mock_save:
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

        with patch.object(extractor, "detect_motion", autospec=True) as mock_detect:
            with patch.object(extractor, "save_frame", autospec=True) as mock_save:
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

        with patch.object(extractor, "detect_motion", autospec=True) as mock_detect:
            with patch.object(extractor, "save_frame", autospec=True) as mock_save:
                with patch.object(extractor, "queue_detection", autospec=True) as mock_queue:
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

        with patch.object(extractor, "detect_motion", autospec=True) as mock_detect:
            with patch.object(extractor, "save_frame", autospec=True) as mock_save:
                with patch.object(extractor, "queue_detection", autospec=True):
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

        with patch.object(extractor, "detect_motion", autospec=True) as mock_detect:
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

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
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


# =============================================================================
# WP4.4 wave-67: directory semantics, guard/boundary exactness, helper contracts
# =============================================================================


class TestFrameExtractorSaveFrameDirectorySemantics:
    """save_frame must create the full directory chain and tolerate re-saves."""

    def test_save_frame_creates_missing_parent_directories(self, tmp_path) -> None:
        """save_frame creates frame_save_dir and its parents when missing (parents=True).

        WP4.4 C3: the existing dir test used a tmp_path whose parent already
        existed, so parents=None/False/omitted mutants never crashed there —
        in production a missing frame_save_dir would FileNotFoundError every save.
        """
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        missing_base = tmp_path / "does" / "not" / "exist"
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(missing_base))

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

        assert (missing_base / "camera1").is_dir()
        assert Path(file_path).parent == missing_base / "camera1"

    def test_save_frame_twice_to_same_camera_does_not_raise(self, tmp_path) -> None:
        """Re-saving reuses the camera dir (exist_ok=True) — else second frame FileExistsError."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        ts1 = datetime(2025, 1, 29, 12, 30, 45, 123456)
        ts2 = datetime(2025, 1, 29, 12, 31, 0, 0)

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
            mock_imwrite.return_value = True
            first = extractor.save_frame("camera1", frame, ts1)
            second = extractor.save_frame("camera1", frame, ts2)

        assert Path(first).parent == Path(second).parent == tmp_path / "camera1"
        assert first != second

    def test_save_frame_passes_exact_resolved_path_to_imwrite(self, tmp_path) -> None:
        """cv2.imwrite gets the exact YYYYMMDD_HHMMSS_us.jpg path (WP4.4 C1/C2).

        The existing test asserted only call_args[1] (the frame), so imwrite(None)
        and the XX-wrapped strftime format both survived.
        """
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, frame_save_dir=str(tmp_path))

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)
        expected_name = "20250129_123045_123456.jpg"

        with patch("cv2.imwrite", autospec=True) as mock_imwrite:
            mock_imwrite.return_value = True
            file_path = extractor.save_frame("camera1", frame, timestamp)

            written_path = mock_imwrite.call_args.args[0]
            assert written_path == str(tmp_path / "camera1" / expected_name)

        assert Path(file_path).name == expected_name


class TestFrameExtractorMotionDetectionSemantics:
    """detect_motion guards/boundaries and the sensitivity→threshold curve, exactly."""

    def test_detect_motion_empty_frame_returns_false_without_subtractor_call(self) -> None:
        """Empty frame short-circuits: exactly False, subtractor never touched."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis)
        frame = np.zeros((0, 0, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.zeros((0, 0), dtype=np.uint8)
            result = extractor.detect_motion(frame, camera_id="camera1")

        assert result is False  # kills `return False -> True`
        mock_apply.assert_not_called()  # kills `frame.size == 0 -> == 1`

    def test_detect_motion_single_element_frame_is_processed_normally(self) -> None:
        """A size-1 (non-empty) frame must go through detection, not the empty guard."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.5)
        frame = np.array([[[255, 255, 255]]], dtype=np.uint8)  # frame.size == 1

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.array([[255]], dtype=np.uint8)
            result = extractor.detect_motion(frame, camera_id="camera1")

        # Original: 1.0 > 0.25 -> True. `== 1` guard mutant returns False.
        assert result is True

    def test_detect_motion_single_pixel_mask_is_not_treated_as_empty(self) -> None:
        """A size-1 foreground mask with a nonzero pixel is motion (ratio 1.0)."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.5)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.array([[255]], dtype=np.uint8)
            result = extractor.detect_motion(frame, camera_id="camera1")

        assert result is True  # kills `fg_mask.size == 0 -> == 1`

    def test_motion_threshold_follows_documented_squared_curve(self) -> None:
        """_motion_threshold is exactly (1.0 - sensitivity) ** 2 (docstring curve)."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        for sensitivity, expected in [(0.0, 1.0), (0.1, 0.81), (0.5, 0.25), (0.9, 0.01)]:
            extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=sensitivity)
            assert extractor._motion_threshold == pytest.approx(expected)  # kills ** 3

    def test_detect_motion_at_exact_threshold_boundary_is_false(self) -> None:
        """Motion ratio EQUAL to the threshold is NOT motion: comparison is strict >."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()
        # sensitivity 0.0 -> threshold (1-0)**2 == 1.0 exactly
        extractor = FrameExtractor(redis_client=mock_redis, motion_sensitivity=0.0)

        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        with patch.object(extractor._bg_subtractor, "apply", autospec=True) as mock_apply:
            mock_apply.return_value = np.full((8, 8), 255, dtype=np.uint8)
            result = extractor.detect_motion(frame, camera_id="camera1")

        assert result is False  # original: 1.0 > 1.0 False; the >= mutant returns True

    def test_init_accepts_sensitivity_range_endpoints(self) -> None:
        """Sensitivity 0.0 and 1.0 are documented valid — must construct; ±ε still raises."""
        from backend.services.frame_extractor import FrameExtractor

        mock_redis = Mock()

        low = FrameExtractor(
            redis_client=mock_redis, motion_sensitivity=0.0
        )  # kills `0.0 <=` -> `0.0 <`
        assert low.motion_sensitivity == 0.0
        high = FrameExtractor(
            redis_client=mock_redis, motion_sensitivity=1.0
        )  # kills `<= 1.0` -> `< 1.0`
        assert high.motion_sensitivity == 1.0

        with pytest.raises(ValueError):
            FrameExtractor(redis_client=mock_redis, motion_sensitivity=-0.001)
        with pytest.raises(ValueError):
            FrameExtractor(redis_client=mock_redis, motion_sensitivity=1.001)


class TestFrameExtractorTestabilityHelpers:
    """_is_mock / _create_subtractor / _MOG2Wrapper contracts, asserted directly."""

    def test_is_mock_detects_either_marker(self) -> None:
        """_is_mock is True for _mock_name OR assert_called markers, False otherwise.

        Only directly-callable: every Mock has BOTH attrs (auto-attribute), so
        marker renames and the hasattr(None, …) mutant are invisible through Mocks.
        """
        from types import SimpleNamespace

        from backend.services.frame_extractor import _is_mock

        assert _is_mock(Mock()) is True
        assert _is_mock(SimpleNamespace(_mock_name="x")) is True
        assert _is_mock(SimpleNamespace(assert_called=lambda: None)) is True
        assert _is_mock(SimpleNamespace()) is False
        assert _is_mock(object()) is False

    def test_mog2_wrapper_stores_and_delegates_subtractor(self) -> None:
        """_MOG2Wrapper must store the given subtractor and delegate apply() to it."""
        from backend.services.frame_extractor import _MOG2Wrapper

        class StubSubtractor:
            def __init__(self) -> None:
                self.calls = []

            def apply(self, frame):
                self.calls.append(frame)
                return frame

        stub = StubSubtractor()
        wrapper = _MOG2Wrapper(stub)

        assert wrapper._subtractor is stub  # kills the None-store mutant
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        np.testing.assert_array_equal(wrapper.apply(frame), frame)
        assert stub.calls == [frame]

    def test_create_subtractor_wraps_non_mock_factory_result(self) -> None:
        """_create_subtractor wraps a REAL (non-Mock) subtractor, retaining it inside."""
        from types import SimpleNamespace

        from backend.services.frame_extractor import _create_subtractor, _MOG2Wrapper

        stub = SimpleNamespace(apply=lambda frame: frame)  # deliberately NOT a Mock
        with patch("cv2.createBackgroundSubtractorMOG2", autospec=True) as mock_factory:
            mock_factory.return_value = stub
            subtractor = _create_subtractor()

        assert isinstance(subtractor, _MOG2Wrapper)
        assert subtractor._subtractor is stub  # kills the wraps-None mutant
