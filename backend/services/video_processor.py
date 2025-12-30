"""Video processor service for extracting metadata and thumbnails from video files.

This service handles video file processing including:
- Extracting video metadata (duration, codec, resolution)
- Generating thumbnail frames from videos
- Validating video file integrity

Uses ffmpeg subprocess for reliable cross-platform video processing.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from backend.core.logging import get_logger, sanitize_error
from backend.core.mime_types import DEFAULT_VIDEO_MIME, get_mime_type_with_default

# Keep sanitize_error imported for future use, suppress unused import warning
_ = sanitize_error

logger = get_logger(__name__)

# Default thumbnail extraction settings
DEFAULT_THUMBNAIL_SIZE = (320, 240)
DEFAULT_THUMBNAIL_QUALITY = 85


def _validate_video_path(video_path: str) -> Path:
    """Validate video path for safe use in subprocess calls.

    Performs security checks to prevent path injection attacks when
    the path is passed to ffmpeg/ffprobe subprocess commands.

    Args:
        video_path: Path to validate

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path validation fails
    """
    video_path_obj = Path(video_path).resolve()
    if not video_path_obj.exists():
        raise ValueError(f"Video file not found: {video_path}")
    if not video_path_obj.is_file():
        raise ValueError(f"Path is not a file: {video_path}")
    # Prevent paths that look like command-line options
    if str(video_path_obj).startswith("-"):
        raise ValueError(f"Invalid video path: {video_path}")
    return video_path_obj


class VideoProcessingError(Exception):
    """Raised when video processing fails."""

    pass


class VideoProcessor:
    """Processes video files for metadata extraction and thumbnail generation.

    This service uses ffmpeg/ffprobe for video processing, providing reliable
    cross-platform support for various video formats.

    Supported formats:
    - MP4 (.mp4)
    - Matroska (.mkv)
    - AVI (.avi)
    - QuickTime (.mov)

    Features:
    - Extract video metadata (duration, codec, resolution)
    - Generate thumbnail frames at configurable timestamps
    - Async-compatible subprocess execution
    """

    def __init__(self, output_dir: str = "data/thumbnails"):
        """Initialize video processor.

        Args:
            output_dir: Directory to save thumbnails. Relative paths are
                       relative to backend/. Defaults to "data/thumbnails".
        """
        self.output_dir = Path(output_dir)
        self._ensure_output_dir()
        self._check_ffmpeg_available()

    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Video thumbnail output directory ready: {self.output_dir}")
        except Exception as e:
            logger.error(
                f"Failed to create video thumbnail output directory {self.output_dir}: {e}"
            )
            raise

    def _check_ffmpeg_available(self) -> None:
        """Check if ffmpeg and ffprobe are available on the system."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],  # noqa: S607
                capture_output=True,
                check=True,
                timeout=5,
            )
            subprocess.run(
                ["ffprobe", "-version"],  # noqa: S607
                capture_output=True,
                check=True,
                timeout=5,
            )
            logger.debug("ffmpeg and ffprobe are available")
        except FileNotFoundError:
            logger.warning(
                "ffmpeg/ffprobe not found in PATH. Video processing will not work. "
                "Install ffmpeg: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
            )
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg/ffprobe check timed out")
        except subprocess.CalledProcessError as e:
            logger.warning(f"ffmpeg/ffprobe check failed: {e}")

    async def get_video_metadata(self, video_path: str) -> dict[str, Any]:
        """Extract metadata from a video file.

        Args:
            video_path: Path to the video file

        Returns:
            Dictionary containing:
            - duration: Video duration in seconds (float)
            - video_codec: Video codec name (e.g., "h264", "hevc")
            - video_width: Video width in pixels
            - video_height: Video height in pixels
            - file_type: MIME type of the video

        Raises:
            VideoProcessingError: If metadata extraction fails
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError as e:
            raise VideoProcessingError(str(e)) from e

        try:
            # Use ffprobe to get video metadata as JSON
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

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise VideoProcessingError(f"ffprobe failed for {video_path}: {result.stderr}")

            data = json.loads(result.stdout)

            # Extract video stream info
            video_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            if not video_stream:
                raise VideoProcessingError(f"No video stream found in {video_path}")

            # Extract format info
            format_info = data.get("format", {})

            # Determine MIME type based on file extension
            mime_type = self._get_mime_type(video_path)

            return {
                "duration": float(format_info.get("duration", 0)),
                "video_codec": video_stream.get("codec_name"),
                "video_width": video_stream.get("width"),
                "video_height": video_stream.get("height"),
                "file_type": mime_type,
            }

        except json.JSONDecodeError as e:
            raise VideoProcessingError(f"Failed to parse ffprobe output: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise VideoProcessingError(f"ffprobe timed out for {video_path}") from e
        except Exception as e:
            if isinstance(e, VideoProcessingError):
                raise
            raise VideoProcessingError(f"Failed to get video metadata: {e}") from e

    def _get_mime_type(self, video_path: str) -> str:
        """Get MIME type for a video file based on extension.

        Args:
            video_path: Path to video file

        Returns:
            MIME type string
        """
        return get_mime_type_with_default(video_path, DEFAULT_VIDEO_MIME)

    async def extract_thumbnail(
        self,
        video_path: str,
        output_path: str | None = None,
        timestamp: float | None = None,
        size: tuple[int, int] = DEFAULT_THUMBNAIL_SIZE,
    ) -> str | None:
        """Extract a thumbnail frame from a video.

        By default, extracts frame at 1 second or 10% into the video, whichever
        is smaller. This helps avoid black/blank frames at the start.

        Args:
            video_path: Path to the video file
            output_path: Path to save thumbnail. If None, generates path in output_dir
            timestamp: Timestamp in seconds to extract frame. If None, uses smart default
            size: Thumbnail dimensions as (width, height). Default: (320, 240)

        Returns:
            Path to the saved thumbnail, or None if extraction failed
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError as e:
            logger.error(f"Video path validation failed: {e}")
            return None

        try:
            # Get video duration to calculate smart timestamp
            if timestamp is None:
                try:
                    metadata = await self.get_video_metadata(video_path)
                    duration = metadata.get("duration", 0)
                    # Use 1 second or 10% into video, whichever is smaller
                    timestamp = min(1.0, duration * 0.1) if duration > 0 else 0
                except VideoProcessingError:
                    # Fall back to 1 second if metadata extraction fails
                    timestamp = 1.0

            # Generate output path if not provided
            if output_path is None:
                video_stem = validated_path.stem
                output_path = str(self.output_dir / f"{video_stem}_thumb.jpg")

            # Build ffmpeg command for thumbnail extraction
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-ss",
                str(timestamp),  # Seek to timestamp
                "-i",
                str(validated_path),  # Input file
                "-vframes",
                "1",  # Extract only 1 frame
                "-vf",
                f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",  # Scale with padding
                "-q:v",
                "2",  # High quality JPEG
                output_path,
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg thumbnail extraction failed: {result.stderr}")
                return None

            # Verify output file was created
            if not Path(output_path).exists():
                logger.error(f"Thumbnail file was not created: {output_path}")
                return None

            logger.debug(f"Generated video thumbnail: {output_path}")
            return output_path

        except subprocess.TimeoutExpired:
            logger.error(f"ffmpeg timed out extracting thumbnail from {video_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract thumbnail from {video_path}: {e}")
            return None

    async def extract_frames_for_detection(
        self,
        video_path: str,
        interval_seconds: float = 2.0,
        max_frames: int = 30,
        size: tuple[int, int] | None = None,
    ) -> list[str]:
        """Extract multiple frames from a video at regular intervals for object detection.

        This method extracts frames at specified intervals throughout the video
        for use in object detection. Frames are saved as temporary JPEG files.

        Args:
            video_path: Path to the video file
            interval_seconds: Time between frame extractions (default: 2.0 seconds)
            max_frames: Maximum number of frames to extract (default: 30)
            size: Optional frame dimensions. If None, uses original resolution.

        Returns:
            List of paths to extracted frame images
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError as e:
            logger.error(f"Video path validation failed: {e}")
            return []

        try:
            # Get video duration
            metadata = await self.get_video_metadata(video_path)
            duration = metadata.get("duration", 0)

            if duration <= 0:
                logger.warning(f"Video has no duration or invalid duration: {video_path}")
                return []

            # Calculate frame timestamps
            timestamps: list[float] = []
            current_time = 0.5  # Start at 0.5 seconds to avoid black frames
            while current_time < duration and len(timestamps) < max_frames:
                timestamps.append(current_time)
                current_time += interval_seconds

            if not timestamps:
                # Video too short, extract at least one frame at 10% into video
                timestamps = [min(0.5, duration * 0.1)]

            logger.info(
                f"Extracting {len(timestamps)} frames from {video_path} "
                f"(duration: {duration:.1f}s, interval: {interval_seconds}s)"
            )

            # Create output directory for frames
            video_stem = validated_path.stem
            frames_dir = self.output_dir / f"{video_stem}_frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            extracted_frames: list[str] = []

            # Build scale filter if size is specified
            scale_filter = ""
            if size:
                scale_filter = f"-vf scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease"

            # Extract frames in parallel using ffmpeg
            # Use a single ffmpeg command to extract all frames efficiently
            for idx, timestamp in enumerate(timestamps):
                output_path = frames_dir / f"frame_{idx:04d}.jpg"

                cmd = [
                    "ffmpeg",
                    "-y",  # Overwrite output file
                    "-ss",
                    str(timestamp),  # Seek to timestamp
                    "-i",
                    str(validated_path),  # Input file
                    "-vframes",
                    "1",  # Extract only 1 frame
                ]

                if scale_filter:
                    cmd.extend(["-vf", scale_filter[4:]])  # Remove "-vf " prefix

                cmd.extend(
                    [
                        "-q:v",
                        "2",  # High quality JPEG
                        str(output_path),
                    ]
                )

                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0 and output_path.exists():
                    extracted_frames.append(str(output_path))
                else:
                    logger.warning(
                        f"Failed to extract frame at {timestamp}s from {video_path}: "
                        f"{result.stderr}"
                    )

            logger.info(f"Successfully extracted {len(extracted_frames)} frames from {video_path}")
            return extracted_frames

        except VideoProcessingError as e:
            logger.error(f"Video processing error for {video_path}: {e}")
            return []
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout extracting frames from {video_path}")
            return []
        except Exception as e:
            logger.error(f"Failed to extract frames from {video_path}: {e}")
            return []

    def cleanup_extracted_frames(self, video_path: str) -> bool:
        """Clean up extracted frames directory for a video.

        Args:
            video_path: Path to the original video file

        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            video_stem = Path(video_path).stem
            frames_dir = self.output_dir / f"{video_stem}_frames"
            if frames_dir.exists():
                import shutil

                shutil.rmtree(frames_dir)
                logger.debug(f"Cleaned up frames directory: {frames_dir}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cleanup frames for {video_path}: {e}")
            return False

    async def extract_thumbnail_for_detection(
        self,
        video_path: str,
        detection_id: str | int,
        size: tuple[int, int] = DEFAULT_THUMBNAIL_SIZE,
    ) -> str | None:
        """Extract thumbnail for a detection record.

        Convenience method that generates a standardized thumbnail path
        based on the detection ID.

        Args:
            video_path: Path to the video file
            detection_id: Detection ID for naming the thumbnail
            size: Thumbnail dimensions as (width, height)

        Returns:
            Path to the saved thumbnail, or None if extraction failed
        """
        output_path = str(self.output_dir / f"{detection_id}_video_thumb.jpg")
        return await self.extract_thumbnail(video_path, output_path, size=size)

    def get_output_path(self, detection_id: str | int) -> Path:
        """Get output path for a detection video thumbnail.

        Args:
            detection_id: Detection ID

        Returns:
            Path object for thumbnail file
        """
        return self.output_dir / f"{detection_id}_video_thumb.jpg"

    def delete_thumbnail(self, detection_id: str | int) -> bool:
        """Delete a video thumbnail file.

        Args:
            detection_id: Detection ID

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            thumbnail_path = self.get_output_path(detection_id)
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                logger.debug(f"Deleted video thumbnail: {thumbnail_path}")
                return True
            else:
                logger.warning(f"Video thumbnail not found: {thumbnail_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete video thumbnail for {detection_id}: {e}")
            return False
