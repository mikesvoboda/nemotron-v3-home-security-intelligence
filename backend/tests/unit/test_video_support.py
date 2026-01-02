"""Unit tests for video file support in file watcher and detections API.

Tests cover:
- Video file extension detection (is_video_file, is_supported_media_file)
- Video file validation (is_valid_video)
- Media type detection (get_media_type)
- Video processing in file watcher queue
- Video streaming endpoint
- Video thumbnail endpoint
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.file_watcher import (
    IMAGE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    VIDEO_EXTENSIONS,
    get_media_type,
    is_supported_media_file,
    is_valid_media_file,
    is_valid_video,
    is_video_file,
)

# =============================================================================
# Video Extension Detection Tests
# =============================================================================


class TestVideoExtensionDetection:
    """Test video file extension detection functions."""

    def test_is_video_file_mp4(self) -> None:
        """Test is_video_file recognizes MP4 files."""
        assert is_video_file("/path/to/video.mp4") is True
        assert is_video_file("/path/to/video.MP4") is True

    def test_is_video_file_mkv(self) -> None:
        """Test is_video_file recognizes MKV files."""
        assert is_video_file("/path/to/video.mkv") is True
        assert is_video_file("/path/to/video.MKV") is True

    def test_is_video_file_avi(self) -> None:
        """Test is_video_file recognizes AVI files."""
        assert is_video_file("/path/to/video.avi") is True
        assert is_video_file("/path/to/video.AVI") is True

    def test_is_video_file_mov(self) -> None:
        """Test is_video_file recognizes MOV files."""
        assert is_video_file("/path/to/video.mov") is True
        assert is_video_file("/path/to/video.MOV") is True

    def test_is_video_file_non_video(self) -> None:
        """Test is_video_file rejects non-video files."""
        assert is_video_file("/path/to/file.jpg") is False
        assert is_video_file("/path/to/file.png") is False
        assert is_video_file("/path/to/file.txt") is False
        assert is_video_file("/path/to/file.pdf") is False
        assert is_video_file("/path/to/file") is False

    def test_is_supported_media_file_images(self) -> None:
        """Test is_supported_media_file accepts image files."""
        assert is_supported_media_file("/path/to/image.jpg") is True
        assert is_supported_media_file("/path/to/image.jpeg") is True
        assert is_supported_media_file("/path/to/image.png") is True

    def test_is_supported_media_file_videos(self) -> None:
        """Test is_supported_media_file accepts video files."""
        assert is_supported_media_file("/path/to/video.mp4") is True
        assert is_supported_media_file("/path/to/video.mkv") is True
        assert is_supported_media_file("/path/to/video.avi") is True
        assert is_supported_media_file("/path/to/video.mov") is True

    def test_is_supported_media_file_unsupported(self) -> None:
        """Test is_supported_media_file rejects unsupported files."""
        assert is_supported_media_file("/path/to/file.txt") is False
        assert is_supported_media_file("/path/to/file.pdf") is False
        assert is_supported_media_file("/path/to/file.webm") is False

    def test_extension_sets_are_disjoint(self) -> None:
        """Test that image and video extension sets don't overlap."""
        assert IMAGE_EXTENSIONS.isdisjoint(VIDEO_EXTENSIONS)
        assert SUPPORTED_EXTENSIONS == IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


# =============================================================================
# Media Type Detection Tests
# =============================================================================


class TestGetMediaType:
    """Test media type detection function."""

    def test_get_media_type_image(self) -> None:
        """Test get_media_type returns 'image' for image files."""
        assert get_media_type("/path/to/image.jpg") == "image"
        assert get_media_type("/path/to/image.jpeg") == "image"
        assert get_media_type("/path/to/image.png") == "image"
        assert get_media_type("/path/to/image.PNG") == "image"

    def test_get_media_type_video(self) -> None:
        """Test get_media_type returns 'video' for video files."""
        assert get_media_type("/path/to/video.mp4") == "video"
        assert get_media_type("/path/to/video.mkv") == "video"
        assert get_media_type("/path/to/video.avi") == "video"
        assert get_media_type("/path/to/video.mov") == "video"
        assert get_media_type("/path/to/video.MOV") == "video"

    def test_get_media_type_unsupported(self) -> None:
        """Test get_media_type returns None for unsupported files."""
        assert get_media_type("/path/to/file.txt") is None
        assert get_media_type("/path/to/file.pdf") is None
        assert get_media_type("/path/to/file") is None


# =============================================================================
# Video Validation Tests
# =============================================================================


class TestVideoValidation:
    """Test video file validation functions."""

    def test_is_valid_video_valid_file(self, tmp_path: Path) -> None:
        """Test is_valid_video accepts valid video files (by size)."""
        video_path = tmp_path / "test.mp4"
        # Create file with content larger than 1KB minimum
        video_path.write_bytes(b"x" * 2048)

        assert is_valid_video(str(video_path)) is True

    def test_is_valid_video_empty_file(self, tmp_path: Path) -> None:
        """Test is_valid_video rejects empty files."""
        video_path = tmp_path / "empty.mp4"
        video_path.touch()  # Create empty file

        assert is_valid_video(str(video_path)) is False

    def test_is_valid_video_too_small(self, tmp_path: Path) -> None:
        """Test is_valid_video rejects files smaller than 1KB."""
        video_path = tmp_path / "small.mp4"
        video_path.write_bytes(b"x" * 500)  # Less than 1KB

        assert is_valid_video(str(video_path)) is False

    def test_is_valid_video_nonexistent(self) -> None:
        """Test is_valid_video rejects nonexistent files."""
        assert is_valid_video("/path/that/does/not/exist.mp4") is False

    def test_is_valid_media_file_image(self, tmp_path: Path) -> None:
        """Test is_valid_media_file with valid image above minimum size threshold."""
        from PIL import Image

        image_path = tmp_path / "test.jpg"
        # Create a valid image large enough to pass minimum size validation (>10KB)
        size = (640, 480)
        img = Image.new("RGB", size, color="red")
        # Add gradient pattern to increase file size
        pixels = img.load()
        if pixels is not None:
            for y in range(size[1]):
                for x in range(size[0]):
                    pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
        img.save(image_path, "JPEG", quality=95)

        assert is_valid_media_file(str(image_path)) is True

    def test_is_valid_media_file_video(self, tmp_path: Path) -> None:
        """Test is_valid_media_file with valid video."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"x" * 2048)

        assert is_valid_media_file(str(video_path)) is True

    def test_is_valid_media_file_unsupported(self, tmp_path: Path) -> None:
        """Test is_valid_media_file with unsupported file."""
        text_path = tmp_path / "test.txt"
        text_path.write_text("not a media file")

        assert is_valid_media_file(str(text_path)) is False


# =============================================================================
# FileWatcher Video Processing Tests
# =============================================================================


class TestFileWatcherVideoProcessing:
    """Test video file processing in FileWatcher."""

    @pytest.fixture
    def temp_camera_root(self, tmp_path: Path) -> Path:
        """Create temporary camera directory structure."""
        camera_root = tmp_path / "foscam"
        camera_root.mkdir()
        (camera_root / "camera1").mkdir()
        return camera_root

    @pytest.fixture
    def mock_redis_client(self) -> AsyncMock:
        """Mock Redis client."""
        from backend.core.redis import QueueAddResult

        mock_client = AsyncMock()
        # Mock add_to_queue_safe (the method actually used by FileWatcher)
        mock_client.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        return mock_client

    @pytest.fixture
    def file_watcher(self, temp_camera_root: Path, mock_redis_client: AsyncMock):
        """Create FileWatcher instance with mocked dependencies."""
        from backend.services.file_watcher import FileWatcher

        # Mock settings to avoid DATABASE_URL validation error
        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(temp_camera_root)

        # Mock DedupeService to avoid additional settings calls
        mock_dedupe_service = MagicMock()
        mock_dedupe_service.is_duplicate_and_mark = AsyncMock(return_value=(False, None))

        with patch("backend.services.file_watcher.get_settings", return_value=mock_settings):
            watcher = FileWatcher(
                camera_root=str(temp_camera_root),
                redis_client=mock_redis_client,
                debounce_delay=0.1,
                dedupe_service=mock_dedupe_service,
            )
        return watcher

    @pytest.mark.asyncio
    async def test_process_video_file(
        self, file_watcher, temp_camera_root: Path, mock_redis_client: AsyncMock
    ) -> None:
        """Test processing a valid video file."""
        camera_dir = temp_camera_root / "camera1"
        video_path = camera_dir / "test.mp4"
        video_path.write_bytes(b"x" * 2048)

        await file_watcher._process_file(str(video_path))

        # Verify Redis queue was called with correct data
        mock_redis_client.add_to_queue_safe.assert_awaited_once()
        call_args = mock_redis_client.add_to_queue_safe.call_args

        assert call_args[0][0] == "detection_queue"
        data = call_args[0][1]
        assert data["camera_id"] == "camera1"
        assert data["file_path"] == str(video_path)
        assert data["media_type"] == "video"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_process_video_file_mkv(
        self, file_watcher, temp_camera_root: Path, mock_redis_client: AsyncMock
    ) -> None:
        """Test processing MKV video file."""
        camera_dir = temp_camera_root / "camera1"
        video_path = camera_dir / "test.mkv"
        video_path.write_bytes(b"x" * 2048)

        await file_watcher._process_file(str(video_path))

        call_args = mock_redis_client.add_to_queue_safe.call_args
        data = call_args[0][1]
        assert data["media_type"] == "video"

    @pytest.mark.asyncio
    async def test_process_invalid_video_file(
        self, file_watcher, temp_camera_root: Path, mock_redis_client: AsyncMock
    ) -> None:
        """Test processing an invalid (too small) video file."""
        camera_dir = temp_camera_root / "camera1"
        video_path = camera_dir / "invalid.mp4"
        video_path.write_bytes(b"x" * 100)  # Too small

        await file_watcher._process_file(str(video_path))

        # Should not queue invalid videos
        mock_redis_client.add_to_queue_safe.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_queue_includes_media_type(
        self, file_watcher, temp_camera_root: Path, mock_redis_client: AsyncMock
    ) -> None:
        """Test that queue data includes media_type for images too."""
        from PIL import Image

        camera_dir = temp_camera_root / "camera1"
        image_path = camera_dir / "test.jpg"
        # Create a valid image above minimum size (>10KB)
        size = (640, 480)
        img = Image.new("RGB", size, color="blue")
        pixels = img.load()
        if pixels is not None:
            for y in range(size[1]):
                for x in range(size[0]):
                    pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
        img.save(image_path, "JPEG", quality=95)

        await file_watcher._process_file(str(image_path))

        call_args = mock_redis_client.add_to_queue_safe.call_args
        data = call_args[0][1]
        assert data["media_type"] == "image"

    @pytest.mark.asyncio
    async def test_event_handler_triggers_on_video(
        self, file_watcher, temp_camera_root: Path
    ) -> None:
        """Test event handler responds to video file creation."""
        camera_dir = temp_camera_root / "camera1"
        video_path = camera_dir / "new_video.mp4"
        video_path.write_bytes(b"x" * 2048)

        from watchdog.events import FileCreatedEvent

        event = FileCreatedEvent(str(video_path))

        with patch.object(file_watcher._event_handler, "_schedule_async_task") as mock_schedule:
            file_watcher._event_handler.on_created(event)
            mock_schedule.assert_called_once_with(str(video_path))


# =============================================================================
# Video Processor Tests
# =============================================================================


class TestVideoProcessor:
    """Test VideoProcessor service."""

    @pytest.fixture
    def video_processor(self, tmp_path: Path):
        """Create VideoProcessor instance with temp output directory."""
        from backend.services.video_processor import VideoProcessor

        output_dir = tmp_path / "thumbnails"
        return VideoProcessor(output_dir=str(output_dir))

    def test_output_dir_created(self, tmp_path: Path) -> None:
        """Test that output directory is created on initialization."""
        from backend.services.video_processor import VideoProcessor

        output_dir = tmp_path / "new_thumbnails"
        assert not output_dir.exists()

        VideoProcessor(output_dir=str(output_dir))
        assert output_dir.exists()

    def test_get_output_path(self, video_processor) -> None:
        """Test get_output_path returns correct path."""
        path = video_processor.get_output_path("123")
        assert path.name == "123_video_thumb.jpg"

    def test_get_mime_type(self, video_processor) -> None:
        """Test MIME type detection."""
        assert video_processor._get_mime_type("/path/to/video.mp4") == "video/mp4"
        assert video_processor._get_mime_type("/path/to/video.mkv") == "video/x-matroska"
        assert video_processor._get_mime_type("/path/to/video.avi") == "video/x-msvideo"
        assert video_processor._get_mime_type("/path/to/video.mov") == "video/quicktime"

    @pytest.mark.asyncio
    async def test_get_video_metadata_file_not_found(self, video_processor) -> None:
        """Test get_video_metadata raises error for missing file."""
        from backend.services.video_processor import VideoProcessingError

        with pytest.raises(VideoProcessingError, match="Video file not found"):
            await video_processor.get_video_metadata("/nonexistent/video.mp4")

    @pytest.mark.asyncio
    async def test_extract_thumbnail_file_not_found(self, video_processor) -> None:
        """Test extract_thumbnail returns None for missing file."""
        result = await video_processor.extract_thumbnail("/nonexistent/video.mp4")
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_frames_for_detection_file_not_found(self, video_processor) -> None:
        """Test extract_frames_for_detection returns empty list for missing file."""
        result = await video_processor.extract_frames_for_detection("/nonexistent/video.mp4")
        assert result == []

    def test_cleanup_extracted_frames_nonexistent(self, video_processor) -> None:
        """Test cleanup_extracted_frames returns False for nonexistent directory."""
        result = video_processor.cleanup_extracted_frames("/nonexistent/video.mp4")
        assert result is False

    def test_cleanup_extracted_frames_success(self, video_processor, tmp_path: Path) -> None:
        """Test cleanup_extracted_frames removes frames directory."""
        # Create a mock frames directory
        video_stem = "test_video"
        frames_dir = video_processor.output_dir / f"{video_stem}_frames"
        frames_dir.mkdir(parents=True)
        (frames_dir / "frame_0000.jpg").touch()

        result = video_processor.cleanup_extracted_frames(f"/path/to/{video_stem}.mp4")

        assert result is True
        assert not frames_dir.exists()


# =============================================================================
# Range Header Parsing Tests
# =============================================================================


class TestRangeHeaderParsing:
    """Test HTTP Range header parsing."""

    def test_parse_range_explicit(self) -> None:
        """Test parsing explicit range (e.g., bytes=0-1023)."""
        from backend.api.routes.detections import _parse_range_header

        start, end = _parse_range_header("bytes=0-1023", 10000)
        assert start == 0
        assert end == 1023

    def test_parse_range_open_ended(self) -> None:
        """Test parsing open-ended range (e.g., bytes=500-)."""
        from backend.api.routes.detections import _parse_range_header

        start, end = _parse_range_header("bytes=500-", 10000)
        assert start == 500
        assert end == 9999

    def test_parse_range_suffix(self) -> None:
        """Test parsing suffix range (e.g., bytes=-500)."""
        from backend.api.routes.detections import _parse_range_header

        start, end = _parse_range_header("bytes=-500", 10000)
        assert start == 9500
        assert end == 9999

    def test_parse_range_clamps_to_file_size(self) -> None:
        """Test that range is clamped to file size."""
        from backend.api.routes.detections import _parse_range_header

        start, end = _parse_range_header("bytes=0-50000", 10000)
        assert start == 0
        assert end == 9999

    def test_parse_range_invalid_format(self) -> None:
        """Test that invalid format raises ValueError."""
        from backend.api.routes.detections import _parse_range_header

        with pytest.raises(ValueError, match="Invalid range header format"):
            _parse_range_header("invalid=0-100", 10000)

    def test_parse_range_invalid_start_greater_than_end(self) -> None:
        """Test that start > end raises ValueError."""
        from backend.api.routes.detections import _parse_range_header

        with pytest.raises(ValueError, match="Invalid range"):
            _parse_range_header("bytes=5000-100", 10000)


# =============================================================================
# Video Streaming Endpoint Tests
# =============================================================================


class TestVideoStreamingEndpoint:
    """Test video streaming API endpoint."""

    @pytest.fixture
    def mock_detection_video(self) -> MagicMock:
        """Create a mock video Detection object."""
        from backend.models.detection import Detection

        detection = MagicMock(spec=Detection)
        detection.id = 1
        detection.camera_id = "camera-001"
        detection.file_path = "/export/foscam/front_door/20251223_120000.mp4"
        detection.file_type = "video/mp4"
        detection.media_type = "video"
        detection.thumbnail_path = None
        return detection

    @pytest.fixture
    def mock_detection_image(self) -> MagicMock:
        """Create a mock image Detection object."""
        from backend.models.detection import Detection

        detection = MagicMock(spec=Detection)
        detection.id = 2
        detection.media_type = "image"
        return detection

    @pytest.fixture
    def mock_db_session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_stream_video_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test streaming video when detection doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes import detections as detections_routes

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await detections_routes.stream_detection_video(
                detection_id=999, range_header=None, db=mock_db_session
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_video_not_video_type(
        self, mock_db_session: AsyncMock, mock_detection_image: MagicMock
    ) -> None:
        """Test streaming video when detection is not a video."""
        from fastapi import HTTPException

        from backend.api.routes import detections as detections_routes

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection_image
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await detections_routes.stream_detection_video(
                detection_id=2, range_header=None, db=mock_db_session
            )

        assert exc_info.value.status_code == 400
        assert "not a video" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_stream_video_file_not_found(
        self, mock_db_session: AsyncMock, mock_detection_video: MagicMock
    ) -> None:
        """Test streaming video when file doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes import detections as detections_routes

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection_video
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("os.path.exists", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await detections_routes.stream_detection_video(
                detection_id=1, range_header=None, db=mock_db_session
            )

        assert exc_info.value.status_code == 404
        assert "Video file not found" in exc_info.value.detail


# =============================================================================
# Video Thumbnail Endpoint Tests
# =============================================================================


class TestVideoThumbnailEndpoint:
    """Test video thumbnail API endpoint."""

    @pytest.fixture
    def mock_detection_video(self) -> MagicMock:
        """Create a mock video Detection object."""
        from backend.models.detection import Detection

        detection = MagicMock(spec=Detection)
        detection.id = 1
        detection.camera_id = "camera-001"
        detection.file_path = "/export/foscam/front_door/20251223_120000.mp4"
        detection.file_type = "video/mp4"
        detection.media_type = "video"
        detection.thumbnail_path = None
        return detection

    @pytest.fixture
    def mock_db_session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test getting thumbnail when detection doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes import detections as detections_routes

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await detections_routes.get_video_thumbnail(detection_id=999, db=mock_db_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_not_video(self, mock_db_session: AsyncMock) -> None:
        """Test getting thumbnail when detection is not a video."""
        from fastapi import HTTPException

        from backend.api.routes import detections as detections_routes
        from backend.models.detection import Detection

        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.media_type = "image"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await detections_routes.get_video_thumbnail(detection_id=1, db=mock_db_session)

        assert exc_info.value.status_code == 400
        assert "not a video" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_with_existing(
        self, mock_db_session: AsyncMock, mock_detection_video: MagicMock
    ) -> None:
        """Test getting thumbnail when it already exists."""
        from unittest.mock import mock_open

        from backend.api.routes import detections as detections_routes

        mock_detection_video.thumbnail_path = "/data/thumbnails/1_video_thumb.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection_video
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        image_data = b"\xff\xd8\xff\xe0fake_jpeg_data"

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=image_data)),
        ):
            result = await detections_routes.get_video_thumbnail(detection_id=1, db=mock_db_session)

        assert result.status_code == 200
        assert result.media_type == "image/jpeg"
        assert result.body == image_data
