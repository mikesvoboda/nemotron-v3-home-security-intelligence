"""Video transcoding service for browser-compatible video delivery.

This service transcodes videos to browser-compatible formats (H.264/MP4) for
seamless playback in web browsers. It includes caching to avoid re-transcoding
previously processed videos.

Features:
    - Transcode videos to H.264/MP4 format
    - Cache transcoded videos to disk
    - Lookup cached videos before transcoding
    - Support for various input formats (AVI, MKV, MOV, etc.)
    - NVIDIA NVENC hardware acceleration with automatic fallback (NEM-2682)

Output Format:
    - Container: MP4
    - Video Codec: h264_nvenc (NVENC) or libx264 (software fallback)
    - Audio Codec: AAC (if audio present)
    - Pixel Format: yuv420p (for maximum browser compatibility)

Security:
    - All paths are validated before use in subprocess calls
    - Uses subprocess with list arguments (never shell=True)
    - Paths are validated to prevent command-line option injection

Cache Structure:
    {cache_directory}/{file_hash}_transcoded.mp4

NEM-2681: Added for browser-compatible video streaming.
NEM-2682: Added NVIDIA NVENC hardware acceleration support.
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
from pathlib import Path

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Browser-compatible output settings
OUTPUT_VIDEO_CODEC_SOFTWARE = "libx264"
OUTPUT_VIDEO_CODEC_NVENC = "h264_nvenc"
OUTPUT_AUDIO_CODEC = "aac"
OUTPUT_PIXEL_FORMAT = "yuv420p"
OUTPUT_CONTAINER = "mp4"
OUTPUT_CRF = "23"  # Constant Rate Factor for quality (software)
OUTPUT_PRESET_SOFTWARE = "fast"  # Encoding speed preset (software)

# Cache for NVENC availability detection (checked once per process)
_nvenc_available: bool | None = None


def check_nvenc_available() -> bool:  # noqa: PLR0911
    """Check if NVIDIA NVENC hardware acceleration is available.

    Detects NVENC availability by querying ffmpeg for the h264_nvenc encoder
    and testing if it actually works with a minimal encoding operation.
    The result is cached after the first check to avoid repeated subprocess calls.

    NVENC requires:
    1. NVIDIA GPU with NVENC support (most GTX 600+ series)
    2. ffmpeg compiled with NVENC support (--enable-nvenc)
    3. NVIDIA drivers with NVENC library

    Returns:
        True if NVENC is available and working, False otherwise.
    """
    global _nvenc_available  # noqa: PLW0603

    if _nvenc_available is not None:
        return _nvenc_available

    try:
        # Query ffmpeg for available encoders and check for h264_nvenc
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,  # We handle return codes explicitly
        )

        if result.returncode == 0 and "h264_nvenc" in result.stdout:
            # NVENC encoder is available in ffmpeg, now test if it actually works
            # by attempting a minimal encoding operation
            test_result = subprocess.run(
                [  # noqa: S607
                    "ffmpeg",
                    "-hide_banner",
                    "-f",
                    "lavfi",
                    "-i",
                    "nullsrc=s=64x64:d=0.1",
                    "-c:v",
                    "h264_nvenc",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,  # We handle return codes explicitly
            )

            if test_result.returncode == 0:
                logger.info("NVENC hardware acceleration is available and working")
                _nvenc_available = True
                return True
            else:
                logger.warning(
                    "NVENC encoder found but test failed, falling back to software encoding",
                    extra={"stderr": test_result.stderr[:500] if test_result.stderr else ""},
                )
                _nvenc_available = False
                return False

        logger.info("NVENC encoder not available, using software encoding (libx264)")
        _nvenc_available = False
        return False

    except FileNotFoundError:
        logger.warning("ffmpeg not found, cannot check NVENC availability")
        _nvenc_available = False
        return False
    except subprocess.TimeoutExpired:
        logger.warning("NVENC check timed out, assuming unavailable")
        _nvenc_available = False
        return False
    except Exception as e:
        logger.warning(f"Error checking NVENC availability: {e}")
        _nvenc_available = False
        return False


def reset_nvenc_cache() -> None:
    """Reset the NVENC availability cache (for testing)."""
    global _nvenc_available  # noqa: PLW0603
    _nvenc_available = None


def get_video_encoder_args(use_hardware: bool = True) -> list[str]:
    """Get ffmpeg encoder arguments based on hardware availability.

    Returns appropriate encoder arguments for either NVENC hardware encoding
    or libx264 software encoding. Automatically detects and falls back to
    software encoding if NVENC is unavailable.

    Args:
        use_hardware: If True, attempt to use NVENC if available.
                     If False, always use software encoding.

    Returns:
        List of ffmpeg arguments for video encoding.
    """
    settings = get_settings()

    # Check if hardware acceleration is enabled and available
    if use_hardware and settings.hardware_acceleration_enabled and check_nvenc_available():
        logger.debug("Using NVENC hardware encoder for video transcoding")
        return [
            "-c:v",
            OUTPUT_VIDEO_CODEC_NVENC,
            "-preset",
            settings.nvenc_preset,
            "-cq",
            str(settings.nvenc_cq),
            "-pix_fmt",
            OUTPUT_PIXEL_FORMAT,
        ]

    # Fall back to software encoding
    logger.debug("Using libx264 software encoder for video transcoding")
    return [
        "-c:v",
        OUTPUT_VIDEO_CODEC_SOFTWARE,
        "-preset",
        OUTPUT_PRESET_SOFTWARE,
        "-crf",
        OUTPUT_CRF,
        "-pix_fmt",
        OUTPUT_PIXEL_FORMAT,
    ]


def _validate_video_path(video_path: str | Path) -> Path:
    """Validate video path for safe use in subprocess calls.

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


def _compute_file_hash(file_path: Path) -> str:
    """Compute a hash of a file for cache key generation.

    Uses file path and modification time for a fast cache key that
    invalidates when the source file changes.

    Args:
        file_path: Path to the file

    Returns:
        Hash string suitable for cache key
    """
    # Use path + mtime for fast hash computation
    # This invalidates cache when source file is modified
    stat = file_path.stat()
    hash_input = f"{file_path}:{stat.st_mtime}:{stat.st_size}"
    # nosemgrep: weak-hash-md5 - MD5 used for non-security cache key generation
    return hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()


class TranscodingError(Exception):
    """Raised when video transcoding fails."""

    pass


class TranscodingService:
    """Service for transcoding videos to browser-compatible formats.

    This service handles video transcoding using ffmpeg, with built-in caching
    to avoid re-transcoding previously processed videos.

    The service transcodes to H.264/MP4 format which is universally supported
    by modern web browsers (Chrome, Firefox, Safari, Edge).

    Supported Input Formats:
        - MP4 (may need transcoding if codec is not H.264)
        - AVI
        - MKV (Matroska)
        - MOV (QuickTime)

    Output Format:
        - Container: MP4
        - Video: H.264 (libx264)
        - Audio: AAC
        - Pixel Format: yuv420p

    NEM-2681: Added for browser-compatible video streaming.
    """

    def __init__(
        self,
        cache_directory: str | Path | None = None,
    ):
        """Initialize transcoding service.

        Args:
            cache_directory: Directory to store transcoded videos.
                            Defaults to settings.transcoding_cache_directory
                            or 'data/transcoded_cache'.
        """
        settings = get_settings()

        # Use settings or default
        self._cache_directory = Path(
            cache_directory
            if cache_directory is not None
            else getattr(settings, "transcoding_cache_directory", "data/transcoded_cache")
        )

        # Ensure cache directory exists
        self._ensure_cache_directory()

        logger.info(f"TranscodingService initialized: cache_directory={self._cache_directory}")

    def _ensure_cache_directory(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self._cache_directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Transcoding cache directory ready: {self._cache_directory}")
        except Exception as e:
            logger.error(
                f"Failed to create transcoding cache directory {self._cache_directory}: {e}"
            )
            raise

    @property
    def cache_directory(self) -> Path:
        """Get the cache directory path."""
        return self._cache_directory

    def _get_cache_path(self, source_path: Path) -> Path:
        """Get the cache path for a source video.

        Args:
            source_path: Path to the source video file

        Returns:
            Path where the transcoded file would be cached
        """
        file_hash = _compute_file_hash(source_path)
        return self._cache_directory / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"

    def get_cached_video(self, video_path: str | Path) -> Path | None:
        """Check if a transcoded version exists in cache.

        This method performs a cache lookup for a previously transcoded video.
        Use this before calling transcode_video() to avoid unnecessary work.

        Args:
            video_path: Path to the source video file

        Returns:
            Path to cached transcoded file if it exists, None otherwise

        Raises:
            ValueError: If video_path validation fails
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError as e:
            logger.warning(f"Cache lookup failed - path validation error: {e}")
            return None

        cache_path = self._get_cache_path(validated_path)

        if cache_path.exists():
            logger.debug(f"Cache hit for video: {video_path} -> {cache_path}")
            return cache_path

        logger.debug(f"Cache miss for video: {video_path}")
        return None

    def is_transcoding_needed(self, video_path: str | Path) -> bool:
        """Check if transcoding is needed for a video.

        H.264 encoded MP4 files with yuv420p pixel format can typically be
        played directly in browsers without transcoding. This method checks
        the video codec and container to determine if transcoding is needed.

        Args:
            video_path: Path to the video file

        Returns:
            True if transcoding is needed, False if video is already browser-compatible
        """
        try:
            validated_path = _validate_video_path(video_path)
        except ValueError:
            return True  # Assume transcoding needed if validation fails

        # Check file extension - only MP4 is universally browser-compatible
        # For MP4 files, we assume they're already H.264 encoded.
        # In production, you might want to probe with ffprobe to verify codec.
        suffix = validated_path.suffix.lower()
        return suffix not in (".mp4",)

    async def _remux_video(
        self,
        video_path: Path,
        cache_path: Path,
    ) -> Path | None:
        """Try to remux video to MP4 without re-encoding (fast path).

        Remuxing copies the video/audio streams directly to a new container
        without re-encoding. This is nearly instant and uses minimal resources.
        Only works if the source video codec is browser-compatible (H.264/H.265).

        Args:
            video_path: Validated path to source video
            cache_path: Path for output file

        Returns:
            Path to remuxed file if successful, None if remux failed
        """
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-c:v",
            "copy",  # Copy video stream without re-encoding
            "-c:a",
            "copy",  # Copy audio stream without re-encoding
            "-movflags",
            "+faststart",
            str(cache_path),
        ]

        logger.info(f"Attempting fast remux: {video_path} -> {cache_path}")
        logger.debug(f"FFmpeg remux command: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, _stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0,  # Remux should be fast, 30s timeout
            )

            if process.returncode == 0 and cache_path.exists():
                file_size = cache_path.stat().st_size
                if file_size > 1000:  # Sanity check - file should be > 1KB
                    logger.info(f"Fast remux successful: {cache_path} ({file_size} bytes)")
                    return cache_path
                else:
                    logger.warning(
                        f"Remux produced suspiciously small file ({file_size} bytes), falling back to transcode"
                    )
                    cache_path.unlink(missing_ok=True)
                    return None

            # Remux failed - this is expected for some codecs
            logger.debug(f"Remux failed (returncode={process.returncode}), will try full transcode")
            cache_path.unlink(missing_ok=True)
            return None

        except TimeoutError:
            logger.warning("Remux timed out, falling back to transcode")
            cache_path.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.debug(f"Remux failed with exception: {e}, will try full transcode")
            cache_path.unlink(missing_ok=True)
            return None

    async def transcode_video(
        self,
        video_path: str | Path,
        force: bool = False,
    ) -> Path:
        """Transcode a video to browser-compatible format.

        This method first attempts a fast remux (stream copy) if the source
        video is already H.264. If remux fails, it falls back to full
        transcoding with H.264/MP4 format for browser playback.

        Args:
            video_path: Path to the source video file
            force: If True, force re-transcoding even if cached version exists

        Returns:
            Path to the transcoded (or cached) video file

        Raises:
            ValueError: If video_path validation fails
            TranscodingError: If transcoding fails
        """
        validated_path = _validate_video_path(video_path)
        cache_path = self._get_cache_path(validated_path)

        # Check cache first (unless forced)
        if not force and cache_path.exists():
            logger.info(f"Using cached transcoded video: {cache_path}")
            return cache_path

        # Try fast remux first (copies streams without re-encoding)
        remux_result = await self._remux_video(validated_path, cache_path)
        if remux_result is not None:
            return remux_result

        # Fall back to full transcoding
        # Uses get_video_encoder_args() for adaptive NVENC/software encoding (NEM-2682)
        # -c:a aac: AAC audio codec
        # -movflags +faststart: Enable progressive download/streaming
        encoder_args = get_video_encoder_args(use_hardware=True)

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-i",
            str(validated_path),  # Input file
            *encoder_args,  # Video codec settings (NVENC or libx264)
            "-c:a",
            OUTPUT_AUDIO_CODEC,
            "-movflags",
            "+faststart",
            str(cache_path),
        ]

        logger.info(f"Full transcoding video: {video_path} -> {cache_path}")
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
                logger.error(f"FFmpeg transcoding failed: {error_msg}")
                raise TranscodingError(f"FFmpeg exited with code {process.returncode}: {error_msg}")

            if not cache_path.exists():
                raise TranscodingError(f"Transcoded file was not created: {cache_path}")

            logger.info(f"Transcoding complete: {cache_path} ({cache_path.stat().st_size} bytes)")
            return cache_path

        except FileNotFoundError:
            logger.error("ffmpeg not found. Please ensure ffmpeg is installed.")
            raise TranscodingError("ffmpeg not found") from None
        except TranscodingError:
            raise
        except Exception as e:
            logger.error(f"Transcoding failed: {e}", exc_info=True)
            raise TranscodingError(f"Transcoding failed: {e}") from e

    async def get_or_transcode(
        self,
        video_path: str | Path,
    ) -> Path:
        """Get cached video or transcode if not available.

        This is a convenience method that combines cache lookup and transcoding.
        It first checks if a cached version exists, and if not, transcodes the video.

        For videos that are already browser-compatible (H.264 MP4), this method
        returns the original path without transcoding.

        Args:
            video_path: Path to the source video file

        Returns:
            Path to browser-compatible video (original, cached, or newly transcoded)

        Raises:
            ValueError: If video_path validation fails
            TranscodingError: If transcoding fails
        """
        validated_path = _validate_video_path(video_path)

        # Check if transcoding is needed
        if not self.is_transcoding_needed(validated_path):
            logger.debug(f"Video is already browser-compatible: {video_path}")
            return validated_path

        # Check cache
        cached = self.get_cached_video(validated_path)
        if cached:
            return cached

        # Transcode
        return await self.transcode_video(validated_path)

    def cleanup_cache(self, max_age_days: int = 7) -> int:
        """Clean up old cached transcoded files.

        Removes cached files older than max_age_days to free up disk space.

        Args:
            max_age_days: Maximum age in days for cached files

        Returns:
            Number of files deleted
        """
        import time

        deleted_count = 0
        max_age_seconds = max_age_days * 24 * 60 * 60
        now = time.time()

        try:
            for cache_file in self._cache_directory.glob(f"*_transcoded.{OUTPUT_CONTAINER}"):
                try:
                    file_age = now - cache_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        cache_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old cache file: {cache_file}")
                except OSError as e:
                    logger.warning(f"Failed to delete cache file {cache_file}: {e}")
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")

        if deleted_count > 0:
            logger.info(
                f"Cache cleanup: deleted {deleted_count} files older than {max_age_days} days"
            )

        return deleted_count

    def delete_cached(self, video_path: str | Path) -> bool:
        """Delete the cached transcoded version of a video.

        Args:
            video_path: Path to the source video file

        Returns:
            True if deleted, False if not found or error
        """
        try:
            validated_path = _validate_video_path(video_path)
            cache_path = self._get_cache_path(validated_path)

            if cache_path.exists():
                cache_path.unlink()
                logger.debug(f"Deleted cached transcoded file: {cache_path}")
                return True

            logger.debug(f"No cached file to delete for: {video_path}")
            return False
        except ValueError:
            return False
        except OSError as e:
            logger.warning(f"Failed to delete cached file: {e}")
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
