"""Unit tests for clip generator service."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.clip_generator import (
    ALLOWED_OUTPUT_FORMATS,
    ClipGenerationError,
    ClipGenerator,
    _validate_fps,
    _validate_output_format,
    _validate_roll_seconds,
    _validate_video_path,
    get_clip_generator,
    reset_clip_generator,
)

# Fixtures


@pytest.fixture
def temp_clips_dir(tmp_path):
    """Create temporary clips directory."""
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    return clips_dir


@pytest.fixture
def clip_generator(temp_clips_dir):
    """Create ClipGenerator instance with temp directory."""
    return ClipGenerator(
        clips_directory=str(temp_clips_dir),
        pre_roll_seconds=5,
        post_roll_seconds=5,
        enabled=True,
    )


@pytest.fixture
def disabled_clip_generator(temp_clips_dir):
    """Create disabled ClipGenerator instance."""
    return ClipGenerator(
        clips_directory=str(temp_clips_dir),
        enabled=False,
    )


@pytest.fixture
def mock_event():
    """Create mock Event object."""
    event = MagicMock()
    event.id = 123
    event.started_at = datetime(2024, 1, 15, 10, 30, 0)
    event.ended_at = datetime(2024, 1, 15, 10, 30, 30)
    event.camera_id = "front_door"
    return event


@pytest.fixture
def mock_event_no_end():
    """Create mock Event without ended_at."""
    event = MagicMock()
    event.id = 456
    event.started_at = datetime(2024, 1, 15, 10, 30, 0)
    event.ended_at = None
    event.camera_id = "back_door"
    return event


# Initialization tests


def test_clip_generator_initialization(temp_clips_dir):
    """Test ClipGenerator initializes with correct settings."""
    generator = ClipGenerator(
        clips_directory=str(temp_clips_dir),
        pre_roll_seconds=10,
        post_roll_seconds=15,
        enabled=True,
    )

    assert generator.clips_directory == temp_clips_dir
    assert generator._pre_roll_seconds == 10
    assert generator._post_roll_seconds == 15
    assert generator.enabled is True


def test_clip_generator_default_values():
    """Test ClipGenerator uses settings defaults."""
    with patch("backend.services.clip_generator.get_settings") as mock_settings:
        mock_settings.return_value.clips_directory = "custom/clips"
        mock_settings.return_value.clip_pre_roll_seconds = 8
        mock_settings.return_value.clip_post_roll_seconds = 12
        mock_settings.return_value.clip_generation_enabled = False

        generator = ClipGenerator()

        assert str(generator.clips_directory) == "custom/clips"
        assert generator._pre_roll_seconds == 8
        assert generator._post_roll_seconds == 12
        assert generator.enabled is False


def test_clip_generator_creates_directory(tmp_path):
    """Test ClipGenerator creates clips directory if missing."""
    nonexistent_dir = tmp_path / "new_clips_dir"
    assert not nonexistent_dir.exists()

    generator = ClipGenerator(clips_directory=str(nonexistent_dir))

    assert nonexistent_dir.exists()
    assert generator.clips_directory == nonexistent_dir


def test_enabled_property(clip_generator, disabled_clip_generator):
    """Test enabled property reflects configuration."""
    assert clip_generator.enabled is True
    assert disabled_clip_generator.enabled is False


def test_clips_directory_property(clip_generator, temp_clips_dir):
    """Test clips_directory property returns correct path."""
    assert clip_generator.clips_directory == temp_clips_dir


# get_clip_path tests


def test_get_clip_path_mp4_exists(clip_generator, temp_clips_dir, mock_event):
    """Test get_clip_path returns MP4 path when exists."""
    # Create the clip file
    clip_file = temp_clips_dir / f"{mock_event.id}_clip.mp4"
    clip_file.touch()

    result = clip_generator.get_clip_path(mock_event.id)

    assert result == clip_file


def test_get_clip_path_gif_exists(clip_generator, temp_clips_dir, mock_event):
    """Test get_clip_path returns GIF path when MP4 doesn't exist."""
    # Create GIF clip file (no MP4)
    gif_file = temp_clips_dir / f"{mock_event.id}_clip.gif"
    gif_file.touch()

    result = clip_generator.get_clip_path(mock_event.id)

    assert result == gif_file


def test_get_clip_path_not_found(clip_generator, mock_event):
    """Test get_clip_path returns None when clip doesn't exist."""
    result = clip_generator.get_clip_path(mock_event.id)

    assert result is None


def test_get_clip_path_mp4_preferred_over_gif(clip_generator, temp_clips_dir, mock_event):
    """Test get_clip_path prefers MP4 over GIF."""
    # Create both MP4 and GIF
    mp4_file = temp_clips_dir / f"{mock_event.id}_clip.mp4"
    gif_file = temp_clips_dir / f"{mock_event.id}_clip.gif"
    mp4_file.touch()
    gif_file.touch()

    result = clip_generator.get_clip_path(mock_event.id)

    assert result == mp4_file


def test_get_clip_path_string_event_id(clip_generator, temp_clips_dir):
    """Test get_clip_path works with string event ID."""
    event_id = "789"
    clip_file = temp_clips_dir / f"{event_id}_clip.mp4"
    clip_file.touch()

    result = clip_generator.get_clip_path(event_id)

    assert result == clip_file


# delete_clip tests


def test_delete_clip_mp4(clip_generator, temp_clips_dir, mock_event):
    """Test delete_clip removes MP4 file."""
    clip_file = temp_clips_dir / f"{mock_event.id}_clip.mp4"
    clip_file.touch()
    assert clip_file.exists()

    result = clip_generator.delete_clip(mock_event.id)

    assert result is True
    assert not clip_file.exists()


def test_delete_clip_gif(clip_generator, temp_clips_dir, mock_event):
    """Test delete_clip removes GIF file when no MP4."""
    gif_file = temp_clips_dir / f"{mock_event.id}_clip.gif"
    gif_file.touch()
    assert gif_file.exists()

    result = clip_generator.delete_clip(mock_event.id)

    assert result is True
    assert not gif_file.exists()


def test_delete_clip_not_found(clip_generator, mock_event):
    """Test delete_clip returns False when clip doesn't exist."""
    result = clip_generator.delete_clip(mock_event.id)

    assert result is False


def test_delete_clip_error_handling(clip_generator, temp_clips_dir, mock_event):
    """Test delete_clip handles errors gracefully."""
    clip_file = temp_clips_dir / f"{mock_event.id}_clip.mp4"
    clip_file.touch()

    with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
        result = clip_generator.delete_clip(mock_event.id)

    # Should return False on error (but file still exists)
    assert result is False


# generate_clip_from_video tests


@pytest.mark.asyncio
async def test_generate_clip_from_video_disabled(disabled_clip_generator, mock_event, tmp_path):
    """Test generate_clip_from_video returns None when disabled."""
    video_path = tmp_path / "test.mp4"
    video_path.touch()

    result = await disabled_clip_generator.generate_clip_from_video(mock_event, video_path)

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_from_video_file_not_found(clip_generator, mock_event):
    """Test generate_clip_from_video returns None when video doesn't exist."""
    result = await clip_generator.generate_clip_from_video(mock_event, "/nonexistent/video.mp4")

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_from_video_success(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_video successfully generates clip."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    # Mock subprocess for ffmpeg
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    # Create the expected output file
    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        # Create the output file when ffmpeg "runs"
        expected_output.touch()

        result = await clip_generator.generate_clip_from_video(mock_event, video_path)

        assert result == expected_output
        mock_exec.assert_called_once()

        # Verify ffmpeg command arguments
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "ffmpeg"
        assert "-i" in call_args
        assert str(video_path) in call_args
        assert str(expected_output) in call_args


@pytest.mark.asyncio
async def test_generate_clip_from_video_ffmpeg_error(clip_generator, mock_event, tmp_path):
    """Test generate_clip_from_video raises error on ffmpeg failure."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(return_value=(b"", b"FFmpeg error message"))

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(ClipGenerationError) as exc_info:
            await clip_generator.generate_clip_from_video(mock_event, video_path)

        assert "FFmpeg exited with code 1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_clip_from_video_ffmpeg_not_found(clip_generator, mock_event, tmp_path):
    """Test generate_clip_from_video handles missing ffmpeg."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("ffmpeg not found"),
    ):
        result = await clip_generator.generate_clip_from_video(mock_event, video_path)

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_from_video_custom_pre_post_roll(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_video uses custom pre/post roll."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        expected_output.touch()

        await clip_generator.generate_clip_from_video(
            mock_event, video_path, pre_seconds=10, post_seconds=20
        )

        call_args = mock_exec.call_args[0]
        # Verify -ss (seek) and -t (duration) values reflect custom pre/post roll
        ss_index = call_args.index("-ss")
        assert call_args[ss_index + 1] == "10"  # pre_seconds


# generate_clip_from_images tests


@pytest.mark.asyncio
async def test_generate_clip_from_images_disabled(disabled_clip_generator, mock_event, tmp_path):
    """Test generate_clip_from_images returns None when disabled."""
    img_path = tmp_path / "frame1.jpg"
    img_path.touch()

    result = await disabled_clip_generator.generate_clip_from_images(mock_event, [str(img_path)])

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_from_images_empty_list(clip_generator, mock_event):
    """Test generate_clip_from_images returns None for empty list."""
    result = await clip_generator.generate_clip_from_images(mock_event, [])

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_from_images_no_valid_images(clip_generator, mock_event):
    """Test generate_clip_from_images returns None when no valid images."""
    result = await clip_generator.generate_clip_from_images(
        mock_event, ["/nonexistent/image1.jpg", "/nonexistent/image2.jpg"]
    )

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_from_images_success_mp4(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_images generates MP4 successfully."""
    # Create test images
    images = []
    for i in range(3):
        img_path = tmp_path / f"frame{i}.jpg"
        img_path.touch()
        images.append(str(img_path))

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        expected_output.touch()

        result = await clip_generator.generate_clip_from_images(
            mock_event, images, fps=2, output_format="mp4"
        )

        assert result == expected_output
        mock_exec.assert_called_once()

        call_args = mock_exec.call_args[0]
        assert call_args[0] == "ffmpeg"
        assert "-c:v" in call_args
        assert "libx264" in call_args


@pytest.mark.asyncio
async def test_generate_clip_from_images_success_gif(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_images generates GIF successfully."""
    images = []
    for i in range(3):
        img_path = tmp_path / f"frame{i}.jpg"
        img_path.touch()
        images.append(str(img_path))

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.gif"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        expected_output.touch()

        result = await clip_generator.generate_clip_from_images(
            mock_event, images, fps=2, output_format="gif"
        )

        assert result == expected_output
        mock_exec.assert_called_once()

        call_args = mock_exec.call_args[0]
        assert call_args[0] == "ffmpeg"
        assert "-loop" in call_args


@pytest.mark.asyncio
async def test_generate_clip_from_images_skips_invalid(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_images skips nonexistent images."""
    valid_img = tmp_path / "valid.jpg"
    valid_img.touch()

    images = [
        str(valid_img),
        "/nonexistent/image.jpg",  # Should be skipped
    ]

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        expected_output.touch()

        result = await clip_generator.generate_clip_from_images(mock_event, images)

        assert result is not None


@pytest.mark.asyncio
async def test_generate_clip_from_images_ffmpeg_error(clip_generator, mock_event, tmp_path):
    """Test generate_clip_from_images raises error on ffmpeg failure."""
    img_path = tmp_path / "frame.jpg"
    img_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(return_value=(b"", b"FFmpeg error"))

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_process),
        pytest.raises(ClipGenerationError),
    ):
        await clip_generator.generate_clip_from_images(mock_event, [str(img_path)])


# generate_clip_for_event tests


@pytest.mark.asyncio
async def test_generate_clip_for_event_disabled(disabled_clip_generator, mock_event):
    """Test generate_clip_for_event returns None when disabled."""
    result = await disabled_clip_generator.generate_clip_for_event(mock_event)

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_for_event_no_source(clip_generator, mock_event):
    """Test generate_clip_for_event returns None when no source provided."""
    result = await clip_generator.generate_clip_for_event(mock_event)

    assert result is None


@pytest.mark.asyncio
async def test_generate_clip_for_event_with_video(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_for_event uses video when provided."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        expected_output.touch()

        result = await clip_generator.generate_clip_for_event(
            mock_event, video_path=str(video_path)
        )

        assert result == expected_output


@pytest.mark.asyncio
async def test_generate_clip_for_event_with_images(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_for_event uses images when provided."""
    images = []
    for i in range(3):
        img_path = tmp_path / f"frame{i}.jpg"
        img_path.touch()
        images.append(str(img_path))

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        expected_output.touch()

        result = await clip_generator.generate_clip_for_event(mock_event, image_paths=images)

        assert result == expected_output


@pytest.mark.asyncio
async def test_generate_clip_for_event_video_preferred_over_images(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_for_event prefers video over images."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    images = [str(tmp_path / "frame.jpg")]
    (tmp_path / "frame.jpg").touch()

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        expected_output.touch()

        await clip_generator.generate_clip_for_event(
            mock_event, video_path=str(video_path), image_paths=images
        )

        # Verify video method was used (check for -i with video path)
        call_args = mock_exec.call_args[0]
        assert str(video_path) in call_args


# Singleton tests


def test_get_clip_generator_returns_singleton():
    """Test get_clip_generator returns same instance."""
    reset_clip_generator()

    gen1 = get_clip_generator()
    gen2 = get_clip_generator()

    assert gen1 is gen2

    reset_clip_generator()


def test_reset_clip_generator():
    """Test reset_clip_generator clears singleton."""
    reset_clip_generator()

    gen1 = get_clip_generator()
    reset_clip_generator()
    gen2 = get_clip_generator()

    assert gen1 is not gen2

    reset_clip_generator()


# Event without end time tests


@pytest.mark.asyncio
async def test_generate_clip_from_video_no_end_time(
    clip_generator, mock_event_no_end, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_video handles event without ended_at."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event_no_end.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        expected_output.touch()

        result = await clip_generator.generate_clip_from_video(mock_event_no_end, video_path)

        assert result is not None


# Path handling tests


@pytest.mark.asyncio
async def test_generate_clip_from_video_path_object(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_video accepts Path object."""
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        expected_output.touch()

        # Pass as Path object, not string
        result = await clip_generator.generate_clip_from_video(mock_event, video_path)

        assert result is not None


@pytest.mark.asyncio
async def test_generate_clip_from_images_path_objects(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Test generate_clip_from_images accepts Path objects."""
    images = []
    for i in range(2):
        img_path = tmp_path / f"frame{i}.jpg"
        img_path.touch()
        images.append(img_path)  # Path objects, not strings

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        expected_output.touch()

        result = await clip_generator.generate_clip_from_images(mock_event, images)

        assert result is not None


# =============================================================================
# Security Validation Tests - Command Injection Prevention
# =============================================================================


class TestSecurityValidation:
    """Test input validation functions that prevent command injection."""

    def test_validate_video_path_rejects_nonexistent(self) -> None:
        """Test that nonexistent paths are rejected."""
        with pytest.raises(ValueError, match="Video file not found"):
            _validate_video_path("/nonexistent/path/to/video.mp4")

    def test_validate_video_path_rejects_directory(self, tmp_path: Path) -> None:
        """Test that directories are rejected."""
        with pytest.raises(ValueError, match="Path is not a file"):
            _validate_video_path(str(tmp_path))

    def test_validate_video_path_rejects_dash_prefix(self) -> None:
        """Test that paths starting with dash are rejected (command option injection)."""
        with pytest.raises(ValueError, match="Video file not found"):
            _validate_video_path("-malicious_file.mp4")

    def test_validate_video_path_accepts_valid_file(self, tmp_path: Path) -> None:
        """Test that valid video files are accepted."""
        video_file = tmp_path / "valid_video.mp4"
        video_file.write_bytes(b"fake video content")
        result = _validate_video_path(str(video_file))
        assert result == video_file.resolve()

    def test_validate_roll_seconds_rejects_non_integer(self) -> None:
        """Test that non-integer roll seconds are rejected."""
        with pytest.raises(ValueError, match="pre_seconds must be an integer"):
            _validate_roll_seconds(5.5, "pre_seconds")  # type: ignore[arg-type]

    def test_validate_roll_seconds_rejects_negative(self) -> None:
        """Test that negative roll seconds are rejected."""
        with pytest.raises(ValueError, match="pre_seconds must be between 0 and 300"):
            _validate_roll_seconds(-1, "pre_seconds")

    def test_validate_roll_seconds_rejects_too_large(self) -> None:
        """Test that roll seconds over 5 minutes are rejected."""
        with pytest.raises(ValueError, match="post_seconds must be between 0 and 300"):
            _validate_roll_seconds(400, "post_seconds")

    def test_validate_roll_seconds_accepts_valid_values(self) -> None:
        """Test that valid roll seconds are accepted."""
        assert _validate_roll_seconds(0, "pre_seconds") == 0
        assert _validate_roll_seconds(5, "pre_seconds") == 5
        assert _validate_roll_seconds(300, "post_seconds") == 300

    def test_validate_output_format_rejects_invalid(self) -> None:
        """Test that invalid output formats are rejected."""
        with pytest.raises(ValueError, match="Output format must be one of"):
            _validate_output_format("avi")
        with pytest.raises(ValueError, match="Output format must be one of"):
            _validate_output_format("mp4; rm -rf /")

    def test_validate_output_format_accepts_valid(self) -> None:
        """Test that valid output formats are accepted."""
        assert _validate_output_format("mp4") == "mp4"
        assert _validate_output_format("gif") == "gif"
        assert _validate_output_format("MP4") == "mp4"
        assert _validate_output_format("GIF") == "gif"
        assert _validate_output_format("  mp4  ") == "mp4"

    def test_allowed_formats_immutable(self) -> None:
        """Test that ALLOWED_OUTPUT_FORMATS is immutable."""
        assert isinstance(ALLOWED_OUTPUT_FORMATS, frozenset)
        assert "mp4" in ALLOWED_OUTPUT_FORMATS
        assert "gif" in ALLOWED_OUTPUT_FORMATS

    def test_validate_fps_rejects_non_integer(self) -> None:
        """Test that non-integer fps are rejected."""
        with pytest.raises(ValueError, match="fps must be an integer"):
            _validate_fps(2.5)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="fps must be an integer"):
            _validate_fps("2")  # type: ignore[arg-type]

    def test_validate_fps_rejects_out_of_bounds(self) -> None:
        """Test that out-of-bounds fps are rejected."""
        with pytest.raises(ValueError, match="fps must be between 1 and 60"):
            _validate_fps(0)
        with pytest.raises(ValueError, match="fps must be between 1 and 60"):
            _validate_fps(61)

    def test_validate_fps_accepts_valid_values(self) -> None:
        """Test that valid fps are accepted."""
        assert _validate_fps(1) == 1
        assert _validate_fps(30) == 30
        assert _validate_fps(60) == 60


class TestClipGeneratorSecurityIntegration:
    """Integration tests for security validation in ClipGenerator methods."""

    @pytest.fixture
    def temp_clips_dir(self, tmp_path):
        """Create temporary clips directory."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        return clips_dir

    @pytest.fixture
    def clip_generator(self, temp_clips_dir):
        """Create ClipGenerator instance with temp directory."""
        return ClipGenerator(
            clips_directory=str(temp_clips_dir),
            pre_roll_seconds=5,
            post_roll_seconds=5,
            enabled=True,
        )

    @pytest.fixture
    def mock_event(self):
        """Create mock Event object."""
        event = MagicMock()
        event.id = 123
        event.started_at = datetime(2024, 1, 15, 10, 30, 0)
        event.ended_at = datetime(2024, 1, 15, 10, 30, 30)
        event.camera_id = "front_door"
        return event

    @pytest.mark.asyncio
    async def test_generate_clip_from_video_rejects_invalid_path(
        self, clip_generator, mock_event
    ) -> None:
        """Test that generate_clip_from_video rejects invalid video paths."""
        # Path that looks like command option
        result = await clip_generator.generate_clip_from_video(
            mock_event, "-i /etc/passwd -o /tmp/evil"
        )
        assert result is None

        # Nonexistent path
        result = await clip_generator.generate_clip_from_video(mock_event, "/nonexistent/video.mp4")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_clip_from_images_rejects_invalid_fps(
        self, clip_generator, mock_event, tmp_path
    ) -> None:
        """Test that generate_clip_from_images rejects invalid fps."""
        img_path = tmp_path / "frame1.jpg"
        img_path.touch()

        with pytest.raises(ValueError, match="fps must be between 1 and 60"):
            await clip_generator.generate_clip_from_images(mock_event, [str(img_path)], fps=0)

        with pytest.raises(ValueError, match="fps must be between 1 and 60"):
            await clip_generator.generate_clip_from_images(mock_event, [str(img_path)], fps=100)

    @pytest.mark.asyncio
    async def test_generate_clip_from_images_rejects_invalid_format(
        self, clip_generator, mock_event, tmp_path
    ) -> None:
        """Test that generate_clip_from_images rejects invalid output format."""
        img_path = tmp_path / "frame1.jpg"
        img_path.touch()

        with pytest.raises(ValueError, match="Output format must be one of"):
            await clip_generator.generate_clip_from_images(
                mock_event, [str(img_path)], output_format="avi; rm -rf /"
            )

    @pytest.mark.asyncio
    async def test_generate_clip_for_event_rejects_invalid_fps(
        self, clip_generator, mock_event, tmp_path
    ) -> None:
        """Test that generate_clip_for_event rejects invalid fps."""
        img_path = tmp_path / "frame1.jpg"
        img_path.touch()

        with pytest.raises(ValueError, match="fps must be between 1 and 60"):
            await clip_generator.generate_clip_for_event(
                mock_event, image_paths=[str(img_path)], fps=0
            )

    def test_validate_image_paths_rejects_dash_prefix(self, clip_generator, tmp_path) -> None:
        """Test that _validate_image_paths filters out paths starting with dash."""
        # Create a regular file
        valid_img = tmp_path / "valid.jpg"
        valid_img.touch()

        # Try to include a path that looks like a command option
        # This won't exist, so it will be filtered out
        result = clip_generator._validate_image_paths([str(valid_img), "-i /etc/passwd"])

        assert len(result) == 1
        assert result[0] == valid_img.resolve()

    def test_validate_image_paths_skips_nonexistent(self, clip_generator, tmp_path) -> None:
        """Test that _validate_image_paths skips nonexistent files."""
        valid_img = tmp_path / "valid.jpg"
        valid_img.touch()

        result = clip_generator._validate_image_paths([str(valid_img), "/nonexistent/image.jpg"])

        assert len(result) == 1
        assert result[0] == valid_img.resolve()

    def test_validate_image_paths_skips_directories(self, clip_generator, tmp_path) -> None:
        """Test that _validate_image_paths skips directories."""
        valid_img = tmp_path / "valid.jpg"
        valid_img.touch()

        result = clip_generator._validate_image_paths(
            [str(valid_img), str(tmp_path)]  # tmp_path is a directory
        )

        assert len(result) == 1
        assert result[0] == valid_img.resolve()
