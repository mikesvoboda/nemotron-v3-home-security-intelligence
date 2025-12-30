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
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# NOTE: We use watchdog's default Observer (not PollingObserver) for efficiency.
# Observer auto-selects the best native backend for each platform:
#   - Linux: inotify (kernel-level filesystem notifications)
#   - macOS: FSEvents (native filesystem event API)
#   - Windows: ReadDirectoryChangesW (native API)
# This provides near-instant event detection without CPU-intensive polling.
# Only use PollingObserver if monitoring network filesystems (NFS/SMB) where
# inotify events may not propagate.
from backend.core.config import get_settings
from backend.core.logging import get_logger
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


def is_valid_image(file_path: str) -> bool:
    """Validate that file is a valid, non-corrupted image.

    Args:
        file_path: Path to the image file

    Returns:
        True if file is a valid image with size > 0
    """
    try:
        # Check file exists and has content
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return False

        if file_path_obj.stat().st_size == 0:
            logger.warning(f"Empty file detected: {file_path}")
            return False

        # Try to open and verify image
        with Image.open(file_path) as img:
            img.verify()

        return True
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
        queue_name: str = "detection_queue",
        dedupe_service: DedupeService | None = None,
        auto_create_cameras: bool = True,
        camera_creator: Callable[[Camera], Any] | None = None,
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
        """
        settings = get_settings()
        self.camera_root = camera_root or settings.foscam_base_path
        self.redis_client = redis_client
        self.debounce_delay = debounce_delay
        self.queue_name = queue_name
        self.auto_create_cameras = auto_create_cameras
        self._camera_creator = camera_creator

        # Track which cameras we've already tried to create (avoid repeated attempts)
        self._known_cameras: set[str] = set()

        # Initialize dedupe service (creates one if not provided and redis is available)
        self._dedupe_service: DedupeService | None = None
        if dedupe_service is not None:
            self._dedupe_service = dedupe_service
        elif redis_client is not None:
            self._dedupe_service = DedupeService(redis_client=redis_client)

        # Watchdog observer for filesystem monitoring
        self.observer = Observer()

        # Track running state
        self.running = False

        # Debounce tracking: maps file_path -> asyncio.Task
        self._pending_tasks: dict[str, asyncio.Task[None]] = {}

        # Event loop reference (set during start())
        self._loop: asyncio.AbstractEventLoop | None = None

        # Create event handler
        self._event_handler = self._create_event_handler()

        logger.info(
            f"FileWatcher initialized for camera root: {self.camera_root} "
            f"(dedupe={'enabled' if self._dedupe_service else 'disabled'}, "
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
                """
                # Use the stored loop reference if available
                if self.watcher._loop and self.watcher._loop.is_running():
                    # Schedule task in the event loop (thread-safe from watchdog thread)
                    asyncio.run_coroutine_threadsafe(
                        self.watcher._schedule_file_processing(file_path),
                        self.watcher._loop,
                    )
                else:
                    logger.warning(f"Event loop not available for processing {file_path}")

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

    async def _debounced_process(self, file_path: str) -> None:
        """Process file after debounce delay.

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
        finally:
            # Clean up pending task
            self._pending_tasks.pop(file_path, None)

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

        # Validate media file integrity
        if not is_valid_media_file(file_path):
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

        detection_data = {
            "camera_id": camera_id,
            "file_path": file_path,
            "timestamp": datetime.now().isoformat(),
            "media_type": media_type or get_media_type(file_path) or "image",
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
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop detected - file processing may not work")
            self._loop = None

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
        self.observer.join(timeout=5)

        # Clear loop reference
        self._loop = None

        self.running = False
        logger.info("FileWatcher stopped")
