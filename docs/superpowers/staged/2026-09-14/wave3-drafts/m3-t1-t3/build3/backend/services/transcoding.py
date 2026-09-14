"""Video transcoding service for browser-compatible video playback.

This service provides video transcoding functionality to convert various video
formats into browser-compatible H.264/AAC format for web playback.

Features:
    - Transcode videos to H.264/AAC MP4 format for universal browser support
    - Configurable quality presets (high, medium, low)
    - NVIDIA NVENC hardware acceleration with automatic fallback (NEM-2682)
    - Progress logging for long-running transcoding operations
    - Proper error handling with detailed error messages
    - Input validation to prevent command injection attacks

Output Format:
    - Container: MP4
    - Video Codec: h264_nvenc (NVENC) or libx264 (software fallback)
    - Audio Codec: AAC
    - Pixel Format: yuv420p (for browser compatibility)
    - Fast start enabled for progressive web playback

Security:
    - All user inputs are validated before use in subprocess calls
    - Uses subprocess with list arguments (never shell=True)
    - Paths are validated to prevent command-line option injection

Error Handling Pattern:
    This module uses a consistent error handling strategy:

    1. REQUIRED operations -> raise TranscodingError
       - transcode_to_mp4(): Raises TranscodingError if transcoding fails
       These are operations where callers cannot proceed without the result.

    2. OPTIONAL operations -> return False/None
       - check_ffmpeg_available() -> bool
       - get_video_info() -> dict | None
       These are operations where callers can proceed with fallback behavior.

Example:
    from backend.services.transcoding import TranscodingService

    service = TranscodingService(output_dir="/path/to/output")
    try:
        output_path = await service.transcode_to_mp4(
            input_path="/path/to/video.mkv",
            output_filename="video_transcoded.mp4",
            quality_preset="medium",
        )
    except TranscodingError as e:
        logger.error(f"Transcoding failed: {e}")
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Literal

from backend.core.logging import get_logger

# Import NVENC detection functions from transcoding_service (NEM-2682)
from backend.services.transcoding_service import (
    check_nvenc_available,
    get_video_encoder_args,
    reset_nvenc_cache,
)

logger = get_logger(__name__)

# Re-export NVENC functions for convenience
__all__ = [
    "QUALITY_PRESETS",
    "QualityPreset",
    "TranscodingError",
    "TranscodingService",
    "check_nvenc_available",
    "get_transcoding_service",
    "get_video_encoder_args",
    "reset_nvenc_cache",
    "reset_transcoding_service",
]

# Quality preset configurations
# CRF (Constant Rate Factor): Lower = better quality, larger file
# 18 = visually lossless, 23 = default, 28 = smaller file
QUALITY_PRESETS: dict[str, dict[str, str | int]] = {
    "high": {
        "crf": 18,
        "preset": "slow",
        "audio_bitrate": "192k",
    },
    "medium": {
        "crf": 23,
        "preset": "medium",
        "audio_bitrate": "128k",
    },
    "low": {
        "crf": 28,
        "preset": "fast",
        "audio_bitrate": "96k",
    },
}

QualityPreset = Literal["high", "medium", "low"]


def _validate_input_path(input_path: str | Path) -> Path:
    """Validate input video path for safe use in subprocess calls.

    Performs security checks to prevent path injection attacks when
    the path is passed to ffmpeg subprocess commands.

    Args:
        input_path: Path to validate

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path validation fails
    """
    path_obj = Path(input_path).resolve()
    if not path_obj.exists():
        raise ValueError(f"Input video file not found: {input_path}")
    if not path_obj.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    # Prevent paths that look like command-line options
    if str(path_obj).startswith("-"):
        raise ValueError(f"Invalid input path: {input_path}")
    return path_obj


def _validate_output_filename(filename: str) -> str:
    """Validate output filename for safe use.

    Args:
        filename: Filename to validate

    Returns:
        Validated filename

    Raises:
        ValueError: If filename is invalid
    """
    if not filename:
        raise ValueError("Output filename cannot be empty")
    if "/" in filename or "\\" in filename:
        raise ValueError(f"Output filename cannot contain path separators: {filename}")
    if filename.startswith("-"):
        raise ValueError(f"Invalid output filename: {filename}")
    # Ensure it has .mp4 extension
    if not filename.lower().endswith(".mp4"):
        filename = f"{filename}.mp4"
    return filename


def _validate_quality_preset(preset: str) -> str:
    """Validate quality preset.

    Args:
        preset: Quality preset name

    Returns:
        Validated preset name (lowercase)

    Raises:
        ValueError: If preset is not valid
    """
    normalized = preset.lower().strip()
    if normalized not in QUALITY_PRESETS:
        raise ValueError(
            f"Invalid quality preset: {preset}. Must be one of: {', '.join(QUALITY_PRESETS.keys())}"
        )
    return normalized


class TranscodingError(Exception):
    """Exception raised when video transcoding fails.

    This exception is raised for any error during the transcoding process,
    including FFmpeg failures, file I/O errors, or invalid input.
    """

    pass


class TranscodingService:
    """Video transcoding service for browser-compatible playback.

    This service uses FFmpeg to transcode videos into browser-compatible
    H.264/AAC MP4 format, suitable for web playback across all major browsers.

    Supported input formats:
        - Most formats supported by FFmpeg (MKV, AVI, MOV, WebM, etc.)

    Output format:
        - Container: MP4
        - Video: H.264 (libx264)
        - Audio: AAC
        - Pixel Format: yuv420p

    Attributes:
        output_dir: Directory where transcoded files are saved
    """

    def __init__(self, output_dir: str | Path = "data/transcoded"):
        """Initialize the transcoding service.

        Args:
            output_dir: Directory to save transcoded videos. Relative paths
                       are relative to the current working directory.
                       Defaults to "data/transcoded".
        """
        self._output_dir = Path(output_dir)
        self._ensure_output_dir()
        self._ffmpeg_available: bool | None = None

    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist.

        Raises:
            Exception: If directory creation fails
        """
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Transcoding output directory ready: {self._output_dir}")
        except Exception as e:
            logger.error(f"Failed to create transcoding output directory {self._output_dir}: {e}")
            raise

    @property
    def output_dir(self) -> Path:
        """Get the output directory path."""
        return self._output_dir

    def check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available on the system.

        Returns:
            True if FFmpeg is available, False otherwise
        """
        if self._ffmpeg_available is not None:
            return self._ffmpeg_available

        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self._ffmpeg_available = result.returncode == 0
            if self._ffmpeg_available:
                logger.debug("FFmpeg is available")
            else:
                logger.warning("FFmpeg returned non-zero exit code")
        except FileNotFoundError:
            logger.warning(
                "FFmpeg not found in PATH. Install with: "
                "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
            )
            self._ffmpeg_available = False
        except subprocess.TimeoutExpired:
            logger.warning("FFmpeg availability check timed out")
            self._ffmpeg_available = False
        except Exception as e:
            logger.warning(f"Error checking FFmpeg availability: {e}")
            self._ffmpeg_available = False

        return self._ffmpeg_available

    async def get_video_info(self, input_path: str | Path) -> dict | None:  # noqa: PLR0911
        """Get video information using FFprobe.

        Args:
            input_path: Path to the video file

        Returns:
            Dictionary with video info (duration, width, height, video_codec,
            audio_codec, has_audio), or None if extraction fails
        """
        try:
            validated_path = _validate_input_path(input_path)
        except ValueError as e:
            logger.error(f"Input path validation failed: {e}")
            return None

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(validated_path),
        ]

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                logger.error(f"FFprobe failed for {input_path}: {result.stderr}")
                return None

            data = json.loads(result.stdout)

            # Extract stream information
            video_stream = None
            audio_stream = None
            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video" and video_stream is None:
                    video_stream = stream
                elif codec_type == "audio" and audio_stream is None:
                    audio_stream = stream

            if not video_stream:
                logger.warning(f"No video stream found in {input_path}")
                return None

            format_info = data.get("format", {})

            return {
                "duration": float(format_info.get("duration", 0)),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "video_codec": video_stream.get("codec_name"),
                "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
                "has_audio": audio_stream is not None,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse FFprobe output: {e}")
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"FFprobe timed out for {input_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return None

    async def transcode_to_mp4(
        self,
        input_path: str | Path,
        output_filename: str | None = None,
        quality_preset: QualityPreset = "medium",
        timeout: int = 3600,
    ) -> Path:
        """Transcode a video to browser-compatible H.264/AAC MP4 format.

        This method converts any FFmpeg-supported video format into a
        browser-compatible MP4 file using H.264 video and AAC audio codecs.

        Args:
            input_path: Path to the input video file
            output_filename: Name for the output file (without directory).
                            If None, generates from input filename.
            quality_preset: Quality preset ('high', 'medium', 'low').
                           Defaults to 'medium'.
            timeout: Maximum time in seconds for transcoding. Defaults to 3600 (1 hour).

        Returns:
            Path to the transcoded video file

        Raises:
            TranscodingError: If transcoding fails for any reason
        """
        # Validate inputs
        try:
            validated_input = _validate_input_path(input_path)
        except ValueError as e:
            raise TranscodingError(str(e)) from e

        try:
            validated_preset = _validate_quality_preset(quality_preset)
        except ValueError as e:
            raise TranscodingError(str(e)) from e

        # Generate output filename if not provided
        if output_filename is None:
            output_filename = f"{validated_input.stem}_transcoded.mp4"

        try:
            validated_filename = _validate_output_filename(output_filename)
        except ValueError as e:
            raise TranscodingError(str(e)) from e

        output_path = self._output_dir / validated_filename

        # Check FFmpeg availability
        if not self.check_ffmpeg_available():
            raise TranscodingError(
                "FFmpeg is not available. Install with: "
                "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
            )

        # Get video info for logging
        video_info = await self.get_video_info(input_path)
        if video_info:
            logger.info(
                f"Transcoding {validated_input.name}: "
                f"{video_info.get('width')}x{video_info.get('height')}, "
                f"duration: {video_info.get('duration', 0):.1f}s, "
                f"codec: {video_info.get('video_codec')}"
            )
        else:
            logger.info(f"Transcoding {validated_input.name}")

        # Get quality settings
        quality_config = QUALITY_PRESETS[validated_preset]

        # Get video encoder arguments with NVENC/software fallback (NEM-2682)
        encoder_args = get_video_encoder_args(use_hardware=True)

        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-i",
            str(validated_input),
            # Video codec settings (NVENC or libx264 via get_video_encoder_args)
            *encoder_args,
            # Audio codec settings
            "-c:a",
            "aac",
            "-b:a",
            str(quality_config["audio_bitrate"]),
            # Container settings
            "-movflags",
            "+faststart",  # Enable progressive playback
            # Output
            str(output_path),
        ]

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                _stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except TimeoutError as e:
                process.kill()
                await process.wait()
                raise TranscodingError(
                    f"Transcoding timed out after {timeout} seconds for {input_path}"
                ) from e

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                # Extract relevant error message (last few lines)
                error_lines = error_msg.strip().split("\n")
                relevant_error = "\n".join(error_lines[-5:]) if len(error_lines) > 5 else error_msg
                raise TranscodingError(
                    f"FFmpeg transcoding failed (exit code {process.returncode}): {relevant_error}"
                )

            # Verify output file was created
            if not output_path.exists():
                raise TranscodingError(f"Transcoded file was not created: {output_path}")

            # Log success
            output_size = output_path.stat().st_size
            logger.info(
                f"Transcoding complete: {output_path.name} ({output_size / (1024 * 1024):.1f} MB)"
            )

            return output_path

        except FileNotFoundError as e:
            raise TranscodingError("FFmpeg executable not found") from e
        except TranscodingError:
            raise
        except Exception as e:
            raise TranscodingError(f"Unexpected error during transcoding: {e}") from e

    def get_output_path(self, filename: str) -> Path:
        """Get the full output path for a given filename.

        Args:
            filename: Output filename

        Returns:
            Full path in the output directory
        """
        return self._output_dir / filename

    def delete_transcoded_file(self, filename: str) -> bool:
        """Delete a transcoded file.

        Args:
            filename: Name of the file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            file_path = self._output_dir / filename
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted transcoded file: {file_path}")
                return True
            else:
                logger.warning(f"Transcoded file not found: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete transcoded file {filename}: {e}")
            return False


# Module-level singleton for convenience
_transcoding_service: TranscodingService | None = None


def get_transcoding_service() -> TranscodingService:
    """Get or create the global transcoding service instance.

    Returns:
        TranscodingService singleton instance
    """
    global _transcoding_service  # noqa: PLW0603

    if _transcoding_service is None:
        _transcoding_service = TranscodingService()

    return _transcoding_service


def reset_transcoding_service() -> None:
    """Reset the global transcoding service (for testing)."""
    global _transcoding_service  # noqa: PLW0603
    _transcoding_service = None
