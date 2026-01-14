"""File watcher service for monitoring Foscam camera uploads.

This service watches camera directories for new image and video uploads, validates them,
and queues them for AI processing with debounce logic to prevent duplicate processing.

Supported file types:
- Images: .jpg, .jpeg, .png
- Videos: .mp4, .mkv, .avi, .mov

Idempotency:
-----------
Files are deduplicated using SHA256 content hashes stored in Redis with TTL.
This prevents duplicate processing caused by:
- Watchdog create/modify event bursts
- Service restarts during file processing
- FTP upload retries

The dedupe check happens before enqueueing to Redis, ensuring the same file
content is never processed twice within the TTL window (default 5 minutes).

Camera ID Contract:
------------------
Camera IDs are derived from upload directory names using normalize_camera_id().
This ensures a consistent mapping between filesystem paths and database records:

    Upload path: /export/foscam/Front Door/image.jpg
    -> folder_name: "Front Door"
    -> camera_id: "front_door" (normalized)

When a new upload directory is detected, a Camera record is auto-created if
auto_create_cameras is enabled (default: True).
"""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.observers.polling import PollingObserver

# Observer selection:
# By default, we use watchdog's Observer which auto-selects the best native backend:
#   - Linux: inotify (kernel-level filesystem notifications)
#   - macOS: FSEvents (native filesystem event API)
#   - Windows: ReadDirectoryChangesW (native API)
#
# However, in containerized environments (Docker Desktop/macOS, or NFS/SMB mounts),
# inotify events may not propagate properly. In these cases, enable polling mode
# via the FILE_WATCHER_POLLING environment variable or settings.file_watcher_polling.
from backend.core.config import get_settings
from backend.core.constants import DETECTION_QUEUE
from backend.core.logging import get_logger
from backend.core.metrics import record_pipeline_stage_latency
from backend.core.redis import QueueOverflowPolicy
from backend.models.camera import Camera, normalize_camera_id
from backend.services.dedupe import DedupeService

logger = get_logger(__name__)

# Supported file extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def is_image_file(file_path: str) -> bool:
    """Check if file has a valid image extension.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file has image extension (.jpg, .jpeg, .png)
    """
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS


def is_video_file(file_path: str) -> bool:
    """Check if file has a valid video extension.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file has video extension (.mp4, .mkv, .avi, .mov)
    """
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS


def is_supported_media_file(file_path: str) -> bool:
    """Check if file has a supported media extension (image or video).

    Args:
        file_path: Path to the file to check

    Returns:
        True if file has a supported image or video extension
    """
    return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS


def get_media_type(file_path: str) -> str | None:
    """Get the media type (image or video) for a file.

    Args:
        file_path: Path to the file to check

    Returns:
        "image" for image files, "video" for video files, None for unsupported
    """
    suffix = Path(file_path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    elif suffix in VIDEO_EXTENSIONS:
        return "video"
    return None


# Minimum image file size (10KB) - images smaller than this are likely truncated/corrupt
# A valid JPEG with any meaningful content is typically at least a few KB
MIN_IMAGE_FILE_SIZE = 10 * 1024  # 10KB


def _validate_image_sync(file_path: str) -> bool:
    """Synchronous image validation helper.

    This performs the blocking PIL operations for image validation.
    Should be called via asyncio.to_thread() in async contexts.

    Args:
        file_path: Path to the image file

    Returns:
        True if file is a valid, complete image
    """
    # Try to open and verify image header
    with Image.open(file_path) as img:
        # verify() checks image header but doesn't load pixel data
        img.verify()

    # Re-open and fully load the image to catch truncation
    # verify() only checks headers - truncated files can pass verify() but fail load()
    # Note: We need to re-open because verify() invalidates the image object
    with Image.open(file_path) as img:
        # load() forces PIL to read and decompress all image data
        # This will raise an exception for truncated/corrupt images
        img.load()

    return True


def is_valid_image(file_path: str) -> bool:
    """Validate that file is a valid, non-corrupted image.

    This performs comprehensive validation to catch truncated/corrupt images
    from incomplete FTP uploads:
    1. File exists and is readable
    2. File size is non-zero and above minimum threshold
    3. PIL can verify the image header (basic structure check)
    4. PIL can fully load the image data (catches truncated images)

    Note: This is a synchronous function that blocks on PIL operations.
    For async contexts, use is_valid_image_async() instead.

    Args:
        file_path: Path to the image file

    Returns:
        True if file is a valid, complete image
    """
    try:
        # Check file exists and has content
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return False

        file_size = file_path_obj.stat().st_size

        if file_size == 0:
            logger.warning(f"Empty image file detected: {file_path}")
            return False

        # Check minimum file size - very small images are likely truncated
        if file_size < MIN_IMAGE_FILE_SIZE:
            logger.warning(
                f"Image file too small ({file_size} bytes, minimum {MIN_IMAGE_FILE_SIZE}): {file_path}"
            )
            return False

        return _validate_image_sync(file_path)
    except OSError as e:
        # OSError covers most PIL image errors (truncated, corrupt, etc.)
        logger.warning(f"Image validation failed (corrupt/truncated) {file_path}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Invalid image file {file_path}: {e}")
        return False


async def is_valid_image_async(file_path: str) -> bool:
    """Validate that file is a valid, non-corrupted image asynchronously.

    This is the async version that runs PIL operations in a thread pool
    to avoid blocking the event loop. Use this in async contexts instead
    of is_valid_image().

    Performs comprehensive validation to catch truncated/corrupt images
    from incomplete FTP uploads:
    1. File exists and is readable
    2. File size is non-zero and above minimum threshold
    3. PIL can verify the image header (basic structure check)
    4. PIL can fully load the image data (catches truncated images)

    Args:
        file_path: Path to the image file

    Returns:
        True if file is a valid, complete image
    """
    try:
        # Check file exists and has content (non-blocking stat operations)
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return False

        file_size = file_path_obj.stat().st_size

        if file_size == 0:
            logger.warning(f"Empty image file detected: {file_path}")
            return False

        # Check minimum file size - very small images are likely truncated
        if file_size < MIN_IMAGE_FILE_SIZE:
            logger.warning(
                f"Image file too small ({file_size} bytes, minimum {MIN_IMAGE_FILE_SIZE}): {file_path}"
            )
            return False

        # Run blocking PIL operations in thread pool to avoid blocking event loop
        return await asyncio.to_thread(_validate_image_sync, file_path)
    except OSError as e:
        # OSError covers most PIL image errors (truncated, corrupt, etc.)
        logger.warning(f"Image validation failed (corrupt/truncated) {file_path}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Invalid image file {file_path}: {e}")
        return False


def is_valid_video(file_path: str) -> bool:
    """Validate that file is a valid video with content.

    Note: This performs a basic validation (file exists and has content).
    Full video validation (codec, corruption) is done during processing.

    Args:
        file_path: Path to the video file

    Returns:
        True if file exists and has content
    """
    try:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return False

        # Check file has content (videos should be at least a few KB)
        file_size = file_path_obj.stat().st_size
        if file_size == 0:
            logger.warning(f"Empty video file detected: {file_path}")
            return False

        # Minimum video file size check (1KB minimum)
        if file_size < 1024:
            logger.warning(f"Video file too small ({file_size} bytes): {file_path}")
            return False

        return True
    except Exception as e:
        logger.warning(f"Invalid video file {file_path}: {e}")
        return False


def is_valid_media_file(file_path: str) -> bool:
    """Validate that file is a valid image or video.

    Note: This is a synchronous function that may block on PIL operations.
    For async contexts, use is_valid_media_file_async() instead.

    Args:
        file_path: Path to the media file

    Returns:
        True if file is valid
    """
    if is_image_file(file_path):
        return is_valid_image(file_path)
    elif is_video_file(file_path):
        return is_valid_video(file_path)
    return False


async def is_valid_media_file_async(file_path: str) -> bool:
    """Validate that file is a valid image or video asynchronously.

    This is the async version that runs PIL operations in a thread pool
    to avoid blocking the event loop. Use this in async contexts instead
    of is_valid_media_file().

    Args:
        file_path: Path to the media file

    Returns:
        True if file is valid
    """
    if is_image_file(file_path):
        return await is_valid_image_async(file_path)
    elif is_video_file(file_path):
        return is_valid_video(file_path)
    return False


class FileWatcher:
    """Watches camera directories for new media (image/video) uploads and queues for processing.

    Features:
    - Support for both image and video files
    - Debounce logic to wait for file writes to complete
    - Media file integrity validation before queuing
    - Async-compatible design
    - Graceful shutdown handling
    - Auto-creation of cameras for new upload directories

    Supported formats:
    - Images: .jpg, .jpeg, .png
    - Videos: .mp4, .mkv, .avi, .mov

    Camera ID Contract:
    - Camera IDs are normalized from folder names (e.g., "Front Door" -> "front_door")
    - This ensures consistent mapping between filesystem paths and database records
    - When auto_create_cameras=True, new cameras are created automatically
    """

    def __init__(
        self,
        camera_root: str | None = None,
        redis_client: Any | None = None,
        debounce_delay: float = 0.5,
        queue_name: str = DETECTION_QUEUE,
        dedupe_service: DedupeService | None = None,
        auto_create_cameras: bool = True,
        camera_creator: Callable[[Camera], Any] | None = None,
        use_polling: bool | None = None,
        polling_interval: float | None = None,
        stability_time: float = 2.0,
    ):
        """Initialize file watcher.

        Args:
            camera_root: Root directory containing camera folders (e.g., /export/foscam)
            redis_client: RedisClient instance for queueing detections
            debounce_delay: Delay in seconds to wait after last file modification
            queue_name: Name of Redis queue for detection jobs
            dedupe_service: Optional DedupeService for file deduplication
            auto_create_cameras: If True, auto-create camera records for new directories
            camera_creator: Async callback to create camera in database.
                            Signature: async def creator(camera: Camera) -> None
                            If None, auto-creation is disabled even if auto_create_cameras=True
            use_polling: If True, use PollingObserver instead of native Observer.
                        Enable for Docker Desktop/macOS mounts or network filesystems.
                        If None, reads from settings.file_watcher_polling.
            polling_interval: Polling interval in seconds when using PollingObserver.
                             If None, reads from settings.file_watcher_polling_interval.
            stability_time: Time in seconds that file size must remain unchanged
                           before considering the file stable (for FTP uploads).
                           Default is 2.0 seconds.
        """
        settings = get_settings()
        self.camera_root = camera_root or settings.foscam_base_path
        self.redis_client = redis_client
        self.debounce_delay = debounce_delay
        self.queue_name = queue_name
        self.auto_create_cameras = auto_create_cameras
        self._camera_creator = camera_creator
        self.stability_time = stability_time

        # Track which cameras we've already tried to create (avoid repeated attempts)
        self._known_cameras: set[str] = set()

        # Initialize dedupe service (creates one if not provided and redis is available)
        self._dedupe_service: DedupeService | None = None
        if dedupe_service is not None:
            self._dedupe_service = dedupe_service
        elif redis_client is not None:
            self._dedupe_service = DedupeService(redis_client=redis_client)

        # Determine observer type from parameters or settings
        self._use_polling = (
            use_polling if use_polling is not None else settings.file_watcher_polling
        )
        self._polling_interval = (
            polling_interval
            if polling_interval is not None
            else settings.file_watcher_polling_interval
        )

        # Create watchdog observer for filesystem monitoring
        # Use PollingObserver for Docker Desktop/macOS or network filesystem mounts
        self.observer: BaseObserver
        if self._use_polling:
            self.observer = PollingObserver(timeout=self._polling_interval)
        else:
            self.observer = Observer()

        # Track running state
        self.running = False

        # Debounce tracking: maps file_path -> asyncio.Task
        self._pending_tasks: dict[str, asyncio.Task[None]] = {}

        # Event loop reference (set during start())
        self._loop: asyncio.AbstractEventLoop | None = None

        # Create event handler
        self._event_handler = self._create_event_handler()

        # Log initialization with observer type
        observer_type = "polling" if self._use_polling else "native"
        polling_info = f", interval={self._polling_interval}s" if self._use_polling else ""
        logger.info(
            f"FileWatcher initialized for camera root: {self.camera_root} "
            f"(observer={observer_type}{polling_info}, "
            f"dedupe={'enabled' if self._dedupe_service else 'disabled'}, "
            f"auto_create={'enabled' if auto_create_cameras and camera_creator else 'disabled'})"
        )

    def _create_event_handler(self) -> FileSystemEventHandler:
        """Create watchdog event handler for file system events.

        Returns:
            FileSystemEventHandler instance
        """

        class MediaEventHandler(FileSystemEventHandler):
            """Handle file system events for media files (images and videos)."""

            def __init__(self, watcher: FileWatcher):
                self.watcher = watcher
                super().__init__()

            def on_created(self, event: FileSystemEvent) -> None:
                """Handle file creation events."""
                # Ensure src_path is a string (watchdog can return bytes)
                src_path = (
                    event.src_path if isinstance(event.src_path, str) else event.src_path.decode()
                )
                if not event.is_directory and is_supported_media_file(src_path):
                    self._schedule_async_task(src_path)

            def on_modified(self, event: FileSystemEvent) -> None:
                """Handle file modification events."""
                # Ensure src_path is a string (watchdog can return bytes)
                src_path = (
                    event.src_path if isinstance(event.src_path, str) else event.src_path.decode()
                )
                if not event.is_directory and is_supported_media_file(src_path):
                    self._schedule_async_task(src_path)

            def _schedule_async_task(self, file_path: str) -> None:
                """Schedule async task in the event loop (thread-safe).

                Args:
                    file_path: Path to file to process

                Note:
                    If event loop is not available, this logs an ERROR and increments
                    an error counter. This is a critical failure mode that indicates
                    the FileWatcher was not started properly within an async context.
                """
                # Use the stored loop reference if available
                if self.watcher._loop and self.watcher._loop.is_running():
                    # Schedule task in the event loop (thread-safe from watchdog thread)
                    asyncio.run_coroutine_threadsafe(
                        self.watcher._schedule_file_processing(file_path),
                        self.watcher._loop,
                    )
                else:
                    # This is a critical error - file events are being lost
                    # Log as ERROR and track the failure for monitoring
                    logger.error(
                        f"CRITICAL: Event loop not available for processing {file_path}. "
                        "File will NOT be processed. FileWatcher must be started within "
                        "an async context (e.g., during FastAPI lifespan).",
                        extra={
                            "file_path": file_path,
                            "loop_exists": self.watcher._loop is not None,
                            "loop_running": (
                                self.watcher._loop.is_running() if self.watcher._loop else False
                            ),
                        },
                    )

        return MediaEventHandler(self)

    def _get_camera_id_from_path(self, file_path: str) -> tuple[str | None, str | None]:
        """Extract normalized camera ID and folder name from file path.

        Uses normalize_camera_id() to convert directory names to consistent IDs.
        This ensures that "Front Door", "front-door", and "front_door" all map
        to the same camera_id: "front_door".

        Args:
            file_path: Full path to image file

        Returns:
            Tuple of (camera_id, folder_name) or (None, None) if not found.
            folder_name is the original directory name (for auto-creation).
        """
        try:
            path = Path(file_path)
            camera_root_path = Path(self.camera_root)

            # Get relative path from camera root
            relative_path = path.relative_to(camera_root_path)

            # First component is the folder name (original directory name)
            folder_name = relative_path.parts[0]

            # Normalize to camera ID
            camera_id = normalize_camera_id(folder_name)

            if not camera_id:
                logger.warning(f"Empty camera ID after normalization for folder: {folder_name}")
                return None, None

            return camera_id, folder_name
        except (ValueError, IndexError):
            logger.warning(f"Could not extract camera ID from path: {file_path}")
            return None, None

    async def _wait_for_file_stability(
        self, file_path: str, stability_time: float | None = None
    ) -> bool:
        """Wait until file size stops changing for stability_time seconds.

        This ensures FTP uploads are complete before processing. The method polls
        the file size and waits until it remains unchanged for the specified
        stability period.

        Args:
            file_path: Path to the file to check
            stability_time: Time in seconds the file must be stable.
                           If None, uses self.stability_time (default 2.0s).

        Returns:
            True if file became stable, False if file never stabilized,
            was deleted, or doesn't exist.
        """
        if stability_time is None:
            stability_time = self.stability_time

        # Skip stability check if disabled (stability_time <= 0)
        if stability_time <= 0:
            return True

        last_size: int = -1
        stable_since: float | None = None
        check_interval: float = 0.5  # Check every 0.5 seconds
        max_checks: int = 20  # Maximum ~10 seconds total wait time

        for _ in range(max_checks):
            try:
                current_size = Path(file_path).stat().st_size
            except (FileNotFoundError, OSError):
                # File was deleted or became inaccessible
                logger.warning(
                    f"File disappeared during stability check: {file_path}",
                    extra={"file_path": file_path},
                )
                return False

            if current_size == last_size:
                # Size unchanged - check if stable long enough
                if stable_since is not None and time.monotonic() - stable_since >= stability_time:
                    logger.debug(
                        f"File stable after {stability_time:.1f}s: {file_path}",
                        extra={"file_path": file_path, "file_size": current_size},
                    )
                    return True
            else:
                # Size changed - reset stability timer
                last_size = current_size
                stable_since = time.monotonic()

            await asyncio.sleep(check_interval)

        # Reached max checks without stabilizing
        logger.warning(
            f"File never stabilized after {max_checks * check_interval:.1f}s: {file_path}",
            extra={"file_path": file_path, "last_size": last_size},
        )
        return False

    async def _ensure_camera_exists(self, camera_id: str, folder_name: str) -> None:
        """Ensure camera record exists in database, creating if necessary.

        This method is called when auto_create_cameras is enabled. It uses
        a local set to track cameras we've already processed, avoiding
        repeated database operations for known cameras.

        Args:
            camera_id: Normalized camera ID
            folder_name: Original folder name (for display name)
        """
        # Skip if we've already processed this camera
        if camera_id in self._known_cameras:
            return

        # Mark as known to avoid repeated attempts
        self._known_cameras.add(camera_id)

        if not self._camera_creator:
            return

        try:
            # Construct full folder path
            folder_path = str(Path(self.camera_root) / folder_name)

            # Create camera instance using the factory method
            camera = Camera.from_folder_name(folder_name, folder_path)

            logger.info(
                f"Auto-creating camera '{camera_id}' for folder '{folder_name}'",
                extra={"camera_id": camera_id, "folder_path": folder_path},
            )

            # Call the creator callback (handles database operations)
            await self._camera_creator(camera)

        except Exception as e:
            # Don't fail file processing if camera creation fails
            # The detection will still be queued; FK constraint will catch missing cameras
            logger.warning(
                f"Failed to auto-create camera '{camera_id}': {e}",
                extra={"camera_id": camera_id, "folder_name": folder_name},
            )

    async def _schedule_file_processing(self, file_path: str) -> None:
        """Schedule file processing with debounce logic.

        If a task is already pending for this file, cancel it and create a new one.
        This ensures we wait for the file to be fully written before processing.

        Args:
            file_path: Path to the file to process
        """
        # Cancel existing pending task for this file
        if file_path in self._pending_tasks:
            self._pending_tasks[file_path].cancel()

        # Create new debounced task
        task = asyncio.create_task(self._debounced_process(file_path))
        self._pending_tasks[file_path] = task

        # Add done callback for cleanup to prevent memory leak
        # The callback checks if the task in the dict is still this task before removing
        def cleanup_task(t: asyncio.Task[None]) -> None:
            # Only remove if this task is still the one in the dict
            # (prevents removing a replacement task scheduled for the same file)
            if self._pending_tasks.get(file_path) is t:
                self._pending_tasks.pop(file_path, None)

        task.add_done_callback(cleanup_task)

    async def _debounced_process(self, file_path: str) -> None:
        """Process file after debounce delay.

        Note: Task cleanup is handled by the done callback in _schedule_file_processing
        to prevent memory leaks and race conditions when tasks are replaced.

        Args:
            file_path: Path to the file to process
        """
        try:
            # Wait for debounce delay
            await asyncio.sleep(self.debounce_delay)

            # Process the file
            await self._process_file(file_path)

        except asyncio.CancelledError:
            logger.debug(f"Processing cancelled for {file_path}")

    async def _process_file(self, file_path: str) -> None:
        """Process a file by validating and queuing for detection.

        Args:
            file_path: Path to the image or video file
        """
        start_time = time.time()

        # Extract camera ID and folder name for context
        camera_id, folder_name = self._get_camera_id_from_path(file_path)
        media_type = get_media_type(file_path)

        logger.debug(
            f"Processing file: {file_path}",
            extra={"camera_id": camera_id, "file_path": file_path, "media_type": media_type},
        )

        # Validate file type
        if not is_supported_media_file(file_path):
            logger.debug(
                f"Skipping unsupported file: {file_path}",
                extra={"camera_id": camera_id, "file_path": file_path},
            )
            return

        # Wait for file stability (ensures FTP uploads are complete)
        if not await self._wait_for_file_stability(file_path):
            logger.warning(
                f"Skipping file that never stabilized (may still be uploading): {file_path}",
                extra={"camera_id": camera_id, "file_path": file_path, "media_type": media_type},
            )
            return

        # Validate media file integrity (async to avoid blocking event loop)
        if not await is_valid_media_file_async(file_path):
            logger.warning(
                f"Skipping invalid/corrupted {media_type} file: {file_path}",
                extra={"camera_id": camera_id, "file_path": file_path, "media_type": media_type},
            )
            return

        if not camera_id:
            logger.warning(
                f"Could not determine camera ID for: {file_path}", extra={"file_path": file_path}
            )
            return

        # Auto-create camera if enabled and callback is set
        if self.auto_create_cameras and self._camera_creator and folder_name:
            await self._ensure_camera_exists(camera_id, folder_name)

        # Queue for detection
        try:
            await self._queue_for_detection(camera_id, file_path, media_type)
            duration_ms = int((time.time() - start_time) * 1000)
            # Record watch stage latency to in-memory tracker for /api/system/pipeline-latency
            record_pipeline_stage_latency("watch_to_detect", float(duration_ms))
            logger.info(
                f"Queued {media_type} for detection: {file_path} (camera: {camera_id})",
                extra={
                    "camera_id": camera_id,
                    "file_path": file_path,
                    "media_type": media_type,
                    "duration_ms": duration_ms,
                },
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Failed to queue {media_type} {file_path}: {e}",
                extra={
                    "camera_id": camera_id,
                    "file_path": file_path,
                    "media_type": media_type,
                    "duration_ms": duration_ms,
                },
            )

    async def _queue_for_detection(
        self, camera_id: str, file_path: str, media_type: str | None = None
    ) -> None:
        """Add media file to detection queue in Redis with deduplication.

        Checks if file has already been processed using content hash before
        enqueueing. This prevents duplicate detections from watchdog event
        bursts and service restarts.

        Args:
            camera_id: Camera identifier
            file_path: Path to the image or video file
            media_type: Type of media ("image" or "video")
        """
        if not self.redis_client:
            logger.warning("Redis client not configured, skipping queue")
            return

        # Check for duplicate using content hash
        file_hash: str | None = None
        if self._dedupe_service:
            is_duplicate, file_hash = await self._dedupe_service.is_duplicate_and_mark(file_path)
            if is_duplicate:
                logger.info(
                    f"Skipping duplicate file: {file_path} (hash={file_hash[:16] if file_hash else 'unknown'}...)",
                    extra={"camera_id": camera_id, "file_path": file_path, "file_hash": file_hash},
                )
                return

        # Record pipeline start time for total_pipeline latency tracking
        pipeline_start_time = datetime.now(UTC).isoformat()
        detection_data = {
            "camera_id": camera_id,
            "file_path": file_path,
            "timestamp": pipeline_start_time,
            "media_type": media_type or get_media_type(file_path) or "image",
            "pipeline_start_time": pipeline_start_time,
        }

        # Include hash in queue data for downstream deduplication if needed
        if file_hash:
            detection_data["file_hash"] = file_hash

        # Use add_to_queue_safe() with DLQ policy to prevent silent data loss
        # If the queue is full, items are moved to a dead-letter queue instead of being dropped
        result = await self.redis_client.add_to_queue_safe(
            self.queue_name,
            detection_data,
            overflow_policy=QueueOverflowPolicy.DLQ,
        )

        if not result.success:
            logger.error(
                f"Failed to queue detection for {file_path}: {result.error}",
                extra={
                    "camera_id": camera_id,
                    "file_path": file_path,
                    "queue_name": self.queue_name,
                    "queue_length": result.queue_length,
                },
            )
            raise RuntimeError(f"Queue operation failed: {result.error}")

        if result.had_backpressure:
            logger.warning(
                f"Queue backpressure detected while adding detection for {file_path}",
                extra={
                    "camera_id": camera_id,
                    "file_path": file_path,
                    "queue_name": self.queue_name,
                    "queue_length": result.queue_length,
                    "moved_to_dlq": result.moved_to_dlq_count,
                    "warning": result.warning,
                },
            )

    async def start(self) -> None:
        """Start watching camera directories for file changes.

        This method is idempotent - calling it multiple times is safe.
        """
        if self.running:
            logger.warning("FileWatcher already running")
            return

        logger.info(f"Starting FileWatcher for {self.camera_root}")

        # Capture the current event loop for thread-safe task scheduling
        # This is REQUIRED - FileWatcher cannot function without an async event loop
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError as e:
            error_msg = (
                "FileWatcher MUST be started within an async context (e.g., during "
                "FastAPI lifespan). No running event loop detected - file events "
                "will be lost. This is a critical configuration error."
            )
            logger.error(
                error_msg,
                extra={"error": str(e), "camera_root": self.camera_root},
            )
            raise RuntimeError(error_msg) from e
        except Exception as e:
            # Catch any unexpected exceptions during event loop capture
            error_msg = (
                f"Unexpected error capturing event loop: {type(e).__name__}: {e}. "
                "FileWatcher cannot function without a valid event loop."
            )
            logger.error(
                error_msg,
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "camera_root": self.camera_root,
                },
            )
            raise RuntimeError(error_msg) from e

        # Verify the event loop was captured successfully
        if self._loop is None:
            error_msg = (
                "Event loop capture returned None. FileWatcher cannot function "
                "without a valid event loop. This should not happen - please report this bug."
            )
            logger.error(error_msg, extra={"camera_root": self.camera_root})
            raise RuntimeError(error_msg)

        # Verify the loop is actually running
        if not self._loop.is_running():
            error_msg = (
                "Captured event loop is not running. FileWatcher requires "
                "a running event loop for thread-safe task scheduling."
            )
            logger.error(
                error_msg,
                extra={"camera_root": self.camera_root, "loop_closed": self._loop.is_closed()},
            )
            raise RuntimeError(error_msg)

        logger.debug(
            "Event loop captured successfully for FileWatcher",
            extra={
                "camera_root": self.camera_root,
                "loop_running": self._loop.is_running(),
                "loop_closed": self._loop.is_closed(),
            },
        )

        # Schedule observer for each camera directory
        camera_root_path = Path(self.camera_root)
        if not camera_root_path.exists():
            logger.warning(f"Camera root directory does not exist: {self.camera_root}")
            camera_root_path.mkdir(parents=True, exist_ok=True)

        # Watch the entire camera root directory recursively
        self.observer.schedule(
            self._event_handler,
            str(camera_root_path),
            recursive=True,
        )

        # Start observer
        self.observer.start()
        self.running = True

        logger.info("FileWatcher started successfully")

    async def stop(self) -> None:
        """Stop watching and cleanup resources.

        Cancels all pending debounce tasks and stops the observer.
        Uses run_in_executor for blocking observer.join() to avoid blocking the event loop.
        """
        if not self.running:
            logger.debug("FileWatcher not running, nothing to stop")
            self.running = False
            return

        logger.info("Stopping FileWatcher")

        # Cancel all pending tasks
        for task in self._pending_tasks.values():
            task.cancel()

        # Wait for tasks to complete cancellation
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks.values(), return_exceptions=True)

        self._pending_tasks.clear()

        # Stop observer
        self.observer.stop()

        # Run blocking join() in thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.observer.join(timeout=5))

        # Clear loop reference
        self._loop = None

        self.running = False
        logger.info("FileWatcher stopped")

    async def __aenter__(self) -> FileWatcher:
        """Async context manager entry.

        Starts the file watcher and returns self for use in async with statements.

        Returns:
            Self for use in the context manager block.

        Example:
            async with FileWatcher(camera_root="/path/to/cameras") as watcher:
                # watcher is started and ready to use
                ...
            # watcher is automatically stopped when exiting the block
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit.

        Stops the file watcher, ensuring cleanup even if an exception occurred.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise.
            exc_val: Exception value if an exception was raised, None otherwise.
            exc_tb: Exception traceback if an exception was raised, None otherwise.
        """
        await self.stop()
