"""Stream manager service for RTSP camera stream connections.

This service manages RTSP stream connections for live camera feeds with automatic
reconnection and health tracking.

Features:
- RTSP stream connection using TCP transport (reliable, no UDP)
- Exponential backoff for reconnection (5s, 10s, 20s, 40s, max 60s)
- Health tracking via Redis hash keys
- Async-compatible design with event loop integration
- Graceful shutdown handling
- Support for multiple concurrent streams

Redis Schema:
- Health keys: hsi:stream:health:{camera_id}
- Fields: status, connection_time, fps, retry_count, last_error

Related Issues:
    - NEM-4197: Implement Stream Manager Service
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import cv2

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Redis key prefix for stream health tracking
REDIS_HEALTH_KEY_PREFIX = "hsi:stream:health:"

# Backoff configuration
INITIAL_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 60

# Health update interval (seconds)
DEFAULT_HEALTH_UPDATE_INTERVAL = 5.0


class StreamManager:
    """Manages RTSP stream connections with health tracking and reconnection.

    This service provides:
    - RTSP stream connection management using TCP transport
    - Automatic reconnection with exponential backoff
    - Health tracking persisted in Redis
    - Support for multiple concurrent streams
    - Graceful shutdown with resource cleanup

    Example:
        async with StreamManager(redis_client=redis) as manager:
            await manager.add_stream("camera1", "rtsp://example.com/stream1")
            health = await manager.get_stream_health("camera1")
            print(health["status"])  # "connected"
    """

    def __init__(
        self,
        redis_client: Any,
        capture_factory: Any | None = None,
        health_update_interval: float = DEFAULT_HEALTH_UPDATE_INTERVAL,
    ):
        """Initialize StreamManager with Redis client for health tracking.

        Args:
            redis_client: Redis client instance for health tracking (async).
            capture_factory: Optional factory for creating VideoCapture instances.
                           Used for dependency injection in tests.
            health_update_interval: Interval in seconds between health updates.
        """
        self.redis_client = redis_client
        self._capture_factory = capture_factory
        self._health_update_interval = health_update_interval

        # Stream tracking: maps camera_id -> stream context dict
        self._streams: dict[str, dict[str, Any]] = {}

        # Running state
        self.running = False
        self._loop: asyncio.AbstractEventLoop | None = None

        # Background tasks
        self._background_tasks: dict[str, asyncio.Task[None]] = {}

        # Lock for thread-safe stream operations
        self._lock = asyncio.Lock()

        logger.info(
            "StreamManager initialized",
            extra={"health_update_interval": health_update_interval},
        )

    async def start(self) -> None:
        """Start service and capture event loop.

        This method must be called within an async context. It captures the
        running event loop for thread-safe task scheduling.

        Raises:
            RuntimeError: If no running event loop is available.
        """
        if self.running:
            logger.warning("StreamManager already running")
            return

        logger.info("Starting StreamManager")

        # Capture the current event loop for thread-safe operations
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError as e:
            error_msg = (
                "StreamManager MUST be started within an async context. "
                "No running event loop detected."
            )
            logger.error(error_msg, extra={"error": str(e)})
            raise RuntimeError(error_msg) from e

        if self._loop is None:
            error_msg = "Event loop capture returned None unexpectedly."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        if not self._loop.is_running():
            error_msg = "Captured event loop is not running."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        self.running = True
        logger.info("StreamManager started successfully")

    async def stop(self) -> None:
        """Stop service and clean up all resources.

        Cancels all background tasks, releases all VideoCapture instances,
        and clears the event loop reference.
        """
        logger.info("Stopping StreamManager")

        self.running = False

        # Cancel all background tasks
        for task_name, task in list(self._background_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.debug(f"Cancelled background task: {task_name}")

        self._background_tasks.clear()

        # Clean up all streams
        camera_ids = list(self._streams.keys())
        for camera_id in camera_ids:
            await self._cleanup_stream(camera_id)

        self._streams.clear()

        # Clear loop reference
        self._loop = None

        logger.info("StreamManager stopped")

    async def add_stream(self, camera_id: str, rtsp_url: str) -> None:
        """Register new RTSP stream with TCP transport.

        If a stream already exists for this camera_id, it will be replaced
        with the new URL.

        Args:
            camera_id: Unique identifier for the camera.
            rtsp_url: RTSP URL for the stream.
        """
        async with self._lock:
            # Remove existing stream if present
            if camera_id in self._streams:
                await self._cleanup_stream(camera_id)

            logger.info(
                f"Adding stream for camera {camera_id}",
                extra={"camera_id": camera_id, "rtsp_url": rtsp_url},
            )

            # Initialize stream context
            self._streams[camera_id] = {
                "rtsp_url": rtsp_url,
                "capture": None,
                "retry_count": 0,
                "last_error": None,
                "connection_time": None,
            }

            # Start connection task
            task = asyncio.create_task(self._connection_loop(camera_id, rtsp_url))
            self._background_tasks[f"connection_{camera_id}"] = task

            # Update initial health status
            await self._update_health(camera_id, "connecting")

    async def remove_stream(self, camera_id: str) -> None:
        """Remove stream and clean up resources.

        Safe to call with nonexistent camera_id (no-op).

        Args:
            camera_id: Camera identifier to remove.
        """
        async with self._lock:
            if camera_id not in self._streams:
                logger.debug(f"No stream to remove for camera {camera_id}")
                return

            logger.info(f"Removing stream for camera {camera_id}")

            await self._cleanup_stream(camera_id)

            # Remove from streams dict
            self._streams.pop(camera_id, None)

            # Delete Redis health key
            await self._delete_health_key(camera_id)

    async def get_stream_health(self, camera_id: str) -> dict[str, Any] | None:
        """Retrieve health data from Redis.

        Args:
            camera_id: Camera identifier.

        Returns:
            Health data dict with fields: status, connection_time, fps, retry_count, last_error.
            Returns None or empty dict if stream doesn't exist.
        """
        key = f"{REDIS_HEALTH_KEY_PREFIX}{camera_id}"
        try:
            data = await self.redis_client.hgetall(key)
            if not data:
                return None

            # Decode bytes if necessary (Redis returns bytes in some clients)
            result = {}
            for k, v in data.items():
                key_str = k.decode() if isinstance(k, bytes) else k
                val_str = v.decode() if isinstance(v, bytes) else v
                result[key_str] = val_str

            return result
        except Exception as e:
            logger.warning(
                f"Failed to get stream health for {camera_id}: {e}",
                extra={"camera_id": camera_id, "error": str(e)},
            )
            return None

    def _calculate_backoff(self, retry_count: int) -> int:
        """Calculate exponential backoff delay.

        Pattern: 5s -> 10s -> 20s -> 40s -> 60s (max)

        Args:
            retry_count: Number of retry attempts (0-indexed).

        Returns:
            Backoff delay in seconds.
        """
        delay: int = INITIAL_BACKOFF_SECONDS * (2**retry_count)
        return int(min(delay, MAX_BACKOFF_SECONDS))

    async def _connection_loop(self, camera_id: str, rtsp_url: str) -> None:
        """Background task for managing stream connection with reconnection.

        This loop:
        1. Attempts to connect to the RTSP stream
        2. On success, starts health monitoring
        3. On failure, waits with exponential backoff before retrying
        4. Resets backoff counter on successful connection

        Args:
            camera_id: Camera identifier.
            rtsp_url: RTSP URL for the stream.
        """
        while self.running and camera_id in self._streams:
            try:
                # Attempt connection
                capture = await self._create_capture(rtsp_url)

                if capture is not None and capture.isOpened():
                    # Connection successful
                    logger.info(
                        f"Stream connected for camera {camera_id}",
                        extra={"camera_id": camera_id},
                    )

                    # Store capture and reset retry count
                    async with self._lock:
                        if camera_id in self._streams:
                            self._streams[camera_id]["capture"] = capture
                            self._streams[camera_id]["retry_count"] = 0
                            self._streams[camera_id]["last_error"] = None
                            self._streams[camera_id]["connection_time"] = datetime.now(
                                UTC
                            ).isoformat()

                    # Update health to connected
                    await self._update_health(camera_id, "connected")

                    # Start health monitoring loop
                    await self._health_monitoring_loop(camera_id, capture)

                else:
                    # Connection failed
                    await self._handle_connection_failure(camera_id, "Failed to open stream")

            except asyncio.CancelledError:
                logger.debug(f"Connection loop cancelled for camera {camera_id}")
                raise
            except Exception as e:
                await self._handle_connection_failure(camera_id, str(e))

    async def _handle_connection_failure(self, camera_id: str, error_message: str) -> None:
        """Handle connection failure with exponential backoff.

        Args:
            camera_id: Camera identifier.
            error_message: Error description.
        """
        if camera_id not in self._streams:
            return

        async with self._lock:
            if camera_id not in self._streams:
                return

            retry_count = self._streams[camera_id]["retry_count"]
            self._streams[camera_id]["retry_count"] = retry_count + 1
            self._streams[camera_id]["last_error"] = error_message

        backoff = self._calculate_backoff(retry_count)

        logger.warning(
            f"Stream connection failed for camera {camera_id}, retrying in {backoff}s",
            extra={
                "camera_id": camera_id,
                "error": error_message,
                "retry_count": retry_count + 1,
                "backoff_seconds": backoff,
            },
        )

        # Update health to reconnecting
        await self._update_health(
            camera_id,
            "reconnecting",
            retry_count=retry_count + 1,
            last_error=error_message,
        )

        # Wait with backoff
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise

    async def _create_capture(self, rtsp_url: str) -> cv2.VideoCapture | None:
        """Create VideoCapture with TCP transport.

        Args:
            rtsp_url: RTSP URL for the stream.

        Returns:
            VideoCapture instance or None on failure.
        """
        try:
            if self._capture_factory:
                # Cast return from factory to expected type
                result: cv2.VideoCapture | None = self._capture_factory(rtsp_url)
                return result

            # Create VideoCapture with FFMPEG backend and TCP transport
            # Run in thread to avoid blocking event loop
            loop = asyncio.get_running_loop()
            capture: cv2.VideoCapture = await loop.run_in_executor(
                None, lambda: self._create_capture_sync(rtsp_url)
            )
            return capture
        except Exception as e:
            logger.error(
                f"Failed to create capture for {rtsp_url}: {e}",
                extra={"rtsp_url": rtsp_url, "error": str(e)},
            )
            return None

    def _create_capture_sync(self, rtsp_url: str) -> cv2.VideoCapture:
        """Synchronous helper to create VideoCapture with TCP transport.

        Args:
            rtsp_url: RTSP URL for the stream.

        Returns:
            VideoCapture instance.
        """
        # Force TCP transport using FFMPEG backend
        capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

        # Set timeout preferences for reliable streaming
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)  # 10s open timeout
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)  # 5s read timeout

        return capture

    async def _health_monitoring_loop(self, camera_id: str, capture: cv2.VideoCapture) -> None:
        """Monitor stream health and update Redis periodically.

        Args:
            camera_id: Camera identifier.
            capture: VideoCapture instance to monitor.
        """
        last_fps_calc_time = asyncio.get_event_loop().time()
        frame_count = 0

        while self.running and camera_id in self._streams:
            try:
                # Check if capture is still valid
                if not capture.isOpened():
                    logger.warning(f"Stream disconnected for camera {camera_id}")
                    await self._release_capture(capture)
                    break

                # Attempt to read frame (non-blocking check)
                loop = asyncio.get_running_loop()
                success, _ = await loop.run_in_executor(None, capture.read)

                if not success:
                    logger.warning(f"Failed to read frame for camera {camera_id}")
                    await self._release_capture(capture)
                    break

                frame_count += 1

                # Calculate FPS periodically
                current_time = asyncio.get_event_loop().time()
                elapsed = current_time - last_fps_calc_time

                if elapsed >= self._health_update_interval:
                    fps = frame_count / elapsed if elapsed > 0 else 0.0
                    frame_count = 0
                    last_fps_calc_time = current_time

                    # Update health with FPS
                    await self._update_health(camera_id, "connected", fps=fps)

                # Small delay to prevent tight loop
                await asyncio.sleep(0.033)  # ~30 FPS max

            except asyncio.CancelledError:
                await self._release_capture(capture)
                raise
            except Exception as e:
                logger.error(
                    f"Error in health monitoring for camera {camera_id}: {e}",
                    extra={"camera_id": camera_id, "error": str(e)},
                )
                await self._release_capture(capture)
                break

    async def _release_capture(self, capture: cv2.VideoCapture) -> None:
        """Release VideoCapture instance in thread pool.

        Args:
            capture: VideoCapture instance to release.
        """
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, capture.release)
        except Exception as e:
            logger.warning(f"Error releasing capture: {e}")

    async def _cleanup_stream(self, camera_id: str) -> None:
        """Clean up stream resources.

        Args:
            camera_id: Camera identifier.
        """
        # Cancel connection task
        task_name = f"connection_{camera_id}"
        if task_name in self._background_tasks:
            self._background_tasks[task_name].cancel()
            try:
                await self._background_tasks[task_name]
            except asyncio.CancelledError:
                pass
            self._background_tasks.pop(task_name, None)

        # Release capture if exists
        if camera_id in self._streams:
            capture = self._streams[camera_id].get("capture")
            if capture is not None:
                await self._release_capture(capture)
                self._streams[camera_id]["capture"] = None

    async def _update_health(
        self,
        camera_id: str,
        status: str,
        fps: float | None = None,
        retry_count: int | None = None,
        last_error: str | None = None,
    ) -> None:
        """Update health data in Redis.

        Args:
            camera_id: Camera identifier.
            status: Stream status (connected, reconnecting, failed).
            fps: Frames per second (optional).
            retry_count: Number of retry attempts (optional).
            last_error: Last error message (optional).
        """
        key = f"{REDIS_HEALTH_KEY_PREFIX}{camera_id}"

        # Build health data
        health_data: dict[str, str] = {
            "status": status,
        }

        if camera_id in self._streams:
            connection_time = self._streams[camera_id].get("connection_time")
            if connection_time:
                health_data["connection_time"] = connection_time

            if retry_count is None:
                retry_count = self._streams[camera_id].get("retry_count", 0)
            if last_error is None:
                last_error = self._streams[camera_id].get("last_error")

        if fps is not None:
            health_data["fps"] = f"{fps:.1f}"

        if retry_count is not None:
            health_data["retry_count"] = str(retry_count)

        if last_error is not None:
            health_data["last_error"] = last_error

        try:
            await self.redis_client.hset(key, mapping=health_data)
        except Exception as e:
            # Log but don't fail - health tracking is non-critical
            logger.warning(
                f"Failed to update health for camera {camera_id}: {e}",
                extra={"camera_id": camera_id, "error": str(e)},
            )

    async def _delete_health_key(self, camera_id: str) -> None:
        """Delete health key from Redis.

        Args:
            camera_id: Camera identifier.
        """
        key = f"{REDIS_HEALTH_KEY_PREFIX}{camera_id}"
        try:
            # Use delete for the entire key, not hdel for fields
            await self.redis_client.delete(key)
        except Exception as e:
            logger.warning(
                f"Failed to delete health key for camera {camera_id}: {e}",
                extra={"camera_id": camera_id, "error": str(e)},
            )

    async def __aenter__(self) -> StreamManager:
        """Async context manager entry.

        Starts the stream manager and returns self.

        Returns:
            Self for use in the context manager block.
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

        Stops the stream manager, ensuring cleanup even if an exception occurred.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.
        """
        await self.stop()
