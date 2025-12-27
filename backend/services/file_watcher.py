"""File watcher service for monitoring Foscam camera uploads.

This service watches camera directories for new image uploads, validates them,
and queues them for AI processing with debounce logic to prevent duplicate processing.

Idempotency:
-----------
Files are deduplicated using SHA256 content hashes stored in Redis with TTL.
This prevents duplicate processing caused by:
- Watchdog create/modify event bursts
- Service restarts during file processing
- FTP upload retries

The dedupe check happens before enqueueing to Redis, ensuring the same file
content is never processed twice within the TTL window (default 5 minutes).
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.services.dedupe import DedupeService

logger = get_logger(__name__)


def is_image_file(file_path: str) -> bool:
    """Check if file has a valid image extension.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file has image extension (.jpg, .jpeg, .png)
    """
    valid_extensions = {".jpg", ".jpeg", ".png"}
    return Path(file_path).suffix.lower() in valid_extensions


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


class FileWatcher:
    """Watches camera directories for new image uploads and queues for processing.

    Features:
    - Debounce logic to wait for file writes to complete
    - Image integrity validation before queuing
    - Async-compatible design
    - Graceful shutdown handling
    """

    def __init__(
        self,
        camera_root: str | None = None,
        redis_client: Any | None = None,
        debounce_delay: float = 0.5,
        queue_name: str = "detection_queue",
        dedupe_service: DedupeService | None = None,
    ):
        """Initialize file watcher.

        Args:
            camera_root: Root directory containing camera folders (e.g., /export/foscam)
            redis_client: RedisClient instance for queueing detections
            debounce_delay: Delay in seconds to wait after last file modification
            queue_name: Name of Redis queue for detection jobs
            dedupe_service: Optional DedupeService for file deduplication
        """
        settings = get_settings()
        self.camera_root = camera_root or settings.foscam_base_path
        self.redis_client = redis_client
        self.debounce_delay = debounce_delay
        self.queue_name = queue_name

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
        self._pending_tasks: dict[str, asyncio.Task] = {}

        # Event loop reference (set during start())
        self._loop: asyncio.AbstractEventLoop | None = None

        # Create event handler
        self._event_handler = self._create_event_handler()

        logger.info(
            f"FileWatcher initialized for camera root: {self.camera_root} "
            f"(dedupe={'enabled' if self._dedupe_service else 'disabled'})"
        )

    def _create_event_handler(self) -> FileSystemEventHandler:
        """Create watchdog event handler for file system events.

        Returns:
            FileSystemEventHandler instance
        """

        class ImageEventHandler(FileSystemEventHandler):
            """Handle file system events for image files."""

            def __init__(self, watcher: FileWatcher):
                self.watcher = watcher
                super().__init__()

            def on_created(self, event: FileSystemEvent) -> None:
                """Handle file creation events."""
                # Ensure src_path is a string (watchdog can return bytes)
                src_path = (
                    event.src_path if isinstance(event.src_path, str) else event.src_path.decode()
                )
                if not event.is_directory and is_image_file(src_path):
                    self._schedule_async_task(src_path)

            def on_modified(self, event: FileSystemEvent) -> None:
                """Handle file modification events."""
                # Ensure src_path is a string (watchdog can return bytes)
                src_path = (
                    event.src_path if isinstance(event.src_path, str) else event.src_path.decode()
                )
                if not event.is_directory and is_image_file(src_path):
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

        return ImageEventHandler(self)

    def _get_camera_id_from_path(self, file_path: str) -> str | None:
        """Extract camera ID from file path.

        Args:
            file_path: Full path to image file

        Returns:
            Camera ID (directory name under camera_root) or None if not found
        """
        try:
            path = Path(file_path)
            camera_root_path = Path(self.camera_root)

            # Get relative path from camera root
            relative_path = path.relative_to(camera_root_path)

            # First component is camera ID
            camera_id = relative_path.parts[0]
            return camera_id
        except (ValueError, IndexError):
            logger.warning(f"Could not extract camera ID from path: {file_path}")
            return None

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
            file_path: Path to the image file
        """
        start_time = time.time()

        # Extract camera ID early for context
        camera_id = self._get_camera_id_from_path(file_path)

        logger.debug(
            f"Processing file: {file_path}", extra={"camera_id": camera_id, "file_path": file_path}
        )

        # Validate file type
        if not is_image_file(file_path):
            logger.debug(
                f"Skipping non-image file: {file_path}",
                extra={"camera_id": camera_id, "file_path": file_path},
            )
            return

        # Validate image integrity
        if not is_valid_image(file_path):
            logger.warning(
                f"Skipping invalid/corrupted image: {file_path}",
                extra={"camera_id": camera_id, "file_path": file_path},
            )
            return

        if not camera_id:
            logger.warning(
                f"Could not determine camera ID for: {file_path}", extra={"file_path": file_path}
            )
            return

        # Queue for detection
        try:
            await self._queue_for_detection(camera_id, file_path)
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Queued image for detection: {file_path} (camera: {camera_id})",
                extra={"camera_id": camera_id, "file_path": file_path, "duration_ms": duration_ms},
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Failed to queue image {file_path}: {e}",
                extra={"camera_id": camera_id, "file_path": file_path, "duration_ms": duration_ms},
            )

    async def _queue_for_detection(self, camera_id: str, file_path: str) -> None:
        """Add image to detection queue in Redis with deduplication.

        Checks if file has already been processed using content hash before
        enqueueing. This prevents duplicate detections from watchdog event
        bursts and service restarts.

        Args:
            camera_id: Camera identifier
            file_path: Path to the image file
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
        }

        # Include hash in queue data for downstream deduplication if needed
        if file_hash:
            detection_data["file_hash"] = file_hash

        await self.redis_client.add_to_queue(self.queue_name, detection_data)

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
