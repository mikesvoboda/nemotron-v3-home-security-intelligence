"""Unit tests for the video transcoding service.

This module provides comprehensive tests for the transcoding.py module,
covering:
- TranscodingService initialization and directory creation
- FFmpeg availability checking
- Video info extraction via FFprobe
- Video transcoding to browser-compatible MP4 format
- Input validation and security checks
- Error handling paths
- Singleton pattern for module-level access

All subprocess calls to FFmpeg/FFprobe are mocked.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.transcoding import (
    QUALITY_PRESETS,
    TranscodingError,
    TranscodingService,
    _validate_input_path,
    _validate_output_filename,
    _validate_quality_preset,
    get_transcoding_service,
    reset_transcoding_service,
)

# =============================================================================
# Validation Function Tests
# =============================================================================


class TestValidateInputPath:
    """Tests for _validate_input_path function."""

    def test_rejects_nonexistent_file(self) -> None:
        """Test that nonexistent files are rejected."""
        with pytest.raises(ValueError, match="Input video file not found"):
            _validate_input_path("/nonexistent/video.mp4")

    def test_rejects_directory(self, tmp_path: Path) -> None:
        """Test that directories are rejected."""
        with pytest.raises(ValueError, match="Input path is not a file"):
            _validate_input_path(str(tmp_path))

    def test_rejects_dash_prefix(self) -> None:
        """Test that paths starting with dash are rejected."""
        with pytest.raises(ValueError, match="Input video file not found"):
            _validate_input_path("-malicious.mp4")

    def test_accepts_valid_file(self, tmp_path: Path) -> None:
        """Test that valid files are accepted."""
        video_file = tmp_path / "test.mkv"
        video_file.write_bytes(b"fake video content")
        result = _validate_input_path(str(video_file))
        assert result == video_file.resolve()

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        """Test that Path objects are accepted."""
        video_file = tmp_path / "test.avi"
        video_file.write_bytes(b"fake video")
        result = _validate_input_path(video_file)
        assert result == video_file.resolve()


class TestValidateOutputFilename:
    """Tests for _validate_output_filename function."""

    def test_rejects_empty_filename(self) -> None:
        """Test that empty filenames are rejected."""
        with pytest.raises(ValueError, match="Output filename cannot be empty"):
            _validate_output_filename("")

    def test_rejects_path_separators(self) -> None:
        """Test that path separators in filename are rejected."""
        with pytest.raises(ValueError, match="cannot contain path separators"):
            _validate_output_filename("path/to/file.mp4")
        with pytest.raises(ValueError, match="cannot contain path separators"):
            _validate_output_filename("path\\to\\file.mp4")

    def test_rejects_dash_prefix(self) -> None:
        """Test that filenames starting with dash are rejected."""
        with pytest.raises(ValueError, match="Invalid output filename"):
            _validate_output_filename("-output.mp4")

    def test_accepts_valid_filename(self) -> None:
        """Test that valid filenames are accepted."""
        result = _validate_output_filename("output.mp4")
        assert result == "output.mp4"

    def test_adds_mp4_extension(self) -> None:
        """Test that .mp4 extension is added if missing."""
        result = _validate_output_filename("output")
        assert result == "output.mp4"
        result = _validate_output_filename("video_transcoded")
        assert result == "video_transcoded.mp4"

    def test_preserves_mp4_extension(self) -> None:
        """Test that .mp4 extension is not duplicated."""
        result = _validate_output_filename("output.mp4")
        assert result == "output.mp4"
        result = _validate_output_filename("output.MP4")
        assert result == "output.MP4"


class TestValidateQualityPreset:
    """Tests for _validate_quality_preset function."""

    def test_rejects_invalid_preset(self) -> None:
        """Test that invalid presets are rejected."""
        with pytest.raises(ValueError, match="Invalid quality preset"):
            _validate_quality_preset("ultra")
        with pytest.raises(ValueError, match="Invalid quality preset"):
            _validate_quality_preset("best")

    def test_accepts_valid_presets(self) -> None:
        """Test that valid presets are accepted."""
        assert _validate_quality_preset("high") == "high"
        assert _validate_quality_preset("medium") == "medium"
        assert _validate_quality_preset("low") == "low"

    def test_normalizes_case(self) -> None:
        """Test that presets are normalized to lowercase."""
        assert _validate_quality_preset("HIGH") == "high"
        assert _validate_quality_preset("Medium") == "medium"
        assert _validate_quality_preset("LOW") == "low"

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        assert _validate_quality_preset("  high  ") == "high"
        assert _validate_quality_preset("\tmedium\n") == "medium"


# =============================================================================
# TranscodingService Initialization Tests
# =============================================================================


class TestTranscodingServiceInit:
    """Tests for TranscodingService initialization."""

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        """Test that output directory is created on initialization."""
        output_dir = tmp_path / "new_transcoded"
        assert not output_dir.exists()

        service = TranscodingService(output_dir=str(output_dir))

        assert output_dir.exists()
        assert service.output_dir == output_dir

    def test_uses_existing_directory(self, tmp_path: Path) -> None:
        """Test initialization with existing directory."""
        output_dir = tmp_path / "existing"
        output_dir.mkdir()

        service = TranscodingService(output_dir=str(output_dir))

        assert service.output_dir == output_dir

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        """Test initialization with Path object."""
        output_dir = tmp_path / "path_object"

        service = TranscodingService(output_dir=output_dir)

        assert service.output_dir == output_dir
        assert output_dir.exists()

    def test_directory_creation_error(self, tmp_path: Path) -> None:
        """Test error handling when directory creation fails."""
        with (
            patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")),
            pytest.raises(PermissionError),
        ):
            TranscodingService(output_dir=str(tmp_path / "no_permission"))


# =============================================================================
# FFmpeg Availability Tests
# =============================================================================


class TestCheckFFmpegAvailable:
    """Tests for FFmpeg availability checking."""

    def test_ffmpeg_available(self, tmp_path: Path) -> None:
        """Test when FFmpeg is available."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            service = TranscodingService(output_dir=str(tmp_path))
            result = service.check_ffmpeg_available()

        assert result is True

    def test_ffmpeg_not_found(self, tmp_path: Path) -> None:
        """Test when FFmpeg is not installed."""
        service = TranscodingService(output_dir=str(tmp_path))
        service._ffmpeg_available = None  # Reset cache

        with patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
            result = service.check_ffmpeg_available()

        assert result is False

    def test_ffmpeg_timeout(self, tmp_path: Path) -> None:
        """Test when FFmpeg check times out."""
        service = TranscodingService(output_dir=str(tmp_path))
        service._ffmpeg_available = None

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 5)):
            result = service.check_ffmpeg_available()

        assert result is False

    def test_ffmpeg_nonzero_exit(self, tmp_path: Path) -> None:
        """Test when FFmpeg returns non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        service = TranscodingService(output_dir=str(tmp_path))
        service._ffmpeg_available = None

        with patch("subprocess.run", return_value=mock_result):
            result = service.check_ffmpeg_available()

        assert result is False

    def test_caches_result(self, tmp_path: Path) -> None:
        """Test that availability check result is cached."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            service = TranscodingService(output_dir=str(tmp_path))

            result1 = service.check_ffmpeg_available()
            result2 = service.check_ffmpeg_available()

        assert result1 is True
        assert result2 is True
        # Should only be called once due to caching
        assert mock_run.call_count == 1

    def test_unexpected_error(self, tmp_path: Path) -> None:
        """Test handling of unexpected errors."""
        service = TranscodingService(output_dir=str(tmp_path))
        service._ffmpeg_available = None

        with patch("subprocess.run", side_effect=RuntimeError("Unexpected")):
            result = service.check_ffmpeg_available()

        assert result is False


# =============================================================================
# Video Info Extraction Tests
# =============================================================================


class TestGetVideoInfo:
    """Tests for video info extraction via FFprobe."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> TranscodingService:
        """Create TranscodingService instance."""
        return TranscodingService(output_dir=str(tmp_path))

    @pytest.fixture
    def sample_ffprobe_output(self) -> dict:
        """Sample FFprobe JSON output."""
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
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
            },
        }

    @pytest.mark.asyncio
    async def test_returns_video_info(
        self, service: TranscodingService, tmp_path: Path, sample_ffprobe_output: dict
    ) -> None:
        """Test successful video info extraction."""
        video_path = tmp_path / "test.mkv"
        video_path.write_bytes(b"fake video")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(sample_ffprobe_output)

        with patch("asyncio.to_thread", return_value=mock_result):
            info = await service.get_video_info(str(video_path))

        assert info is not None
        assert info["duration"] == 120.5
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["video_codec"] == "hevc"
        assert info["audio_codec"] == "aac"
        assert info["has_audio"] is True

    @pytest.mark.asyncio
    async def test_video_without_audio(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test video info extraction for video without audio."""
        video_path = tmp_path / "silent.mkv"
        video_path.write_bytes(b"fake video")

        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 640,
                    "height": 480,
                },
            ],
            "format": {"duration": "30.0"},
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)

        with patch("asyncio.to_thread", return_value=mock_result):
            info = await service.get_video_info(str(video_path))

        assert info is not None
        assert info["audio_codec"] is None
        assert info["has_audio"] is False

    @pytest.mark.asyncio
    async def test_invalid_path(self, service: TranscodingService) -> None:
        """Test video info extraction with invalid path."""
        info = await service.get_video_info("/nonexistent/video.mp4")
        assert info is None

    @pytest.mark.asyncio
    async def test_ffprobe_failure(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test handling of FFprobe failure."""
        video_path = tmp_path / "test.mkv"
        video_path.write_bytes(b"fake video")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "FFprobe error"

        with patch("asyncio.to_thread", return_value=mock_result):
            info = await service.get_video_info(str(video_path))

        assert info is None

    @pytest.mark.asyncio
    async def test_no_video_stream(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test handling of file with no video stream."""
        video_path = tmp_path / "audio_only.mp3"
        video_path.write_bytes(b"fake audio")

        ffprobe_output = {
            "streams": [
                {"codec_type": "audio", "codec_name": "mp3"},
            ],
            "format": {"duration": "180.0"},
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)

        with patch("asyncio.to_thread", return_value=mock_result):
            info = await service.get_video_info(str(video_path))

        assert info is None

    @pytest.mark.asyncio
    async def test_json_decode_error(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test handling of invalid JSON from FFprobe."""
        video_path = tmp_path / "test.mkv"
        video_path.write_bytes(b"fake video")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json{"

        with patch("asyncio.to_thread", return_value=mock_result):
            info = await service.get_video_info(str(video_path))

        assert info is None

    @pytest.mark.asyncio
    async def test_ffprobe_timeout(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test handling of FFprobe timeout."""
        video_path = tmp_path / "test.mkv"
        video_path.write_bytes(b"fake video")

        with patch(
            "asyncio.to_thread",
            side_effect=subprocess.TimeoutExpired("ffprobe", 30),
        ):
            info = await service.get_video_info(str(video_path))

        assert info is None

    @pytest.mark.asyncio
    async def test_unexpected_error(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test handling of unexpected errors."""
        video_path = tmp_path / "test.mkv"
        video_path.write_bytes(b"fake video")

        with patch("asyncio.to_thread", side_effect=RuntimeError("Unexpected")):
            info = await service.get_video_info(str(video_path))

        assert info is None


# =============================================================================
# Transcoding Tests
# =============================================================================


class TestTranscodeToMp4:
    """Tests for transcode_to_mp4 method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> TranscodingService:
        """Create TranscodingService instance with mocked FFmpeg check."""
        service = TranscodingService(output_dir=str(tmp_path))
        service._ffmpeg_available = True
        return service

    @pytest.mark.asyncio
    async def test_successful_transcoding(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test successful video transcoding."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video content")

        output_path = service.output_dir / "output.mp4"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
            patch.object(service, "get_video_info", return_value=None),
        ):
            # Create the output file to simulate FFmpeg success
            output_path.write_bytes(b"transcoded video")

            result = await service.transcode_to_mp4(
                input_path=str(input_path),
                output_filename="output.mp4",
            )

        assert result == output_path

    @pytest.mark.asyncio
    async def test_transcoding_with_quality_presets(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test transcoding with different quality presets."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        for preset in ["high", "medium", "low"]:
            output_path = service.output_dir / f"output_{preset}.mp4"

            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"", b""))

            async def mock_wait_for(coro, timeout):
                return await coro

            with (
                patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec,
                patch("asyncio.wait_for", side_effect=mock_wait_for),
                patch.object(service, "get_video_info", return_value=None),
            ):
                output_path.write_bytes(b"transcoded")

                await service.transcode_to_mp4(
                    input_path=str(input_path),
                    output_filename=f"output_{preset}.mp4",
                    quality_preset=preset,  # type: ignore[arg-type]
                )

                # Verify FFmpeg was called with video encoding and audio settings
                # Video encoding args come from get_video_encoder_args() (NEM-2682)
                # Audio bitrate comes from QUALITY_PRESETS
                call_args = mock_exec.call_args[0]
                assert "-c:v" in call_args
                assert "-c:a" in call_args
                assert "aac" in call_args
                assert "-b:a" in call_args
                assert str(QUALITY_PRESETS[preset]["audio_bitrate"]) in call_args

    @pytest.mark.asyncio
    async def test_auto_generated_output_filename(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test automatic output filename generation."""
        input_path = tmp_path / "my_video.mkv"
        input_path.write_bytes(b"fake video")

        expected_output = service.output_dir / "my_video_transcoded.mp4"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
            patch.object(service, "get_video_info", return_value=None),
        ):
            expected_output.write_bytes(b"transcoded")

            result = await service.transcode_to_mp4(input_path=str(input_path))

        assert result == expected_output

    @pytest.mark.asyncio
    async def test_invalid_input_path(self, service: TranscodingService) -> None:
        """Test transcoding with invalid input path."""
        with pytest.raises(TranscodingError, match="Input video file not found"):
            await service.transcode_to_mp4(input_path="/nonexistent/video.mkv")

    @pytest.mark.asyncio
    async def test_invalid_quality_preset(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test transcoding with invalid quality preset."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        with pytest.raises(TranscodingError, match="Invalid quality preset"):
            await service.transcode_to_mp4(
                input_path=str(input_path),
                quality_preset="ultra",  # type: ignore[arg-type]
            )

    @pytest.mark.asyncio
    async def test_invalid_output_filename(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test transcoding with invalid output filename."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        with pytest.raises(TranscodingError, match="cannot contain path separators"):
            await service.transcode_to_mp4(
                input_path=str(input_path),
                output_filename="path/to/output.mp4",
            )

    @pytest.mark.asyncio
    async def test_ffmpeg_not_available(self, tmp_path: Path) -> None:
        """Test transcoding when FFmpeg is not available."""
        service = TranscodingService(output_dir=str(tmp_path))
        service._ffmpeg_available = False

        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        with pytest.raises(TranscodingError, match="FFmpeg is not available"):
            await service.transcode_to_mp4(input_path=str(input_path))

    @pytest.mark.asyncio
    async def test_ffmpeg_execution_error(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test handling of FFmpeg execution error."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error: Invalid input format"))

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
            patch.object(service, "get_video_info", return_value=None),
            pytest.raises(TranscodingError, match="FFmpeg transcoding failed"),
        ):
            await service.transcode_to_mp4(input_path=str(input_path))

    @pytest.mark.asyncio
    async def test_transcoding_timeout(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test handling of transcoding timeout."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        mock_process = AsyncMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=TimeoutError()),
            patch.object(service, "get_video_info", return_value=None),
            pytest.raises(TranscodingError, match="timed out"),
        ):
            await service.transcode_to_mp4(
                input_path=str(input_path),
                timeout=10,
            )

    @pytest.mark.asyncio
    async def test_output_file_not_created(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test error when FFmpeg succeeds but output file not created."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
            patch.object(service, "get_video_info", return_value=None),
            pytest.raises(TranscodingError, match="was not created"),
        ):
            # Don't create the output file
            await service.transcode_to_mp4(input_path=str(input_path))

    @pytest.mark.asyncio
    async def test_ffmpeg_not_found_error(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test handling of FFmpeg executable not found."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        with (
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("ffmpeg not found"),
            ),
            patch.object(service, "get_video_info", return_value=None),
            pytest.raises(TranscodingError, match="FFmpeg executable not found"),
        ):
            await service.transcode_to_mp4(input_path=str(input_path))

    @pytest.mark.asyncio
    async def test_unexpected_error(self, service: TranscodingService, tmp_path: Path) -> None:
        """Test handling of unexpected errors during transcoding."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        with (
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=RuntimeError("Unexpected error"),
            ),
            patch.object(service, "get_video_info", return_value=None),
            pytest.raises(TranscodingError, match="Unexpected error"),
        ):
            await service.transcode_to_mp4(input_path=str(input_path))

    @pytest.mark.asyncio
    async def test_with_video_info_logging(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test transcoding with video info for logging."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        output_path = service.output_dir / "output.mp4"

        video_info = {
            "duration": 120.0,
            "width": 1920,
            "height": 1080,
            "video_codec": "hevc",
        }

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
            patch.object(service, "get_video_info", return_value=video_info),
        ):
            output_path.write_bytes(b"transcoded")

            result = await service.transcode_to_mp4(
                input_path=str(input_path),
                output_filename="output.mp4",
            )

        assert result == output_path


# =============================================================================
# Utility Methods Tests
# =============================================================================


class TestUtilityMethods:
    """Tests for utility methods."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> TranscodingService:
        """Create TranscodingService instance."""
        return TranscodingService(output_dir=str(tmp_path))

    def test_get_output_path(self, service: TranscodingService) -> None:
        """Test get_output_path returns correct path."""
        path = service.get_output_path("test.mp4")
        assert path == service.output_dir / "test.mp4"

    def test_delete_transcoded_file_success(self, service: TranscodingService) -> None:
        """Test successful file deletion."""
        # Create a file
        file_path = service.output_dir / "to_delete.mp4"
        file_path.write_bytes(b"transcoded video")

        result = service.delete_transcoded_file("to_delete.mp4")

        assert result is True
        assert not file_path.exists()

    def test_delete_transcoded_file_not_found(self, service: TranscodingService) -> None:
        """Test deletion of nonexistent file."""
        result = service.delete_transcoded_file("nonexistent.mp4")
        assert result is False

    def test_delete_transcoded_file_error(self, service: TranscodingService) -> None:
        """Test error handling during file deletion."""
        # Create a file
        file_path = service.output_dir / "protected.mp4"
        file_path.write_bytes(b"transcoded video")

        with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
            result = service.delete_transcoded_file("protected.mp4")

        assert result is False


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


class TestSingletonPattern:
    """Tests for module-level singleton pattern."""

    def test_get_transcoding_service_returns_singleton(self) -> None:
        """Test that get_transcoding_service returns same instance."""
        reset_transcoding_service()

        service1 = get_transcoding_service()
        service2 = get_transcoding_service()

        assert service1 is service2

        reset_transcoding_service()

    def test_reset_transcoding_service(self) -> None:
        """Test that reset creates new instance."""
        reset_transcoding_service()

        service1 = get_transcoding_service()
        reset_transcoding_service()
        service2 = get_transcoding_service()

        assert service1 is not service2

        reset_transcoding_service()


# =============================================================================
# Quality Presets Tests
# =============================================================================


class TestQualityPresets:
    """Tests for quality preset configuration."""

    def test_all_presets_have_required_keys(self) -> None:
        """Test that all presets have required configuration keys."""
        required_keys = {"crf", "preset", "audio_bitrate"}

        for preset_name, config in QUALITY_PRESETS.items():
            assert required_keys.issubset(config.keys()), (
                f"Preset '{preset_name}' missing keys: {required_keys - set(config.keys())}"
            )

    def test_crf_values_are_valid(self) -> None:
        """Test that CRF values are in valid range (0-51)."""
        for preset_name, config in QUALITY_PRESETS.items():
            crf = config["crf"]
            assert 0 <= crf <= 51, f"Preset '{preset_name}' has invalid CRF: {crf}"

    def test_presets_ordered_by_quality(self) -> None:
        """Test that presets are ordered correctly by quality (lower CRF = better)."""
        assert QUALITY_PRESETS["high"]["crf"] < QUALITY_PRESETS["medium"]["crf"]
        assert QUALITY_PRESETS["medium"]["crf"] < QUALITY_PRESETS["low"]["crf"]


# =============================================================================
# Integration Tests
# =============================================================================


class TestTranscodingIntegration:
    """Integration-style tests combining multiple components."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> TranscodingService:
        """Create TranscodingService instance."""
        service = TranscodingService(output_dir=str(tmp_path))
        service._ffmpeg_available = True
        return service

    @pytest.mark.asyncio
    async def test_full_transcoding_workflow(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """Test complete transcoding workflow."""
        # Create input file
        input_path = tmp_path / "source_video.mkv"
        input_path.write_bytes(b"source video content")

        output_filename = "transcoded_video.mp4"
        output_path = service.output_dir / output_filename

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
            patch.object(
                service,
                "get_video_info",
                return_value={
                    "duration": 60.0,
                    "width": 1280,
                    "height": 720,
                    "video_codec": "vp9",
                },
            ),
        ):
            output_path.write_bytes(b"transcoded content")

            result = await service.transcode_to_mp4(
                input_path=str(input_path),
                output_filename=output_filename,
                quality_preset="medium",
            )

        # Verify output
        assert result == output_path
        assert result.exists()

        # Test deletion
        deleted = service.delete_transcoded_file(output_filename)
        assert deleted is True
        assert not output_path.exists()

    @pytest.mark.asyncio
    async def test_transcoding_preserves_directory_structure(self, tmp_path: Path) -> None:
        """Test that transcoding respects output directory configuration."""
        custom_output_dir = tmp_path / "custom" / "transcoded" / "videos"
        service = TranscodingService(output_dir=str(custom_output_dir))
        service._ffmpeg_available = True

        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"video")

        output_path = custom_output_dir / "output.mp4"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
            patch.object(service, "get_video_info", return_value=None),
        ):
            output_path.write_bytes(b"transcoded")

            result = await service.transcode_to_mp4(
                input_path=str(input_path),
                output_filename="output.mp4",
            )

        assert result.parent == custom_output_dir
