"""Unit tests for VideoProcessor service.

This module provides comprehensive tests for the video_processor.py module,
covering:
- Initialization and directory creation
- FFmpeg availability checking
- Video metadata extraction via ffprobe
- Thumbnail extraction via ffmpeg
- Frame extraction for object detection
- Cleanup operations
- Error handling paths

All subprocess calls to ffmpeg/ffprobe are mocked.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.video_processor import (
    DEFAULT_THUMBNAIL_SIZE,
    VideoProcessingError,
    VideoProcessor,
)

# =============================================================================
# Initialization Tests
# =============================================================================


class TestVideoProcessorInit:
    """Test VideoProcessor initialization."""

    def test_init_creates_output_dir(self, tmp_path: Path) -> None:
        """Test that output directory is created on initialization."""
        output_dir = tmp_path / "new_thumbnails"
        assert not output_dir.exists()

        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            processor = VideoProcessor(output_dir=str(output_dir))

        assert output_dir.exists()
        assert processor.output_dir == output_dir

    def test_init_existing_dir(self, tmp_path: Path) -> None:
        """Test initialization with existing directory."""
        output_dir = tmp_path / "thumbnails"
        output_dir.mkdir()

        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            processor = VideoProcessor(output_dir=str(output_dir))

        assert processor.output_dir == output_dir

    def test_ensure_output_dir_error(self, tmp_path: Path) -> None:
        """Test _ensure_output_dir raises on permission error."""
        # Create a read-only parent directory
        output_dir = "/nonexistent/path/that/cannot/be/created"

        with (
            patch.object(VideoProcessor, "_check_ffmpeg_available"),
            patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")),
            pytest.raises(PermissionError),
        ):
            VideoProcessor(output_dir=output_dir)


# =============================================================================
# FFmpeg Availability Tests
# =============================================================================


class TestFFmpegAvailability:
    """Test FFmpeg/FFprobe availability checking."""

    def test_check_ffmpeg_available_success(self, tmp_path: Path) -> None:
        """Test successful ffmpeg availability check."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            processor = VideoProcessor(output_dir=str(tmp_path))

        # Should be called twice - once for ffmpeg, once for ffprobe
        assert mock_run.call_count == 2
        assert processor is not None

    def test_check_ffmpeg_not_found(self, tmp_path: Path) -> None:
        """Test handling when ffmpeg is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
            # Should not raise - just logs warning
            processor = VideoProcessor(output_dir=str(tmp_path))
            assert processor is not None

    def test_check_ffmpeg_timeout(self, tmp_path: Path) -> None:
        """Test handling when ffmpeg check times out."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 5)):
            # Should not raise - just logs warning
            processor = VideoProcessor(output_dir=str(tmp_path))
            assert processor is not None

    def test_check_ffmpeg_called_process_error(self, tmp_path: Path) -> None:
        """Test handling when ffmpeg returns error."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr="Error"),
        ):
            # Should not raise - just logs warning
            processor = VideoProcessor(output_dir=str(tmp_path))
            assert processor is not None


# =============================================================================
# Video Metadata Extraction Tests
# =============================================================================


class TestGetVideoMetadata:
    """Test video metadata extraction."""

    @pytest.fixture
    def video_processor(self, tmp_path: Path) -> VideoProcessor:
        """Create VideoProcessor with mocked ffmpeg check."""
        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            return VideoProcessor(output_dir=str(tmp_path))

    @pytest.fixture
    def sample_ffprobe_output(self) -> dict:
        """Sample ffprobe JSON output."""
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                },
            ],
            "format": {
                "duration": "120.5",
                "format_name": "mp4",
            },
        }

    @pytest.mark.asyncio
    async def test_get_video_metadata_file_not_found(self, video_processor: VideoProcessor) -> None:
        """Test get_video_metadata raises error for missing file."""
        with pytest.raises(VideoProcessingError, match="Video file not found"):
            await video_processor.get_video_metadata("/nonexistent/video.mp4")

    @pytest.mark.asyncio
    async def test_get_video_metadata_success(
        self,
        video_processor: VideoProcessor,
        tmp_path: Path,
        sample_ffprobe_output: dict,
    ) -> None:
        """Test successful video metadata extraction."""
        # Create a dummy video file
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(sample_ffprobe_output)
        mock_result.stderr = ""

        with patch("asyncio.to_thread", return_value=mock_result):
            metadata = await video_processor.get_video_metadata(str(video_path))

        assert metadata["duration"] == 120.5
        assert metadata["video_codec"] == "h264"
        assert metadata["video_width"] == 1920
        assert metadata["video_height"] == 1080
        assert metadata["file_type"] == "video/mp4"

    @pytest.mark.asyncio
    async def test_get_video_metadata_ffprobe_error(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling ffprobe command failure."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ffprobe error: invalid file"

        with (
            patch("asyncio.to_thread", return_value=mock_result),
            pytest.raises(VideoProcessingError, match="ffprobe failed"),
        ):
            await video_processor.get_video_metadata(str(video_path))

    @pytest.mark.asyncio
    async def test_get_video_metadata_no_video_stream(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling file with no video stream."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake content")

        # Only audio stream, no video
        ffprobe_output = {
            "streams": [{"codec_type": "audio", "codec_name": "aac"}],
            "format": {"duration": "60.0"},
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_result.stderr = ""

        with (
            patch("asyncio.to_thread", return_value=mock_result),
            pytest.raises(VideoProcessingError, match="No video stream found"),
        ):
            await video_processor.get_video_metadata(str(video_path))

    @pytest.mark.asyncio
    async def test_get_video_metadata_json_decode_error(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling invalid JSON from ffprobe."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake content")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json{"
        mock_result.stderr = ""

        with (
            patch("asyncio.to_thread", return_value=mock_result),
            pytest.raises(VideoProcessingError, match="Failed to parse ffprobe output"),
        ):
            await video_processor.get_video_metadata(str(video_path))

    @pytest.mark.asyncio
    async def test_get_video_metadata_timeout(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling ffprobe timeout."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake content")

        with (
            patch(
                "asyncio.to_thread",
                side_effect=subprocess.TimeoutExpired("ffprobe", 30),
            ),
            pytest.raises(VideoProcessingError, match="ffprobe timed out"),
        ):
            await video_processor.get_video_metadata(str(video_path))

    @pytest.mark.asyncio
    async def test_get_video_metadata_unexpected_error(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling unexpected errors during metadata extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake content")

        with (
            patch("asyncio.to_thread", side_effect=RuntimeError("Unexpected error")),
            pytest.raises(VideoProcessingError, match="Failed to get video metadata"),
        ):
            await video_processor.get_video_metadata(str(video_path))


# =============================================================================
# Thumbnail Extraction Tests
# =============================================================================


class TestExtractThumbnail:
    """Test thumbnail extraction."""

    @pytest.fixture
    def video_processor(self, tmp_path: Path) -> VideoProcessor:
        """Create VideoProcessor with mocked ffmpeg check."""
        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            return VideoProcessor(output_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_extract_thumbnail_file_not_found(self, video_processor: VideoProcessor) -> None:
        """Test extract_thumbnail returns None for missing file."""
        result = await video_processor.extract_thumbnail("/nonexistent/video.mp4")
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_thumbnail_success_with_timestamp(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test successful thumbnail extraction with explicit timestamp."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        output_path = str(tmp_path / "thumb.jpg")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        # Create the output file to simulate ffmpeg success
        async def mock_to_thread(func, *args, **kwargs):
            # Simulate ffmpeg creating the output file
            Path(output_path).write_bytes(b"fake jpeg data")
            return mock_result

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await video_processor.extract_thumbnail(
                str(video_path), output_path=output_path, timestamp=5.0
            )

        assert result == output_path

    @pytest.mark.asyncio
    async def test_extract_thumbnail_auto_timestamp(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test thumbnail extraction with automatic timestamp calculation."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        # Mock get_video_metadata to return duration
        mock_metadata = {"duration": 100.0}

        mock_result = MagicMock()
        mock_result.returncode = 0

        async def mock_to_thread(func, *args, **kwargs):
            # Create output file
            output_path = video_processor.output_dir / f"{video_path.stem}_thumb.jpg"
            output_path.write_bytes(b"fake jpeg")
            return mock_result

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            result = await video_processor.extract_thumbnail(str(video_path))

        assert result is not None
        assert "thumb.jpg" in result

    @pytest.mark.asyncio
    async def test_extract_thumbnail_metadata_failure_fallback(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test thumbnail uses fallback timestamp when metadata extraction fails."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_result = MagicMock()
        mock_result.returncode = 0

        async def mock_to_thread(func, *args, **kwargs):
            output_path = video_processor.output_dir / f"{video_path.stem}_thumb.jpg"
            output_path.write_bytes(b"fake jpeg")
            return mock_result

        with (
            patch.object(
                video_processor,
                "get_video_metadata",
                side_effect=VideoProcessingError("Metadata failed"),
            ),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            result = await video_processor.extract_thumbnail(str(video_path))

        assert result is not None

    @pytest.mark.asyncio
    async def test_extract_thumbnail_ffmpeg_error(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling ffmpeg thumbnail extraction failure."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ffmpeg error"

        with (
            patch.object(
                video_processor,
                "get_video_metadata",
                return_value={"duration": 10.0},
            ),
            patch("asyncio.to_thread", return_value=mock_result),
        ):
            result = await video_processor.extract_thumbnail(str(video_path))

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_thumbnail_output_not_created(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling when ffmpeg succeeds but output file not created."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_result = MagicMock()
        mock_result.returncode = 0  # Success return code but no file created

        with (
            patch.object(
                video_processor,
                "get_video_metadata",
                return_value={"duration": 10.0},
            ),
            patch("asyncio.to_thread", return_value=mock_result),
        ):
            result = await video_processor.extract_thumbnail(str(video_path))

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_thumbnail_timeout(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling ffmpeg timeout during thumbnail extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        # First call for metadata, second call for ffmpeg
        call_count = [0]

        async def mock_to_thread(func, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Return metadata first
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = json.dumps(
                    {
                        "streams": [
                            {
                                "codec_type": "video",
                                "codec_name": "h264",
                                "width": 1920,
                                "height": 1080,
                            }
                        ],
                        "format": {"duration": "10.0"},
                    }
                )
                return mock_result
            # Then timeout on ffmpeg call
            raise subprocess.TimeoutExpired("ffmpeg", 30)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await video_processor.extract_thumbnail(str(video_path))

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_thumbnail_unexpected_error(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling unexpected errors during thumbnail extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        with (
            patch.object(
                video_processor,
                "get_video_metadata",
                side_effect=RuntimeError("Unexpected"),
            ),
        ):
            result = await video_processor.extract_thumbnail(str(video_path))

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_thumbnail_custom_size(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test thumbnail extraction with custom size."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")
        output_path = str(tmp_path / "thumb.jpg")

        mock_result = MagicMock()
        mock_result.returncode = 0

        captured_cmd = []

        async def mock_to_thread(func, cmd, *args, **kwargs):
            captured_cmd.extend(cmd)
            Path(output_path).write_bytes(b"fake jpeg")
            return mock_result

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await video_processor.extract_thumbnail(
                str(video_path),
                output_path=output_path,
                timestamp=1.0,
                size=(640, 480),
            )

        assert result == output_path
        # Verify scale filter contains custom size
        assert "640:480" in "".join(captured_cmd)


# =============================================================================
# Frame Extraction for Detection Tests
# =============================================================================


class TestExtractFramesForDetection:
    """Test frame extraction for object detection."""

    @pytest.fixture
    def video_processor(self, tmp_path: Path) -> VideoProcessor:
        """Create VideoProcessor with mocked ffmpeg check."""
        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            return VideoProcessor(output_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_extract_frames_file_not_found(self, video_processor: VideoProcessor) -> None:
        """Test extract_frames_for_detection returns empty list for missing file."""
        result = await video_processor.extract_frames_for_detection("/nonexistent/video.mp4")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_frames_success(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test successful frame extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_metadata = {"duration": 10.0}

        mock_result = MagicMock()
        mock_result.returncode = 0

        frame_count = [0]

        async def mock_to_thread(func, cmd, *args, **kwargs):
            # Create frame files
            output_path = cmd[-1]  # Last argument is output path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(b"fake frame")
            frame_count[0] += 1
            return mock_result

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            result = await video_processor.extract_frames_for_detection(
                str(video_path), interval_seconds=2.0, max_frames=5
            )

        # Should extract frames at 0.5, 2.5, 4.5, 6.5, 8.5 seconds (5 frames for 10s video)
        assert len(result) == 5
        for frame_path in result:
            assert Path(frame_path).exists()

    @pytest.mark.asyncio
    async def test_extract_frames_zero_duration(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling video with zero duration."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_metadata = {"duration": 0}

        with patch.object(video_processor, "get_video_metadata", return_value=mock_metadata):
            result = await video_processor.extract_frames_for_detection(str(video_path))

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_frames_short_video(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test frame extraction for very short video."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        # Video shorter than default interval
        mock_metadata = {"duration": 0.3}

        mock_result = MagicMock()
        mock_result.returncode = 0

        async def mock_to_thread(func, cmd, *args, **kwargs):
            output_path = cmd[-1]
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(b"fake frame")
            return mock_result

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            result = await video_processor.extract_frames_for_detection(str(video_path))

        # Should extract at least one frame at 10% of duration
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_extract_frames_with_size(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test frame extraction with custom size."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_metadata = {"duration": 5.0}
        mock_result = MagicMock()
        mock_result.returncode = 0

        captured_cmds = []

        async def mock_to_thread(func, cmd, *args, **kwargs):
            captured_cmds.append(cmd)
            output_path = cmd[-1]
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(b"fake frame")
            return mock_result

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            result = await video_processor.extract_frames_for_detection(
                str(video_path), size=(640, 480)
            )

        assert len(result) > 0
        # Verify scale filter was applied
        assert any("640:480" in "".join(cmd) for cmd in captured_cmds)

    @pytest.mark.asyncio
    async def test_extract_frames_ffmpeg_failure(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling ffmpeg failure during frame extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_metadata = {"duration": 10.0}
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ffmpeg error"

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch("asyncio.to_thread", return_value=mock_result),
        ):
            result = await video_processor.extract_frames_for_detection(str(video_path))

        # Should return empty list - all frames failed
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_frames_metadata_error(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling metadata extraction error."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        with patch.object(
            video_processor,
            "get_video_metadata",
            side_effect=VideoProcessingError("Metadata failed"),
        ):
            result = await video_processor.extract_frames_for_detection(str(video_path))

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_frames_timeout(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling timeout during frame extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_metadata = {"duration": 10.0}

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch(
                "asyncio.to_thread",
                side_effect=subprocess.TimeoutExpired("ffmpeg", 30),
            ),
        ):
            result = await video_processor.extract_frames_for_detection(str(video_path))

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_frames_unexpected_error(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test handling unexpected error during frame extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        mock_metadata = {"duration": 10.0}

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch("asyncio.to_thread", side_effect=RuntimeError("Unexpected")),
        ):
            result = await video_processor.extract_frames_for_detection(str(video_path))

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_frames_max_frames_limit(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test that max_frames limit is respected."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        # Long video that would have many frames
        mock_metadata = {"duration": 1000.0}
        mock_result = MagicMock()
        mock_result.returncode = 0

        frame_extract_count = [0]

        async def mock_to_thread(func, cmd, *args, **kwargs):
            output_path = cmd[-1]
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(b"fake frame")
            frame_extract_count[0] += 1
            return mock_result

        with (
            patch.object(video_processor, "get_video_metadata", return_value=mock_metadata),
            patch("asyncio.to_thread", side_effect=mock_to_thread),
        ):
            result = await video_processor.extract_frames_for_detection(
                str(video_path), max_frames=10
            )

        assert len(result) == 10
        assert frame_extract_count[0] == 10


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestCleanupOperations:
    """Test cleanup operations."""

    @pytest.fixture
    def video_processor(self, tmp_path: Path) -> VideoProcessor:
        """Create VideoProcessor with mocked ffmpeg check."""
        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            return VideoProcessor(output_dir=str(tmp_path))

    def test_cleanup_extracted_frames_success(self, video_processor: VideoProcessor) -> None:
        """Test successful cleanup of extracted frames."""
        # Create frames directory
        video_stem = "test_video"
        frames_dir = video_processor.output_dir / f"{video_stem}_frames"
        frames_dir.mkdir(parents=True)
        (frames_dir / "frame_0000.jpg").write_bytes(b"fake frame")
        (frames_dir / "frame_0001.jpg").write_bytes(b"fake frame")

        result = video_processor.cleanup_extracted_frames(f"/path/to/{video_stem}.mp4")

        assert result is True
        assert not frames_dir.exists()

    def test_cleanup_extracted_frames_nonexistent(self, video_processor: VideoProcessor) -> None:
        """Test cleanup when frames directory doesn't exist."""
        result = video_processor.cleanup_extracted_frames("/nonexistent/video.mp4")
        assert result is False

    def test_cleanup_extracted_frames_error(self, video_processor: VideoProcessor) -> None:
        """Test cleanup error handling."""
        video_stem = "test_video"
        frames_dir = video_processor.output_dir / f"{video_stem}_frames"
        frames_dir.mkdir(parents=True)

        with patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            result = video_processor.cleanup_extracted_frames(f"/path/to/{video_stem}.mp4")

        assert result is False


# =============================================================================
# Detection-specific Methods Tests
# =============================================================================


class TestDetectionMethods:
    """Test detection-specific convenience methods."""

    @pytest.fixture
    def video_processor(self, tmp_path: Path) -> VideoProcessor:
        """Create VideoProcessor with mocked ffmpeg check."""
        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            return VideoProcessor(output_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_extract_thumbnail_for_detection(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test extract_thumbnail_for_detection convenience method."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        expected_output = str(video_processor.output_dir / "123_video_thumb.jpg")

        with patch.object(
            video_processor, "extract_thumbnail", return_value=expected_output
        ) as mock_extract:
            result = await video_processor.extract_thumbnail_for_detection(
                str(video_path), detection_id="123"
            )

        assert result == expected_output
        mock_extract.assert_called_once_with(
            str(video_path), expected_output, size=DEFAULT_THUMBNAIL_SIZE
        )

    @pytest.mark.asyncio
    async def test_extract_thumbnail_for_detection_int_id(
        self, video_processor: VideoProcessor, tmp_path: Path
    ) -> None:
        """Test extract_thumbnail_for_detection with integer detection ID."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")

        expected_output = str(video_processor.output_dir / "456_video_thumb.jpg")

        with patch.object(video_processor, "extract_thumbnail", return_value=expected_output):
            result = await video_processor.extract_thumbnail_for_detection(
                str(video_path), detection_id=456
            )

        assert result == expected_output

    def test_get_output_path(self, video_processor: VideoProcessor) -> None:
        """Test get_output_path returns correct path."""
        path = video_processor.get_output_path("123")
        assert path.name == "123_video_thumb.jpg"
        assert path.parent == video_processor.output_dir

    def test_get_output_path_int_id(self, video_processor: VideoProcessor) -> None:
        """Test get_output_path with integer ID."""
        path = video_processor.get_output_path(456)
        assert path.name == "456_video_thumb.jpg"

    def test_delete_thumbnail_success(self, video_processor: VideoProcessor) -> None:
        """Test successful thumbnail deletion."""
        # Create thumbnail file
        thumbnail_path = video_processor.output_dir / "123_video_thumb.jpg"
        thumbnail_path.write_bytes(b"fake thumbnail")

        result = video_processor.delete_thumbnail("123")

        assert result is True
        assert not thumbnail_path.exists()

    def test_delete_thumbnail_not_found(self, video_processor: VideoProcessor) -> None:
        """Test deleting nonexistent thumbnail."""
        result = video_processor.delete_thumbnail("nonexistent")
        assert result is False

    def test_delete_thumbnail_error(self, video_processor: VideoProcessor) -> None:
        """Test thumbnail deletion error handling."""
        # Create thumbnail file
        thumbnail_path = video_processor.output_dir / "123_video_thumb.jpg"
        thumbnail_path.write_bytes(b"fake thumbnail")

        with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
            result = video_processor.delete_thumbnail("123")

        assert result is False


# =============================================================================
# MIME Type Tests
# =============================================================================


class TestMimeType:
    """Test MIME type detection."""

    @pytest.fixture
    def video_processor(self, tmp_path: Path) -> VideoProcessor:
        """Create VideoProcessor with mocked ffmpeg check."""
        with patch.object(VideoProcessor, "_check_ffmpeg_available"):
            return VideoProcessor(output_dir=str(tmp_path))

    def test_get_mime_type_mp4(self, video_processor: VideoProcessor) -> None:
        """Test MIME type for MP4 files."""
        assert video_processor._get_mime_type("/path/to/video.mp4") == "video/mp4"

    def test_get_mime_type_mkv(self, video_processor: VideoProcessor) -> None:
        """Test MIME type for MKV files."""
        assert video_processor._get_mime_type("/path/to/video.mkv") == "video/x-matroska"

    def test_get_mime_type_avi(self, video_processor: VideoProcessor) -> None:
        """Test MIME type for AVI files."""
        assert video_processor._get_mime_type("/path/to/video.avi") == "video/x-msvideo"

    def test_get_mime_type_mov(self, video_processor: VideoProcessor) -> None:
        """Test MIME type for MOV files."""
        assert video_processor._get_mime_type("/path/to/video.mov") == "video/quicktime"

    def test_get_mime_type_unknown(self, video_processor: VideoProcessor) -> None:
        """Test MIME type for unknown extension falls back to default."""
        # Should return default video MIME type
        mime_type = video_processor._get_mime_type("/path/to/video.xyz")
        assert mime_type == "video/mp4"  # Default video MIME
