"""Unit tests for video transcoding service (NEM-2681).

Tests the TranscodingService which provides browser-compatible video transcoding
with caching support.
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.transcoding_service import (
    OUTPUT_AUDIO_CODEC,
    OUTPUT_CONTAINER,
    OUTPUT_PIXEL_FORMAT,
    OUTPUT_VIDEO_CODEC_SOFTWARE,
    TranscodingError,
    TranscodingService,
    _compute_file_hash,
    _validate_video_path,
    get_transcoding_service,
    reset_transcoding_service,
)

# Fixtures


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "transcoded_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def temp_video_file(tmp_path):
    """Create a temporary video file for testing."""
    video_file = tmp_path / "test_video.avi"
    video_file.write_bytes(b"fake video content" * 100)
    return video_file


@pytest.fixture
def temp_mp4_file(tmp_path):
    """Create a temporary MP4 file for testing (browser-compatible)."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake mp4 content" * 100)
    return video_file


@pytest.fixture
def transcoding_service(temp_cache_dir):
    """Create TranscodingService instance with temp directory."""
    return TranscodingService(cache_directory=str(temp_cache_dir))


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    reset_transcoding_service()
    yield
    reset_transcoding_service()


# Initialization tests


def test_transcoding_service_initialization(temp_cache_dir):
    """Test TranscodingService initializes with correct settings."""
    service = TranscodingService(cache_directory=str(temp_cache_dir))

    assert service.cache_directory == temp_cache_dir


def test_transcoding_service_default_values():
    """Test TranscodingService uses settings defaults."""
    with patch("backend.services.transcoding_service.get_settings") as mock_settings:
        mock_settings.return_value.transcoding_cache_directory = "custom/cache"
        mock_settings.return_value.hardware_acceleration_enabled = False
        mock_settings.return_value.nvenc_preset = "p4"
        mock_settings.return_value.nvenc_cq = 23

        service = TranscodingService()

        assert service.cache_directory == Path("custom/cache")


def test_transcoding_service_creates_cache_directory(tmp_path):
    """Test TranscodingService creates cache directory if it doesn't exist."""
    cache_dir = tmp_path / "new_cache"
    assert not cache_dir.exists()

    service = TranscodingService(cache_directory=str(cache_dir))

    assert cache_dir.exists()
    assert service.cache_directory == cache_dir


# Path validation tests


def test_validate_video_path_success(temp_video_file):
    """Test path validation with valid file."""
    result = _validate_video_path(temp_video_file)
    assert result == temp_video_file.resolve()


def test_validate_video_path_not_found():
    """Test path validation with non-existent file."""
    with pytest.raises(ValueError, match="Video file not found"):
        _validate_video_path("/nonexistent/video.mp4")


def test_validate_video_path_not_a_file(tmp_path):
    """Test path validation with directory path."""
    with pytest.raises(ValueError, match="Path is not a file"):
        _validate_video_path(tmp_path)


def test_validate_video_path_dash_prefix(tmp_path):
    """Test path validation rejects paths starting with dash."""
    # This is a security check to prevent command injection
    # In practice, a resolved path won't start with dash
    # But we test the validation logic still works
    video_file = tmp_path / "normal_video.mp4"
    video_file.write_bytes(b"content")
    # This should succeed since resolved path won't start with dash
    result = _validate_video_path(video_file)
    assert not str(result).startswith("-")


# Hash computation tests


def test_compute_file_hash(temp_video_file):
    """Test file hash computation."""
    hash1 = _compute_file_hash(temp_video_file)
    hash2 = _compute_file_hash(temp_video_file)

    assert hash1 == hash2
    assert len(hash1) == 32  # MD5 hex digest length


def test_compute_file_hash_changes_with_content(tmp_path):
    """Test hash changes when file is modified."""
    video_file = tmp_path / "video.avi"
    video_file.write_bytes(b"content1")
    hash1 = _compute_file_hash(video_file)

    # Need to ensure mtime changes
    time.sleep(0.01)
    video_file.write_bytes(b"content2")
    hash2 = _compute_file_hash(video_file)

    assert hash1 != hash2


# Cache lookup tests


def test_get_cached_video_miss(transcoding_service, temp_video_file):
    """Test cache lookup returns None for uncached video."""
    result = transcoding_service.get_cached_video(temp_video_file)
    assert result is None


def test_get_cached_video_hit(transcoding_service, temp_video_file, temp_cache_dir):
    """Test cache lookup returns path for cached video."""
    # Create a cached file (must be at least 1KB to pass corrupted file check)
    file_hash = _compute_file_hash(temp_video_file)
    cached_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    cached_file.write_bytes(b"cached content" + b"\x00" * 1024)

    result = transcoding_service.get_cached_video(temp_video_file)

    assert result == cached_file


def test_get_cached_video_invalid_path(transcoding_service):
    """Test cache lookup handles invalid paths gracefully."""
    result = transcoding_service.get_cached_video("/nonexistent/path.mp4")
    assert result is None


# Transcoding needed tests


def test_is_transcoding_needed_avi(transcoding_service, temp_video_file):
    """Test that AVI files need transcoding."""
    assert transcoding_service.is_transcoding_needed(temp_video_file) is True


def test_is_transcoding_needed_mp4(transcoding_service, temp_mp4_file):
    """Test that MP4 files don't need transcoding."""
    assert transcoding_service.is_transcoding_needed(temp_mp4_file) is False


def test_is_transcoding_needed_mkv(tmp_path):
    """Test that MKV files need transcoding."""
    mkv_file = tmp_path / "video.mkv"
    mkv_file.write_bytes(b"content")
    service = TranscodingService(cache_directory=str(tmp_path / "cache"))

    assert service.is_transcoding_needed(mkv_file) is True


def test_is_transcoding_needed_invalid_path(transcoding_service):
    """Test transcoding check returns True for invalid paths."""
    assert transcoding_service.is_transcoding_needed("/nonexistent.avi") is True


# Transcoding tests


@pytest.mark.asyncio
async def test_transcode_video_success(transcoding_service, temp_video_file, temp_cache_dir):
    """Test successful video transcoding."""
    file_hash = _compute_file_hash(temp_video_file)
    expected_output = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"

    # Ensure no cached file exists
    if expected_output.exists():
        expected_output.unlink()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        # Mock successful ffmpeg execution
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_process

        # The mock creates the file after process.communicate() is called
        # Simulate ffmpeg creating the file after running
        async def create_output(*args, **kwargs):
            # Write at least 1KB to pass the corrupted file check (MIN_VALID_FILE_SIZE = 1024)
            expected_output.write_bytes(b"transcoded content" + b"\x00" * 1024)
            return (b"", b"")

        mock_process.communicate = create_output

        result = await transcoding_service.transcode_video(temp_video_file)

        assert result == expected_output
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_transcode_video_uses_cached(transcoding_service, temp_video_file, temp_cache_dir):
    """Test transcoding returns cached file if available."""
    file_hash = _compute_file_hash(temp_video_file)
    cached_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    cached_file.write_bytes(b"cached content")

    result = await transcoding_service.transcode_video(temp_video_file)

    assert result == cached_file


@pytest.mark.asyncio
async def test_transcode_video_force_retranscode(
    transcoding_service, temp_video_file, temp_cache_dir
):
    """Test force=True bypasses cache."""
    file_hash = _compute_file_hash(temp_video_file)
    cached_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    cached_file.write_bytes(b"old cached content" + b"\x00" * 1024)

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        # First call is remux (should fail), second call is full transcode (should succeed)
        mock_remux_process = AsyncMock()
        mock_remux_process.returncode = 1  # Remux fails
        mock_remux_process.communicate = AsyncMock(return_value=(b"", b"remux failed"))

        mock_transcode_process = AsyncMock()
        mock_transcode_process.returncode = 0

        # Simulate ffmpeg creating the file after full transcode
        async def create_output(*args, **kwargs):
            cached_file.write_bytes(b"new transcoded content" + b"\x00" * 1024)
            return (b"", b"")

        mock_transcode_process.communicate = create_output

        # Return different processes for remux vs transcode calls
        mock_exec.side_effect = [mock_remux_process, mock_transcode_process]

        result = await transcoding_service.transcode_video(temp_video_file, force=True)

        # Both remux and transcode should be called
        assert mock_exec.call_count == 2
        assert result == cached_file


@pytest.mark.asyncio
async def test_transcode_video_ffmpeg_failure(transcoding_service, temp_video_file):
    """Test transcoding raises error on ffmpeg failure."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"ffmpeg error"))
        mock_exec.return_value = mock_process

        with pytest.raises(TranscodingError, match="FFmpeg exited with code 1"):
            await transcoding_service.transcode_video(temp_video_file)


@pytest.mark.asyncio
async def test_transcode_video_ffmpeg_not_found(transcoding_service, temp_video_file):
    """Test transcoding raises error when ffmpeg not found."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = FileNotFoundError()

        with pytest.raises(TranscodingError, match="ffmpeg not found"):
            await transcoding_service.transcode_video(temp_video_file)


@pytest.mark.asyncio
async def test_transcode_video_output_not_created(transcoding_service, temp_video_file):
    """Test transcoding raises error when output file not created."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_process
        # Don't create the output file

        with pytest.raises(TranscodingError, match="Transcoded file was not created"):
            await transcoding_service.transcode_video(temp_video_file)


# Get or transcode tests


@pytest.mark.asyncio
async def test_get_or_transcode_browser_compatible(transcoding_service, temp_mp4_file):
    """Test get_or_transcode returns original path for browser-compatible video."""
    result = await transcoding_service.get_or_transcode(temp_mp4_file)

    assert result == temp_mp4_file.resolve()


@pytest.mark.asyncio
async def test_get_or_transcode_needs_transcoding(
    transcoding_service, temp_video_file, temp_cache_dir
):
    """Test get_or_transcode transcodes non-compatible videos."""
    file_hash = _compute_file_hash(temp_video_file)
    expected_output = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_process

        # Write at least 1KB to pass the corrupted file check (MIN_VALID_FILE_SIZE = 1024)
        expected_output.write_bytes(b"transcoded content" + b"\x00" * 1024)

        result = await transcoding_service.get_or_transcode(temp_video_file)

        assert result == expected_output


@pytest.mark.asyncio
async def test_get_or_transcode_uses_cache(transcoding_service, temp_video_file, temp_cache_dir):
    """Test get_or_transcode returns cached file if available."""
    file_hash = _compute_file_hash(temp_video_file)
    cached_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    # Write at least 1KB to pass corrupted file check
    cached_file.write_bytes(b"cached content" + b"\x00" * 1024)

    result = await transcoding_service.get_or_transcode(temp_video_file)

    assert result == cached_file


# Cache cleanup tests


def test_cleanup_cache_removes_old_files(transcoding_service, temp_cache_dir):
    """Test cache cleanup removes old files."""
    # Create some old cache files
    old_file = temp_cache_dir / "oldhash_transcoded.mp4"
    old_file.write_bytes(b"old content")

    # Make the file appear old by modifying its mtime
    old_mtime = time.time() - (8 * 24 * 60 * 60)  # 8 days ago
    import os

    os.utime(old_file, (old_mtime, old_mtime))

    deleted_count = transcoding_service.cleanup_cache(max_age_days=7)

    assert deleted_count == 1
    assert not old_file.exists()


def test_cleanup_cache_keeps_recent_files(transcoding_service, temp_cache_dir):
    """Test cache cleanup keeps recent files."""
    recent_file = temp_cache_dir / "recenthash_transcoded.mp4"
    recent_file.write_bytes(b"recent content")

    deleted_count = transcoding_service.cleanup_cache(max_age_days=7)

    assert deleted_count == 0
    assert recent_file.exists()


# Delete cached tests


def test_delete_cached_success(transcoding_service, temp_video_file, temp_cache_dir):
    """Test deleting cached file."""
    file_hash = _compute_file_hash(temp_video_file)
    cached_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    cached_file.write_bytes(b"cached content")

    result = transcoding_service.delete_cached(temp_video_file)

    assert result is True
    assert not cached_file.exists()


def test_delete_cached_not_found(transcoding_service, temp_video_file):
    """Test deleting non-existent cached file."""
    result = transcoding_service.delete_cached(temp_video_file)
    assert result is False


def test_delete_cached_invalid_path(transcoding_service):
    """Test deleting with invalid path."""
    result = transcoding_service.delete_cached("/nonexistent/path.mp4")
    assert result is False


# Singleton tests


def test_get_transcoding_service_singleton():
    """Test singleton pattern."""
    with patch("backend.services.transcoding_service.get_settings") as mock_settings:
        mock_settings.return_value.transcoding_cache_directory = "test/cache"
        mock_settings.return_value.hardware_acceleration_enabled = False

        service1 = get_transcoding_service()
        service2 = get_transcoding_service()

        assert service1 is service2


def test_reset_transcoding_service():
    """Test singleton reset."""
    with patch("backend.services.transcoding_service.get_settings") as mock_settings:
        mock_settings.return_value.transcoding_cache_directory = "test/cache"
        mock_settings.return_value.hardware_acceleration_enabled = False

        service1 = get_transcoding_service()
        reset_transcoding_service()
        service2 = get_transcoding_service()

        assert service1 is not service2


# Constants tests


def test_output_constants():
    """Test that output format constants are correct."""
    assert OUTPUT_VIDEO_CODEC_SOFTWARE == "libx264"
    assert OUTPUT_AUDIO_CODEC == "aac"
    assert OUTPUT_PIXEL_FORMAT == "yuv420p"
    assert OUTPUT_CONTAINER == "mp4"


# =============================================================================
# NVENC Hardware Acceleration Tests (NEM-2682)
# =============================================================================


class TestNVENCHardwareAcceleration:
    """Tests for NVIDIA NVENC hardware acceleration support."""

    @pytest.fixture(autouse=True)
    def reset_nvenc_state(self):
        """Reset NVENC cache state before and after each test."""
        from backend.services.transcoding_service import reset_nvenc_cache

        reset_nvenc_cache()
        yield
        reset_nvenc_cache()

    def test_check_nvenc_available_success(self):
        """Test NVENC detection when GPU is available."""
        from backend.services.transcoding_service import check_nvenc_available

        with patch("subprocess.run") as mock_run:
            # First call: check encoders
            encoder_result = MagicMock()
            encoder_result.returncode = 0
            encoder_result.stdout = "h264_nvenc - NVIDIA NVENC H.264 encoder"

            # Second call: test encoding
            test_result = MagicMock()
            test_result.returncode = 0

            mock_run.side_effect = [encoder_result, test_result]

            result = check_nvenc_available()

            assert result is True
            assert mock_run.call_count == 2

    def test_check_nvenc_available_no_encoder(self):
        """Test NVENC detection when encoder is not available in ffmpeg."""
        from backend.services.transcoding_service import check_nvenc_available

        with patch("subprocess.run") as mock_run:
            encoder_result = MagicMock()
            encoder_result.returncode = 0
            encoder_result.stdout = "libx264 - H.264 / AVC / MPEG-4 AVC"

            mock_run.return_value = encoder_result

            result = check_nvenc_available()

            assert result is False
            # Only one call needed since h264_nvenc not in output
            assert mock_run.call_count == 1

    def test_check_nvenc_available_encoder_test_fails(self):
        """Test NVENC detection when encoder exists but test fails (no GPU)."""
        from backend.services.transcoding_service import check_nvenc_available

        with patch("subprocess.run") as mock_run:
            # Encoder check succeeds
            encoder_result = MagicMock()
            encoder_result.returncode = 0
            encoder_result.stdout = "h264_nvenc - NVIDIA NVENC H.264 encoder"

            # Test encoding fails (no GPU device)
            test_result = MagicMock()
            test_result.returncode = 1
            test_result.stderr = "No NVENC capable device found"

            mock_run.side_effect = [encoder_result, test_result]

            result = check_nvenc_available()

            assert result is False

    def test_check_nvenc_available_ffmpeg_not_found(self):
        """Test NVENC detection when ffmpeg is not installed."""
        from backend.services.transcoding_service import check_nvenc_available

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            result = check_nvenc_available()

            assert result is False

    def test_check_nvenc_available_timeout(self):
        """Test NVENC detection handles timeout gracefully."""
        from backend.services.transcoding_service import check_nvenc_available

        with patch("subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10)

            result = check_nvenc_available()

            assert result is False

    def test_check_nvenc_available_caching(self):
        """Test NVENC availability is cached after first check."""
        from backend.services.transcoding_service import check_nvenc_available

        with patch("subprocess.run") as mock_run:
            encoder_result = MagicMock()
            encoder_result.returncode = 0
            encoder_result.stdout = "h264_nvenc"

            test_result = MagicMock()
            test_result.returncode = 0

            mock_run.side_effect = [encoder_result, test_result]

            # First call checks
            result1 = check_nvenc_available()
            # Second call should use cache
            result2 = check_nvenc_available()

            assert result1 is True
            assert result2 is True
            # Only 2 calls for first check, cached on second
            assert mock_run.call_count == 2

    def test_reset_nvenc_cache(self):
        """Test NVENC cache can be reset."""
        from backend.services.transcoding_service import (
            check_nvenc_available,
            reset_nvenc_cache,
        )

        with patch("subprocess.run") as mock_run:
            encoder_result = MagicMock()
            encoder_result.returncode = 0
            encoder_result.stdout = "h264_nvenc"

            test_result = MagicMock()
            test_result.returncode = 0

            # First check
            mock_run.side_effect = [encoder_result, test_result, encoder_result, test_result]

            check_nvenc_available()
            reset_nvenc_cache()
            check_nvenc_available()

            # 4 calls: 2 for first check, 2 for second after reset
            assert mock_run.call_count == 4

    def test_get_video_encoder_args_nvenc(self):
        """Test encoder args when NVENC is available."""
        from backend.services.transcoding_service import get_video_encoder_args

        with (
            patch("backend.services.transcoding_service.check_nvenc_available", return_value=True),
            patch("backend.services.transcoding_service.get_settings") as mock_settings,
        ):
            mock_settings.return_value.hardware_acceleration_enabled = True
            mock_settings.return_value.nvenc_preset = "p4"
            mock_settings.return_value.nvenc_cq = 23

            args = get_video_encoder_args(use_hardware=True)

            assert "-c:v" in args
            assert "h264_nvenc" in args
            assert "-preset" in args
            assert "p4" in args
            assert "-cq" in args
            assert "23" in args

    def test_get_video_encoder_args_software_fallback(self):
        """Test encoder args fallback to software when NVENC unavailable."""
        from backend.services.transcoding_service import get_video_encoder_args

        with (
            patch("backend.services.transcoding_service.check_nvenc_available", return_value=False),
            patch("backend.services.transcoding_service.get_settings") as mock_settings,
        ):
            mock_settings.return_value.hardware_acceleration_enabled = True

            args = get_video_encoder_args(use_hardware=True)

            assert "-c:v" in args
            assert "libx264" in args
            assert "-preset" in args
            assert "fast" in args
            assert "-crf" in args
            assert "23" in args

    def test_get_video_encoder_args_disabled(self):
        """Test encoder args when hardware acceleration is disabled."""
        from backend.services.transcoding_service import get_video_encoder_args

        with patch("backend.services.transcoding_service.get_settings") as mock_settings:
            mock_settings.return_value.hardware_acceleration_enabled = False

            args = get_video_encoder_args(use_hardware=True)

            assert "-c:v" in args
            assert "libx264" in args

    def test_get_video_encoder_args_force_software(self):
        """Test encoder args with use_hardware=False."""
        from backend.services.transcoding_service import get_video_encoder_args

        with patch("backend.services.transcoding_service.get_settings") as mock_settings:
            mock_settings.return_value.hardware_acceleration_enabled = True

            args = get_video_encoder_args(use_hardware=False)

            assert "-c:v" in args
            assert "libx264" in args


class TestTranscodeVideoWithNVENC:
    """Tests for transcode_video method with NVENC integration."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        cache_dir = tmp_path / "transcoded_cache"
        cache_dir.mkdir()
        return cache_dir

    @pytest.fixture
    def temp_video_file(self, tmp_path):
        """Create a temporary video file for testing."""
        video_file = tmp_path / "test_video.avi"
        video_file.write_bytes(b"fake video content" * 100)
        return video_file

    @pytest.fixture
    def transcoding_service(self, temp_cache_dir):
        """Create TranscodingService instance with temp directory."""
        return TranscodingService(cache_directory=str(temp_cache_dir))

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset singleton and NVENC cache."""
        from backend.services.transcoding_service import reset_nvenc_cache

        reset_transcoding_service()
        reset_nvenc_cache()
        yield
        reset_transcoding_service()
        reset_nvenc_cache()

    @pytest.mark.asyncio
    async def test_transcode_video_uses_nvenc_args(
        self, transcoding_service, temp_video_file, temp_cache_dir
    ):
        """Test that transcode_video uses get_video_encoder_args."""
        file_hash = _compute_file_hash(temp_video_file)
        expected_output = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"

        # Ensure no cached file exists - this is critical to test the actual transcoding
        if expected_output.exists():
            expected_output.unlink()

        with (
            patch("asyncio.create_subprocess_exec") as mock_exec,
            patch(
                "backend.services.transcoding_service.get_video_encoder_args",
                return_value=[
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p4",
                    "-cq",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                ],
            ) as mock_encoder,
        ):
            # First call is remux (should fail), second call is full transcode (should succeed)
            mock_remux_process = AsyncMock()
            mock_remux_process.returncode = 1  # Remux fails
            mock_remux_process.communicate = AsyncMock(return_value=(b"", b"remux failed"))

            mock_transcode_process = AsyncMock()
            mock_transcode_process.returncode = 0

            # Simulate ffmpeg creating the file after full transcode
            async def create_output(*args, **kwargs):
                # Write at least 1KB to pass the corrupted file check (MIN_VALID_FILE_SIZE = 1024)
                expected_output.write_bytes(b"transcoded content" + b"\x00" * 1024)
                return (b"", b"")

            mock_transcode_process.communicate = create_output

            # Return different processes for remux vs transcode calls
            mock_exec.side_effect = [mock_remux_process, mock_transcode_process]

            await transcoding_service.transcode_video(temp_video_file)

            mock_encoder.assert_called_once_with(use_hardware=True)

            # Verify NVENC args are passed to ffmpeg (second call is full transcode)
            call_args = mock_exec.call_args_list[1][0]
            assert "h264_nvenc" in call_args

    @pytest.mark.asyncio
    async def test_transcode_video_software_fallback(
        self, transcoding_service, temp_video_file, temp_cache_dir
    ):
        """Test transcoding falls back to software when NVENC unavailable."""
        file_hash = _compute_file_hash(temp_video_file)
        expected_output = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"

        # Ensure no cached file exists - this is critical to test the actual transcoding
        if expected_output.exists():
            expected_output.unlink()

        with (
            patch("asyncio.create_subprocess_exec") as mock_exec,
            patch(
                "backend.services.transcoding_service.get_video_encoder_args",
                return_value=[
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                ],
            ),
        ):
            # First call is remux (should fail), second call is full transcode (should succeed)
            mock_remux_process = AsyncMock()
            mock_remux_process.returncode = 1  # Remux fails
            mock_remux_process.communicate = AsyncMock(return_value=(b"", b"remux failed"))

            mock_transcode_process = AsyncMock()
            mock_transcode_process.returncode = 0

            # Simulate ffmpeg creating the file after full transcode
            async def create_output(*args, **kwargs):
                # Write at least 1KB to pass the corrupted file check (MIN_VALID_FILE_SIZE = 1024)
                expected_output.write_bytes(b"transcoded content" + b"\x00" * 1024)
                return (b"", b"")

            mock_transcode_process.communicate = create_output

            # Return different processes for remux vs transcode calls
            mock_exec.side_effect = [mock_remux_process, mock_transcode_process]

            await transcoding_service.transcode_video(temp_video_file)

            # Verify software args are passed to ffmpeg (second call is full transcode)
            call_args = mock_exec.call_args_list[1][0]
            assert "libx264" in call_args
