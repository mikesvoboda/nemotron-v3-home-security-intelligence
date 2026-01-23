"""Video processor service for extracting metadata and thumbnails from video files.

This service handles video file processing including:
- Extracting video metadata (duration, codec, resolution)
- Generating thumbnail frames from videos
- Validating video file integrity

Uses ffmpeg subprocess for reliable cross-platform video processing.

Error Handling Pattern:
    This module uses a consistent error handling strategy based on operation criticality:

    1. REQUIRED operations (data must be available) -> raise VideoProcessingError
       - get_video_metadata(): Raises VideoProcessingError if extraction fails
       These are operations where callers cannot proceed without the result.

    2. OPTIONAL operations (best-effort) -> return None/False/empty list
       - extract_thumbnail() -> str | None
       - extract_thumbnail_for_detection() -> str | None
       - extract_frames_for_detection() -> list[str] (empty on failure) [DEPRECATED]
       - extract_frames_for_detection_batch() -> list[str] (empty on failure) [PREFERRED]
       - cleanup_extracted_frames() -> bool
       - delete_thumbnail() -> bool
       These are operations where callers can proceed with a fallback behavior.

    For frame extraction, use extract_frames_for_detection_batch() (single FFmpeg call)
    instead of extract_frames_for_detection() (multiple FFmpeg calls) for better performance.

    Callers should:
    - Use try/except for get_video_metadata()
    - Check return values for other methods (if result is None/False/empty: handle gracefully)

Example:
    try:
        metadata = await processor.get_video_metadata(video_path)
    except VideoProcessingError as e:
        logger.error(f"Cannot get metadata: {e}")
        return

    thumbnail = await processor.extract_thumbnail(video_path)
    if thumbnail is None:
        logger.warning("Using fallback thumbnail")
        thumbnail = DEFAULT_THUMBNAIL
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


def _validate_timestamp(timestamp: float) -> float:
    """Validate timestamp for safe use in ffmpeg commands.

    Args:
        timestamp: Timestamp in seconds

    Returns:
        Validated timestamp as float

    Raises:
        ValueError: If timestamp is invalid or out of bounds
    """
    if not isinstance(timestamp, int | float):
        raise ValueError(f"Timestamp must be a number, got {type(timestamp).__name__}")
    timestamp = float(timestamp)
    # Reasonable bounds: 0 to 24 hours (86400 seconds)
    if timestamp < 0 or timestamp > 86400:
        raise ValueError(f"Timestamp must be between 0 and 86400 seconds, got {timestamp}")
    return timestamp


def _validate_size(size: tuple[int, int]) -> tuple[int, int]:
    """Validate size tuple for safe use in ffmpeg scale filter.

    Args:
        size: Tuple of (width, height) in pixels

    Returns:
        Validated size tuple

    Raises:
        ValueError: If size values are invalid or out of bounds
    """
    if not isinstance(size, tuple) or len(size) != 2:
        raise ValueError(f"Size must be a tuple of (width, height), got {type(size).__name__}")
    width, height = size
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError("Size dimensions must be integers")
    # Reasonable bounds: 1 to 8K resolution
    if not (1 <= width <= 7680) or not (1 <= height <= 4320):
        raise ValueError(f"Size dimensions must be between 1 and 7680x4320, got {width}x{height}")
    return (width, height)


def _validate_interval_seconds(interval_seconds: float) -> float:
    """Validate interval for frame extraction.

    Args:
        interval_seconds: Time between frame extractions in seconds

    Returns:
        Validated interval as float

    Raises:
        ValueError: If interval is invalid or out of bounds
    """
    if not isinstance(interval_seconds, int | float):
        raise ValueError(f"Interval must be a number, got {type(interval_seconds).__name__}")
    interval_seconds = float(interval_seconds)
    # Reasonable bounds: 0.1 seconds to 1 hour
    if interval_seconds < 0.1 or interval_seconds > 3600:
        raise ValueError(f"Interval must be between 0.1 and 3600 seconds, got {interval_seconds}")
    return interval_seconds


def _validate_max_frames(max_frames: int) -> int:
    """Validate maximum frames for extraction.

    Args:
        max_frames: Maximum number of frames to extract

    Returns:
        Validated max_frames as int

    Raises:
        ValueError: If max_frames is invalid or out of bounds
    """
    if not isinstance(max_frames, int):
        raise ValueError(f"max_frames must be an integer, got {type(max_frames).__name__}")
    # Reasonable bounds: 1 to 1000 frames
    if max_frames < 1 or max_frames > 1000:
        raise ValueError(f"max_frames must be between 1 and 1000, got {max_frames}")
    return max_frames


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

    Error Handling:
        See module docstring for the error handling pattern. In summary:
        - get_video_metadata() raises VideoProcessingError on failure
        - All other methods return None/False/empty list on failure
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

    async def extract_thumbnail(  # noqa: PLR0911
        self,
        video_path: str,
        output_path: str | None = None,
        timestamp: float | None = None,
        size: tuple[int, int] = DEFAULT_THUMBNAIL_SIZE,
    ) -> str | None:
        """Extract a thumbnail frame from a video (best-effort, returns None on failure).

        By default, extracts frame at 1 second or 10% into the video, whichever
        is smaller. This helps avoid black/blank frames at the start.

        This is an OPTIONAL operation that returns None on failure rather than
        raising an exception. Callers should check for None and handle gracefully.

        Args:
            video_path: Path to the video file
            output_path: Path to save thumbnail. If None, generates path in output_dir
            timestamp: Timestamp in seconds to extract frame. If None, uses smart default
            size: Thumbnail dimensions as (width, height). Default: (320, 240)

        Returns:
            Path to the saved thumbnail, or None if extraction failed.
            Returns None for: invalid path, ffmpeg failure, timeout, or file not created.
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError:
            logger.error(
                "Video path validation failed", exc_info=True, extra={"video_path": video_path}
            )
            return None

        # Validate size parameter to prevent command injection
        try:
            validated_size = _validate_size(size)
        except ValueError:
            logger.error("Size validation failed", exc_info=True, extra={"size": size})
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

            # Validate timestamp parameter to prevent command injection
            validated_timestamp = _validate_timestamp(timestamp)

            # Generate output path if not provided
            if output_path is None:
                video_stem = validated_path.stem
                output_path = str(self.output_dir / f"{video_stem}_thumb.jpg")

            # Build ffmpeg command for thumbnail extraction
            # Note: -ss is placed AFTER -i for accurate seeking (output seeking mode)
            # This is more accurate than input seeking (-ss before -i) especially for
            # videos with low frame rates or when seeking near the end of the video.
            # The format=yuvj420p filter converts limited-range YUV to full-range,
            # which is required for JPEG encoding to avoid "Non full-range YUV" errors.
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-i",
                str(validated_path),  # Input file
                "-ss",
                str(validated_timestamp),  # Seek to timestamp (output seeking)
                "-vframes",
                "1",  # Extract only 1 frame
                "-vf",
                f"format=yuvj420p,scale={validated_size[0]}:{validated_size[1]}:force_original_aspect_ratio=decrease,pad={validated_size[0]}:{validated_size[1]}:(ow-iw)/2:(oh-ih)/2",  # Convert to full-range YUV, scale with padding
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
                logger.error(
                    "ffmpeg thumbnail extraction failed",
                    extra={"stderr": result.stderr, "video_path": video_path},
                )
                return None

            # Verify output file was created
            if not Path(output_path).exists():
                logger.error(f"Thumbnail file was not created: {output_path}")
                return None

            logger.debug(f"Generated video thumbnail: {output_path}")
            return output_path

        except subprocess.TimeoutExpired:
            logger.error(
                "ffmpeg timed out extracting thumbnail",
                exc_info=True,
                extra={"video_path": video_path},
            )
            return None
        except Exception:
            logger.error(
                "Failed to extract thumbnail", exc_info=True, extra={"video_path": video_path}
            )
            return None

    async def extract_frames_for_detection(  # noqa: PLR0911
        self,
        video_path: str,
        interval_seconds: float = 2.0,
        max_frames: int = 30,
        size: tuple[int, int] | None = None,
    ) -> list[str]:
        """Extract multiple frames from a video at regular intervals for object detection.

        DEPRECATED: Use extract_frames_for_detection_batch() instead for better performance.
        This method invokes FFmpeg once per frame, which is slower than the batch method
        that uses a single FFmpeg invocation with the fps filter.

        Kept for backwards compatibility and cases where per-frame control is needed.

        This method extracts frames at specified intervals throughout the video
        for use in object detection. Frames are saved as temporary JPEG files.

        This is an OPTIONAL operation that returns an empty list on failure rather
        than raising an exception. Callers should handle empty results gracefully.

        Args:
            video_path: Path to the video file
            interval_seconds: Time between frame extractions (default: 2.0 seconds)
            max_frames: Maximum number of frames to extract (default: 30)
            size: Optional frame dimensions. If None, uses original resolution.

        Returns:
            List of paths to extracted frame images.
            Returns empty list for: invalid path, metadata extraction failure,
            invalid duration, ffmpeg failures, or timeouts.

        See Also:
            extract_frames_for_detection_batch: Optimized method using single FFmpeg invocation
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError:
            logger.error(
                "Video path validation failed", exc_info=True, extra={"video_path": video_path}
            )
            return []

        # Validate interval_seconds and max_frames to prevent command injection
        try:
            validated_interval = _validate_interval_seconds(interval_seconds)
        except ValueError:
            logger.error(
                "Interval validation failed",
                exc_info=True,
                extra={"interval_seconds": interval_seconds},
            )
            return []

        try:
            validated_max_frames = _validate_max_frames(max_frames)
        except ValueError:
            logger.error(
                "Max frames validation failed", exc_info=True, extra={"max_frames": max_frames}
            )
            return []

        # Validate size if provided
        validated_size: tuple[int, int] | None = None
        if size is not None:
            try:
                validated_size = _validate_size(size)
            except ValueError:
                logger.error("Size validation failed", exc_info=True, extra={"size": size})
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
            while current_time < duration and len(timestamps) < validated_max_frames:
                timestamps.append(current_time)
                current_time += validated_interval

            if not timestamps:
                # Video too short, extract at least one frame at 10% into video
                timestamps = [min(0.5, duration * 0.1)]

            logger.info(
                f"Extracting {len(timestamps)} frames from {video_path} "
                f"(duration: {duration:.1f}s, interval: {validated_interval}s)"
            )

            # Create output directory for frames
            video_stem = validated_path.stem
            frames_dir = self.output_dir / f"{video_stem}_frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            extracted_frames: list[str] = []

            # Build video filter chain
            # format=yuvj420p: Convert to full-range YUV for JPEG encoding
            # This prevents "Non full-range YUV is non-standard" errors on some videos
            video_filters = ["format=yuvj420p"]
            if validated_size:
                video_filters.append(
                    f"scale={validated_size[0]}:{validated_size[1]}:force_original_aspect_ratio=decrease"
                )
            vf_arg = ",".join(video_filters)

            # Extract frames using ffmpeg
            # Note: -ss is placed AFTER -i for accurate seeking (output seeking mode)
            # This is more reliable than input seeking (-ss before -i) especially for
            # videos with low frame rates or when seeking near the end of the video.
            for idx, timestamp in enumerate(timestamps):
                output_path = frames_dir / f"frame_{idx:04d}.jpg"

                cmd = [
                    "ffmpeg",
                    "-y",  # Overwrite output file
                    "-i",
                    str(validated_path),  # Input file
                    "-ss",
                    str(timestamp),  # Seek to timestamp (output seeking)
                    "-vframes",
                    "1",  # Extract only 1 frame
                    "-vf",
                    vf_arg,  # Video filters (format conversion + optional scaling)
                    "-q:v",
                    "2",  # High quality JPEG
                    str(output_path),
                ]

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

        except VideoProcessingError:
            logger.error("Video processing error", exc_info=True, extra={"video_path": video_path})
            return []
        except subprocess.TimeoutExpired:
            logger.error(
                "Timeout extracting frames", exc_info=True, extra={"video_path": video_path}
            )
            return []
        except Exception:
            logger.error(
                "Failed to extract frames", exc_info=True, extra={"video_path": video_path}
            )
            return []

    async def extract_frames_for_detection_batch(  # noqa: PLR0911
        self,
        video_path: str,
        interval_seconds: float = 2.0,
        max_frames: int = 30,
        size: tuple[int, int] | None = None,
    ) -> list[str]:
        """Extract multiple frames from a video using a single FFmpeg call.

        NEM-1062: Optimized batch frame extraction using FFmpeg's select filter.
        This method extracts all frames in a single FFmpeg invocation instead of
        calling FFmpeg once per frame, significantly reducing subprocess overhead.

        Uses the -vf select filter with FPS filter to extract frames at regular
        intervals throughout the video for use in object detection.

        This is an OPTIONAL operation that returns an empty list on failure rather
        than raising an exception. Callers should handle empty results gracefully.

        Args:
            video_path: Path to the video file
            interval_seconds: Time between frame extractions (default: 2.0 seconds)
            max_frames: Maximum number of frames to extract (default: 30)
            size: Optional frame dimensions. If None, uses original resolution.

        Returns:
            List of paths to extracted frame images.
            Returns empty list for: invalid path, metadata extraction failure,
            invalid duration, ffmpeg failures, or timeouts.
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError:
            logger.error(
                "Video path validation failed", exc_info=True, extra={"video_path": video_path}
            )
            return []

        # Validate interval_seconds and max_frames to prevent command injection
        try:
            validated_interval = _validate_interval_seconds(interval_seconds)
        except ValueError:
            logger.error(
                "Interval validation failed",
                exc_info=True,
                extra={"interval_seconds": interval_seconds},
            )
            return []

        try:
            validated_max_frames = _validate_max_frames(max_frames)
        except ValueError:
            logger.error(
                "Max frames validation failed", exc_info=True, extra={"max_frames": max_frames}
            )
            return []

        # Validate size if provided
        validated_size: tuple[int, int] | None = None
        if size is not None:
            try:
                validated_size = _validate_size(size)
            except ValueError:
                logger.error("Size validation failed", exc_info=True, extra={"size": size})
                return []

        try:
            # Get video duration
            metadata = await self.get_video_metadata(video_path)
            duration = metadata.get("duration", 0)

            if duration <= 0:
                logger.warning(f"Video has no duration or invalid duration: {video_path}")
                return []

            # Calculate how many frames to extract
            num_frames = min(validated_max_frames, int((duration - 0.5) / validated_interval) + 1)
            if num_frames <= 0:
                # Video too short, extract at least one frame
                num_frames = 1

            logger.info(
                f"Batch extracting {num_frames} frames from {video_path} "
                f"(duration: {duration:.1f}s, interval: {validated_interval}s)"
            )

            # Create output directory for frames
            video_stem = validated_path.stem
            frames_dir = self.output_dir / f"{video_stem}_frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            # Build video filter chain for batch extraction
            # Uses fps filter to control frame rate, then select to limit frames
            # format=yuvj420p: Convert to full-range YUV for JPEG encoding
            # fps=1/interval: Extract one frame every 'interval' seconds
            # setpts=N/FRAME_RATE/TB: Reset timestamps for proper frame ordering
            video_filters = ["format=yuvj420p"]

            # Use fps filter to extract at regular intervals
            # fps=1/interval extracts 1 frame per interval seconds
            video_filters.append(f"fps=1/{validated_interval}")

            # Apply scale filter if size is specified
            if validated_size:
                video_filters.append(
                    f"scale={validated_size[0]}:{validated_size[1]}:force_original_aspect_ratio=decrease"
                )

            vf_arg = ",".join(video_filters)

            # Output pattern for numbered frames
            output_pattern = str(frames_dir / "%04d.jpg")

            # Build single FFmpeg command for batch extraction
            # Note: We use -ss to skip the first 0.5 seconds to avoid black frames
            # -frames:v limits the total number of extracted frames
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output files
                "-ss",
                "0.5",  # Skip first 0.5 seconds (input seeking for speed)
                "-i",
                str(validated_path),  # Input file
                "-vf",
                vf_arg,  # Video filters (fps extraction + format + optional scaling)
                "-frames:v",
                str(num_frames),  # Limit number of output frames
                "-q:v",
                "2",  # High quality JPEG
                output_pattern,  # Output file pattern
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # Longer timeout for batch operation
            )

            if result.returncode != 0:
                logger.error(
                    "FFmpeg batch frame extraction failed",
                    extra={"stderr": result.stderr, "video_path": video_path},
                )
                return []

            # Collect extracted frame paths
            # FFmpeg outputs frames as 0001.jpg, 0002.jpg, etc.
            extracted_frames: list[str] = []
            for i in range(1, num_frames + 1):
                frame_path = frames_dir / f"{i:04d}.jpg"
                if frame_path.exists():
                    extracted_frames.append(str(frame_path))

            logger.info(
                f"Successfully batch extracted {len(extracted_frames)} frames from {video_path}"
            )
            return extracted_frames

        except VideoProcessingError:
            logger.error(
                "Video processing error during batch extraction",
                exc_info=True,
                extra={"video_path": video_path},
            )
            return []
        except subprocess.TimeoutExpired:
            logger.error(
                "Timeout during batch frame extraction",
                exc_info=True,
                extra={"video_path": video_path},
            )
            return []
        except Exception:
            logger.error(
                "Failed to batch extract frames", exc_info=True, extra={"video_path": video_path}
            )
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
        except Exception:
            logger.error(
                "Failed to cleanup frames", exc_info=True, extra={"video_path": video_path}
            )
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
        except Exception:
            logger.error(
                "Failed to delete video thumbnail",
                exc_info=True,
                extra={"detection_id": detection_id},
            )
            return False
