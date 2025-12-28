"""Video processor service for extracting metadata and thumbnails from video files.

This service handles video file processing including:
- Extracting video metadata (duration, codec, resolution)
- Generating thumbnail frames from videos
- Validating video file integrity

Uses ffmpeg subprocess for reliable cross-platform video processing.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default thumbnail extraction settings
DEFAULT_THUMBNAIL_SIZE = (320, 240)
DEFAULT_THUMBNAIL_QUALITY = 85


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
        if not Path(video_path).exists():
            raise VideoProcessingError(f"Video file not found: {video_path}")

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
                video_path,
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
        suffix = Path(video_path).suffix.lower()
        mime_types = {
            ".mp4": "video/mp4",
            ".mkv": "video/x-matroska",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
        }
        return mime_types.get(suffix, "video/mp4")

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
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            logger.error(f"Video file not found: {video_path}")
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
                video_stem = video_path_obj.stem
                output_path = str(self.output_dir / f"{video_stem}_thumb.jpg")

            # Build ffmpeg command for thumbnail extraction
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-ss",
                str(timestamp),  # Seek to timestamp
                "-i",
                video_path,  # Input file
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
