"""Event clip generator service for creating video clips around detected events.

This service generates short video clips from detected events for review.
It supports two modes:
1. Video source: Extract clip from existing video using ffmpeg
2. Image sequence: Create MP4/GIF from frame sequence using ffmpeg

Features:
    - Extract clips from video files with configurable pre/post roll
    - Generate video from image sequences
    - Store clips in configurable directory
    - Associate clips with Event records

Output Format:
    - File: {clips_directory}/{event_id}_clip.mp4
    - Codec: libx264 (H.264)
    - Audio: copy (if present) or none
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from backend.core.config import get_settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.models import Event

logger = get_logger(__name__)


class ClipGenerationError(Exception):
    """Exception raised when clip generation fails."""

    pass


class ClipGenerator:
    """Generates video clips from events using ffmpeg.

    This service creates visual clips of security events by:
    1. Extracting segments from existing video files
    2. Creating videos from image sequences when no video exists

    Clips are stored in a configurable directory and associated with events.
    """

    def __init__(
        self,
        clips_directory: str | Path | None = None,
        pre_roll_seconds: int | None = None,
        post_roll_seconds: int | None = None,
        enabled: bool | None = None,
    ):
        """Initialize clip generator with configuration.

        Args:
            clips_directory: Directory to save clips to. Defaults to settings.
            pre_roll_seconds: Seconds before event to include. Defaults to settings.
            post_roll_seconds: Seconds after event to include. Defaults to settings.
            enabled: Whether clip generation is enabled. Defaults to settings.
        """
        settings = get_settings()

        # Use settings as defaults, allow overrides
        self._clips_directory = Path(
            clips_directory
            if clips_directory is not None
            else getattr(settings, "clips_directory", "data/clips")
        )
        self._pre_roll_seconds = (
            pre_roll_seconds
            if pre_roll_seconds is not None
            else getattr(settings, "clip_pre_roll_seconds", 5)
        )
        self._post_roll_seconds = (
            post_roll_seconds
            if post_roll_seconds is not None
            else getattr(settings, "clip_post_roll_seconds", 5)
        )
        self._enabled = (
            enabled if enabled is not None else getattr(settings, "clip_generation_enabled", True)
        )

        # Ensure output directory exists
        self._ensure_clips_directory()

        logger.info(
            f"ClipGenerator initialized: directory={self._clips_directory}, "
            f"pre_roll={self._pre_roll_seconds}s, post_roll={self._post_roll_seconds}s, "
            f"enabled={self._enabled}"
        )

    def _ensure_clips_directory(self) -> None:
        """Create clips directory if it doesn't exist."""
        try:
            self._clips_directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Clips directory ready: {self._clips_directory}")
        except Exception as e:
            logger.error(f"Failed to create clips directory {self._clips_directory}: {e}")
            raise

    @property
    def enabled(self) -> bool:
        """Check if clip generation is enabled."""
        return self._enabled

    @property
    def clips_directory(self) -> Path:
        """Get the clips output directory."""
        return self._clips_directory

    async def generate_clip_from_video(
        self,
        event: Event,
        video_path: str | Path,
        pre_seconds: int | None = None,
        post_seconds: int | None = None,
    ) -> Path | None:
        """Generate a clip from an existing video file around event timestamps.

        Uses ffmpeg to extract a segment from the video file based on the event's
        start and end times, with configurable pre/post roll.

        Args:
            event: Event model with started_at and ended_at timestamps
            video_path: Path to source video file
            pre_seconds: Seconds before event start to include. Defaults to config.
            post_seconds: Seconds after event end to include. Defaults to config.

        Returns:
            Path to generated clip file, or None if generation failed

        Raises:
            ClipGenerationError: If ffmpeg command fails
        """
        if not self._enabled:
            logger.debug("Clip generation is disabled")
            return None

        video_path = Path(video_path)
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        pre_seconds = pre_seconds if pre_seconds is not None else self._pre_roll_seconds
        post_seconds = post_seconds if post_seconds is not None else self._post_roll_seconds

        # Calculate start and end times
        start_time = event.started_at
        end_time = event.ended_at or event.started_at

        # Apply pre/post roll
        # Convert to seconds from video start (assuming video starts at midnight of the same day)
        # For simplicity, we'll use the event times directly and calculate duration
        duration = (end_time - start_time).total_seconds() + pre_seconds + post_seconds

        # Generate output filename
        output_path = self._get_clip_path_for_event(event.id)

        # Build ffmpeg command
        # -ss: start time offset (before input for fast seeking)
        # -t: duration
        # -c:v libx264: H.264 video codec
        # -preset fast: encoding speed/quality tradeoff
        # -crf 23: constant rate factor (quality)
        # -c:a copy: copy audio stream if present
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-ss",
            str(pre_seconds),  # Seek offset (relative)
            "-i",
            str(video_path),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",  # Enable fast start for web playback
            str(output_path),
        ]

        try:
            logger.info(f"Generating clip for event {event.id} from video {video_path}")
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"FFmpeg failed for event {event.id}: {error_msg}")
                raise ClipGenerationError(
                    f"FFmpeg exited with code {process.returncode}: {error_msg}"
                )

            if output_path.exists():
                logger.info(f"Generated clip: {output_path} ({output_path.stat().st_size} bytes)")
                return output_path

            logger.error(f"Clip file not created: {output_path}")
            return None

        except FileNotFoundError:
            logger.error("ffmpeg not found. Please ensure ffmpeg is installed.")
            return None
        except ClipGenerationError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate clip for event {event.id}: {e}", exc_info=True)
            return None

    async def _run_ffmpeg_for_images(
        self,
        event_id: int,
        list_file_path: Path,
        output_path: Path,
        output_format: str,
        fps: int,
    ) -> Path | None:
        """Run ffmpeg to create clip from image list file.

        Args:
            event_id: Event ID for logging
            list_file_path: Path to ffmpeg concat list file
            output_path: Path for output clip
            output_format: 'mp4' or 'gif'
            fps: Frames per second

        Returns:
            Path to generated clip, or None on failure
        """
        if output_format.lower() == "gif":
            # GIF generation
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file_path),
                "-vf",
                f"fps={fps},scale=320:-1:flags=lanczos",
                "-loop",
                "0",  # Infinite loop
                str(output_path),
            ]
        else:
            # MP4 generation
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file_path),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",  # Compatibility
                "-movflags",
                "+faststart",
                str(output_path),
            ]

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"FFmpeg failed for event {event_id}: {error_msg}")
                raise ClipGenerationError(
                    f"FFmpeg exited with code {process.returncode}: {error_msg}"
                )

            if output_path.exists():
                logger.info(f"Generated clip: {output_path} ({output_path.stat().st_size} bytes)")
                return output_path

            logger.error(f"Clip file not created: {output_path}")
            return None
        finally:
            # Guaranteed cleanup of temp file even if exceptions occur
            try:
                list_file_path.unlink()
            except OSError:
                logger.debug(f"Could not delete temp file: {list_file_path}")

    async def generate_clip_from_images(
        self,
        event: Event,
        image_paths: list[str | Path],
        fps: int = 2,
        output_format: str = "mp4",
    ) -> Path | None:
        """Generate a video clip from a sequence of images.

        Uses ffmpeg to create an MP4 or GIF from a list of image files.
        Images should be in chronological order.

        Args:
            event: Event model for clip association
            image_paths: List of paths to image files in sequence order
            fps: Frames per second for output video. Defaults to 2.
            output_format: Output format ('mp4' or 'gif'). Defaults to 'mp4'.

        Returns:
            Path to generated clip file, or None if generation failed

        Raises:
            ClipGenerationError: If ffmpeg command fails
            ValueError: If fps is not an integer between 1 and 60
        """
        if not self._enabled:
            logger.debug("Clip generation is disabled")
            return None

        # Validate fps parameter to prevent command injection
        if not isinstance(fps, int) or not (1 <= fps <= 60):
            raise ValueError(f"fps must be an integer between 1 and 60, got {fps}")

        if not image_paths:
            logger.warning(f"No images provided for event {event.id}")
            return None

        # Validate images exist
        valid_paths = self._validate_image_paths(image_paths)
        if not valid_paths:
            logger.error(f"No valid images found for event {event.id}")
            return None

        # Generate output filename
        extension = "gif" if output_format.lower() == "gif" else "mp4"
        output_path = self._clips_directory / f"{event.id}_clip.{extension}"

        try:
            # Create temporary file list for ffmpeg concat demuxer
            list_file_path = self._create_concat_file(valid_paths, fps)

            logger.info(
                f"Generating {output_format} clip for event {event.id} "
                f"from {len(valid_paths)} images"
            )

            return await self._run_ffmpeg_for_images(
                event.id, list_file_path, output_path, output_format, fps
            )

        except FileNotFoundError:
            logger.error("ffmpeg not found. Please ensure ffmpeg is installed.")
            return None
        except ClipGenerationError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate clip for event {event.id}: {e}", exc_info=True)
            return None

    def _validate_image_paths(self, image_paths: list[str | Path]) -> list[Path]:
        """Validate image paths and return list of existing files."""
        valid_paths = []
        for img_path in image_paths:
            path = Path(img_path)
            if path.exists():
                valid_paths.append(path)
            else:
                logger.warning(f"Image not found, skipping: {img_path}")
        return valid_paths

    def _create_concat_file(self, valid_paths: list[Path], fps: int) -> Path:
        """Create ffmpeg concat demuxer file for image sequence."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as list_file:
            list_file_path = Path(list_file.name)
            # Write file list in ffmpeg concat format
            # Each line: file 'path' followed by duration line
            frame_duration = 1.0 / fps
            for img_path in valid_paths:
                # Escape single quotes in paths for FFmpeg concat format
                # FFmpeg uses shell-style quoting: ' -> '\''
                escaped_path = str(img_path).replace("'", "'\\''")
                list_file.write(f"file '{escaped_path}'\n")
                list_file.write(f"duration {frame_duration}\n")
            # Repeat last image to ensure it's shown
            escaped_last = str(valid_paths[-1]).replace("'", "'\\''")
            list_file.write(f"file '{escaped_last}'\n")

        return list_file_path

    def _get_clip_path_for_event(self, event_id: int) -> Path:
        """Get the output path for an event clip.

        Args:
            event_id: Event ID

        Returns:
            Path object for clip file
        """
        return self._clips_directory / f"{event_id}_clip.mp4"

    def get_clip_path(self, event_id: int | str) -> Path | None:
        """Get the path for an existing event clip.

        Args:
            event_id: Event ID

        Returns:
            Path to clip file if it exists, None otherwise
        """
        clip_path = self._clips_directory / f"{event_id}_clip.mp4"
        if clip_path.exists():
            return clip_path

        # Also check for GIF
        gif_path = self._clips_directory / f"{event_id}_clip.gif"
        if gif_path.exists():
            return gif_path

        return None

    def delete_clip(self, event_id: int | str) -> bool:
        """Delete a clip file for an event.

        Args:
            event_id: Event ID

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Try MP4 first
            clip_path = self._clips_directory / f"{event_id}_clip.mp4"
            if clip_path.exists():
                clip_path.unlink()
                logger.debug(f"Deleted clip: {clip_path}")
                return True

            # Try GIF
            gif_path = self._clips_directory / f"{event_id}_clip.gif"
            if gif_path.exists():
                gif_path.unlink()
                logger.debug(f"Deleted clip: {gif_path}")
                return True

            logger.warning(f"Clip not found for event {event_id}")
            return False

        except Exception as e:
            logger.error(f"Failed to delete clip for event {event_id}: {e}")
            return False

    async def generate_clip_for_event(
        self,
        event: Event,
        video_path: str | Path | None = None,
        image_paths: list[str | Path] | None = None,
        fps: int = 2,
    ) -> Path | None:
        """Generate a clip for an event, choosing the best method.

        If video_path is provided, extracts from video.
        Otherwise, if image_paths are provided, creates from images.

        Args:
            event: Event model
            video_path: Optional path to source video
            image_paths: Optional list of image paths
            fps: FPS for image sequence (default 2)

        Returns:
            Path to generated clip, or None if generation failed

        Raises:
            ValueError: If fps is not an integer between 1 and 60
        """
        if not self._enabled:
            logger.debug("Clip generation is disabled")
            return None

        # Validate fps parameter to prevent command injection
        if not isinstance(fps, int) or not (1 <= fps <= 60):
            raise ValueError(f"fps must be an integer between 1 and 60, got {fps}")

        if video_path:
            return await self.generate_clip_from_video(event, video_path)
        elif image_paths:
            return await self.generate_clip_from_images(event, image_paths, fps=fps)
        else:
            logger.warning(f"No source provided for event {event.id} clip generation")
            return None


# Module-level singleton for convenience
_clip_generator: ClipGenerator | None = None


def get_clip_generator() -> ClipGenerator:
    """Get or create the global clip generator instance.

    Returns:
        ClipGenerator singleton instance
    """
    global _clip_generator  # noqa: PLW0603

    if _clip_generator is None:
        _clip_generator = ClipGenerator()

    return _clip_generator


def reset_clip_generator() -> None:
    """Reset the global clip generator (for testing)."""
    global _clip_generator  # noqa: PLW0603
    _clip_generator = None
