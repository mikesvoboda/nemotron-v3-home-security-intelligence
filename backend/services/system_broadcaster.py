"""WebSocket broadcaster for system status updates.

This module manages WebSocket connections and broadcasts real-time system
status updates to connected clients. It handles:

- Connection lifecycle management
- Periodic system status broadcasting via Redis pub/sub
- GPU statistics
- Camera status
- Processing queue status

Redis Pub/Sub Integration:
    The SystemBroadcaster uses Redis pub/sub to enable multi-instance deployments.
    System status updates are published to a dedicated Redis channel, and all
    instances subscribe to receive updates for their connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from sqlalchemy import func, select

from backend.core import get_session
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.logging import get_logger
from backend.models import Camera, GPUStats

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub

    from backend.core.redis import RedisClient
    from backend.services.performance_collector import PerformanceCollector

logger = get_logger(__name__)

# Redis channel for system status updates
SYSTEM_STATUS_CHANNEL = "system_status"

# Redis channel for performance updates
PERFORMANCE_UPDATE_CHANNEL = "performance_update"


class SystemBroadcaster:
    """Manages WebSocket connections for system status broadcasts.

    This class maintains a set of active WebSocket connections and provides
    methods to broadcast system status updates to all connected clients.
    Uses Redis pub/sub to enable multi-instance deployments where any instance
    can publish status updates and all instances forward them to their clients.

    Attributes:
        connections: Set of active WebSocket connections
        _broadcast_task: Background task for periodic status updates
        _listener_task: Background task for listening to Redis pub/sub
        _running: Flag indicating if broadcaster is running
        _redis_client: Injected Redis client instance (optional)
        _redis_getter: Callable that returns Redis client (alternative to direct injection)
        _pubsub: Redis pub/sub instance for receiving updates
        _performance_collector: Optional PerformanceCollector for detailed system metrics
    """

    # Maximum number of consecutive recovery attempts before giving up
    # Prevents unbounded recursion / stack overflow on repeated failures
    MAX_RECOVERY_ATTEMPTS = 5

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        redis_getter: Callable[[], RedisClient | None] | None = None,
    ) -> None:
        """Initialize the SystemBroadcaster.

        Args:
            redis_client: Optional Redis client instance. If provided, takes precedence
                over redis_getter.
            redis_getter: Optional callable that returns a Redis client or None.
                Useful for lazy initialization when Redis may not be immediately available.
        """
        self.connections: set[WebSocket] = set()
        self._broadcast_task: asyncio.Task[None] | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._running = False
        self._redis_client = redis_client
        self._redis_getter = redis_getter
        self._pubsub: PubSub | None = None
        self._pubsub_listening = False
        self._performance_collector: PerformanceCollector | None = None

    def _get_redis(self) -> RedisClient | None:
        """Get the Redis client instance.

        Returns the directly injected redis_client if available, otherwise
        calls redis_getter if provided.

        Returns:
            RedisClient instance or None if unavailable
        """
        if self._redis_client is not None:
            return self._redis_client
        if self._redis_getter is not None:
            return self._redis_getter()
        return None

    def set_redis_client(self, redis_client: RedisClient | None) -> None:
        """Set the Redis client after initialization.

        This allows updating the Redis client after the broadcaster is created,
        useful when Redis initialization happens asynchronously.

        Args:
            redis_client: Redis client instance or None
        """
        self._redis_client = redis_client

    def set_performance_collector(self, collector: PerformanceCollector | None) -> None:
        """Set the PerformanceCollector after initialization.

        This allows the broadcaster to collect and broadcast detailed performance
        metrics from GPU, AI models, databases, and host system.

        Args:
            collector: PerformanceCollector instance or None
        """
        self._performance_collector = collector

    async def connect(self, websocket: WebSocket) -> None:
        """Add a WebSocket connection to the broadcaster.

        Args:
            websocket: WebSocket connection to add
        """
        await websocket.accept()
        self.connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.connections)}")

        # Send initial status immediately after connection
        try:
            status_data = await self._get_system_status()
            await websocket.send_json(status_data)
        except Exception as e:
            logger.error(f"Failed to send initial status: {e}", exc_info=True)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the broadcaster.

        Args:
            websocket: WebSocket connection to remove
        """
        self.connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.connections)}")

    async def broadcast_status(self, status_data: dict) -> None:
        """Broadcast system status to all connected clients via Redis pub/sub.

        If Redis is available, publishes to the system_status channel so all
        instances receive the update. Falls back to direct broadcasting if
        Redis is unavailable.

        Args:
            status_data: System status data to broadcast
        """
        redis_client = self._get_redis()

        # Try to publish via Redis for multi-instance support
        if redis_client is not None:
            try:
                await redis_client.publish(SYSTEM_STATUS_CHANNEL, status_data)
                logger.debug("Published system status via Redis pub/sub")
                return
            except Exception as e:
                logger.warning(f"Failed to publish via Redis, falling back to direct: {e}")

        # Fallback: broadcast directly to local connections
        await self._send_to_local_clients(status_data)

    async def broadcast_performance(self) -> None:
        """Broadcast detailed performance metrics to all connected clients.

        Uses the PerformanceCollector to gather comprehensive system metrics
        including GPU, AI models, databases, and host metrics. Broadcasts
        as message type "performance_update" via WebSocket.

        If no PerformanceCollector is configured, this method returns early
        without broadcasting.
        """
        if self._performance_collector is None:
            logger.debug("No PerformanceCollector configured, skipping performance broadcast")
            return

        try:
            # Collect all performance metrics
            performance_update = await self._performance_collector.collect_all()

            # Build the broadcast message
            performance_data = {
                "type": "performance_update",
                "data": performance_update.model_dump(mode="json"),
            }

            redis_client = self._get_redis()

            # Try to publish via Redis for multi-instance support
            if redis_client is not None:
                try:
                    await redis_client.publish(PERFORMANCE_UPDATE_CHANNEL, performance_data)
                    logger.debug("Published performance update via Redis pub/sub")
                    return
                except Exception as e:
                    logger.warning(
                        f"Failed to publish performance via Redis, falling back to direct: {e}"
                    )

            # Fallback: broadcast directly to local connections
            await self._send_to_local_clients(performance_data)

        except Exception as e:
            logger.error(f"Error broadcasting performance metrics: {e}", exc_info=True)

    async def _send_to_local_clients(self, status_data: dict | Any) -> None:
        """Send status data directly to all locally connected WebSocket clients.

        This is used both by the Redis listener and as a fallback when Redis
        is unavailable.

        Args:
            status_data: System status data to send
        """
        if not self.connections:
            return

        # Convert to JSON string if needed
        message = json.dumps(status_data) if not isinstance(status_data, str) else status_data

        failed_connections = set()

        for websocket in self.connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                failed_connections.add(websocket)

        # Remove failed connections
        self.connections -= failed_connections
        if failed_connections:
            logger.info(
                f"Removed {len(failed_connections)} failed connections. "
                f"Active connections: {len(self.connections)}"
            )

    async def _start_pubsub_listener(self) -> None:
        """Start the Redis pub/sub listener for receiving system status updates.

        This enables multi-instance support where status updates published by
        any instance are received and forwarded to local WebSocket clients.

        Uses a dedicated pub/sub connection to avoid concurrency issues with
        other Redis operations (prevents 'readuntil() called while another
        coroutine is already waiting' errors).
        """
        redis_client = self._get_redis()
        if redis_client is None:
            logger.warning("Redis not available, pub/sub listener not started")
            return

        if self._pubsub_listening:
            logger.warning("Pub/sub listener already running")
            return

        try:
            # Use subscribe_dedicated() to get a dedicated connection that
            # won't conflict with other Redis operations
            self._pubsub = await redis_client.subscribe_dedicated(SYSTEM_STATUS_CHANNEL)
            self._pubsub_listening = True
            self._recovery_attempts = 0  # Reset recovery attempts on successful start
            self._listener_task = asyncio.create_task(self._listen_for_updates())
            logger.info(f"Started pub/sub listener on channel: {SYSTEM_STATUS_CHANNEL}")
        except Exception as e:
            logger.error(f"Failed to start pub/sub listener: {e}", exc_info=True)

    async def _stop_pubsub_listener(self) -> None:
        """Stop the Redis pub/sub listener and close dedicated connection."""
        self._pubsub_listening = False

        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        if self._pubsub:
            try:
                # Unsubscribe directly on the dedicated pubsub instance
                await self._pubsub.unsubscribe(SYSTEM_STATUS_CHANNEL)
            except Exception as e:
                logger.warning(f"Error unsubscribing: {e}")
            try:
                # Close the dedicated pubsub connection
                await self._pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing pubsub connection: {e}")
            self._pubsub = None

        logger.info("Stopped pub/sub listener")

    async def _reset_pubsub_connection(self) -> None:
        """Reset the pub/sub connection by closing old and creating new subscription.

        This is used to recover from errors where the connection enters an invalid
        state. Creates a new dedicated connection for the listener.
        """
        redis_client = self._get_redis()
        if not redis_client:
            logger.error("Cannot reset pub/sub: Redis client not available")
            self._pubsub = None
            return

        # Close old dedicated pubsub connection if exists
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe(SYSTEM_STATUS_CHANNEL)
            except Exception as e:
                logger.debug(f"Error unsubscribing during reset (expected): {e}")
            try:
                await self._pubsub.close()
            except Exception as e:
                logger.debug(f"Error closing pubsub during reset (expected): {e}")
            self._pubsub = None

        # Create fresh dedicated subscription
        try:
            self._pubsub = await redis_client.subscribe_dedicated(SYSTEM_STATUS_CHANNEL)
            logger.info(f"Re-established pub/sub subscription on channel: {SYSTEM_STATUS_CHANNEL}")
        except Exception as e:
            logger.error(f"Failed to re-subscribe during reset: {e}", exc_info=True)
            self._pubsub = None

    async def _listen_for_updates(self) -> None:
        """Listen for system status updates from Redis pub/sub.

        Forwards received messages to all locally connected WebSocket clients.

        Recovery from errors is bounded to MAX_RECOVERY_ATTEMPTS to prevent
        unbounded recursion and stack overflow.
        """
        if not self._pubsub:
            logger.error("Cannot listen: pubsub not initialized")
            return

        redis_client = self._get_redis()
        if not redis_client:
            logger.error("Cannot listen: Redis client not available")
            return

        logger.info("Starting pub/sub listener loop")

        try:
            async for message in redis_client.listen(self._pubsub):
                if not self._pubsub_listening:
                    break

                # Reset recovery attempts on successful message processing
                self._recovery_attempts = 0

                # Extract the status data
                status_data = message.get("data")
                if not status_data:
                    continue

                logger.debug(f"Received system status from Redis: {type(status_data)}")

                # Forward to local WebSocket clients
                await self._send_to_local_clients(status_data)

        except asyncio.CancelledError:
            logger.info("Pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Error in pub/sub listener: {e}", exc_info=True)
            await self._attempt_listener_recovery()

    async def _attempt_listener_recovery(self) -> None:
        """Attempt to recover the pub/sub listener with bounded retries.

        This helper method is extracted to reduce branch complexity in
        _listen_for_updates(). Recovery is bounded to MAX_RECOVERY_ATTEMPTS
        to prevent unbounded recursion and stack overflow.
        """
        if not self._pubsub_listening:
            return

        self._recovery_attempts += 1
        if self._recovery_attempts > self.MAX_RECOVERY_ATTEMPTS:
            logger.error(
                f"Pub/sub listener recovery failed after {self.MAX_RECOVERY_ATTEMPTS} "
                "attempts. Giving up - manual restart required."
            )
            self._pubsub_listening = False
            return

        logger.info(
            f"Restarting pub/sub listener after error "
            f"(attempt {self._recovery_attempts}/{self.MAX_RECOVERY_ATTEMPTS})"
        )
        await asyncio.sleep(1)

        if not self._pubsub_listening:
            return

        # Clean up old pubsub and create fresh subscription
        await self._reset_pubsub_connection()
        if self._pubsub:
            self._listener_task = asyncio.create_task(self._listen_for_updates())
        else:
            logger.error("Failed to re-establish pub/sub connection")
            self._pubsub_listening = False

    async def _get_system_status(self) -> dict:
        """Gather current system status data.

        Returns:
            Dictionary containing system status information:
            - type: "system_status"
            - data: System metrics (GPU, cameras, queue, health)
            - timestamp: ISO format timestamp
        """
        # Get GPU stats
        gpu_stats = await self._get_latest_gpu_stats()

        # Get camera counts
        camera_stats = await self._get_camera_stats()

        # Get queue stats
        queue_stats = await self._get_queue_stats()

        # Get health status
        health_status = await self._get_health_status()

        return {
            "type": "system_status",
            "data": {
                "gpu": gpu_stats,
                "cameras": camera_stats,
                "queue": queue_stats,
                "health": health_status,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _get_latest_gpu_stats(self) -> dict:
        """Get latest GPU statistics from database.

        Returns:
            Dictionary with GPU stats (utilization, memory, etc.)
            Returns null values if no data available.
        """
        try:
            async with get_session() as session:
                stmt = select(GPUStats).order_by(GPUStats.recorded_at.desc()).limit(1)
                result = await session.execute(stmt)
                gpu_stat = result.scalar_one_or_none()

                if gpu_stat is None:
                    return {
                        "utilization": None,
                        "memory_used": None,
                        "memory_total": None,
                        "temperature": None,
                        "inference_fps": None,
                    }

                return {
                    "utilization": gpu_stat.gpu_utilization,
                    "memory_used": gpu_stat.memory_used,
                    "memory_total": gpu_stat.memory_total,
                    "temperature": gpu_stat.temperature,
                    "inference_fps": gpu_stat.inference_fps,
                }
        except Exception as e:
            logger.error(f"Failed to get GPU stats: {e}", exc_info=True)
            return {
                "utilization": None,
                "memory_used": None,
                "memory_total": None,
                "temperature": None,
                "inference_fps": None,
            }

    async def _get_camera_stats(self) -> dict:
        """Get camera statistics from database.

        Returns:
            Dictionary with camera counts (active, total)
        """
        try:
            async with get_session() as session:
                # Count total cameras
                total_stmt = select(func.count()).select_from(Camera)
                total_result = await session.execute(total_stmt)
                total_cameras = total_result.scalar_one()

                # Count active cameras (status = 'online')
                active_stmt = (
                    select(func.count()).select_from(Camera).where(Camera.status == "online")
                )
                active_result = await session.execute(active_stmt)
                active_cameras = active_result.scalar_one()

                return {
                    "active": active_cameras,
                    "total": total_cameras,
                }
        except Exception as e:
            logger.error(f"Failed to get camera stats: {e}", exc_info=True)
            return {
                "active": 0,
                "total": 0,
            }

    async def _get_queue_stats(self) -> dict:
        """Get processing queue statistics from Redis.

        Returns:
            Dictionary with queue counts (pending, processing)
        """
        try:
            redis_client = self._get_redis()
            if redis_client is None:
                return {"pending": 0, "processing": 0}

            # Get detection queue length
            detection_queue_len = await redis_client.get_queue_length(DETECTION_QUEUE)

            # Get analysis queue length
            analysis_queue_len = await redis_client.get_queue_length(ANALYSIS_QUEUE)

            return {
                "pending": detection_queue_len,
                "processing": analysis_queue_len,
            }
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}", exc_info=True)
            return {
                "pending": 0,
                "processing": 0,
            }

    async def _get_health_status(self) -> str:
        """Determine overall system health status.

        Returns:
            Health status: "healthy", "degraded", or "unhealthy"
        """
        try:
            # Check database health
            async with get_session() as session:
                await session.execute(select(func.count()).select_from(Camera))

            # Check Redis health
            redis_healthy = False
            try:
                redis_client = self._get_redis()
                if redis_client:
                    await redis_client.health_check()
                    redis_healthy = True
            except Exception:
                redis_healthy = False

            # Determine overall health
            if redis_healthy:
                return "healthy"
            else:
                return "degraded"

        except Exception as e:
            logger.error(f"Failed to check health status: {e}", exc_info=True)
            return "unhealthy"

    async def start_broadcasting(self, interval: float = 5.0) -> None:
        """Start periodic broadcasting of system status.

        Starts both the broadcast loop (for publishing status updates) and
        the pub/sub listener (for receiving updates from other instances).

        Args:
            interval: Seconds between broadcasts (default: 5.0)
        """
        if self._running:
            logger.warning("Broadcasting already running")
            return

        self._running = True

        # Start the pub/sub listener for multi-instance support
        await self._start_pubsub_listener()

        # Start the broadcast loop
        self._broadcast_task = asyncio.create_task(self._broadcast_loop(interval))
        logger.info(f"Started system status broadcasting (interval: {interval}s)")

    async def stop_broadcasting(self) -> None:
        """Stop periodic broadcasting of system status.

        Stops both the broadcast loop and the pub/sub listener.
        """
        self._running = False

        # Stop the broadcast loop
        if self._broadcast_task:
            self._broadcast_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._broadcast_task
            self._broadcast_task = None

        # Stop the pub/sub listener
        await self._stop_pubsub_listener()

        logger.info("Stopped system status broadcasting")

    async def _broadcast_loop(self, interval: float) -> None:
        """Background task that periodically broadcasts system status and performance.

        Broadcasts two message types:
        - system_status: Basic system health information
        - performance_update: Detailed performance metrics (if PerformanceCollector configured)

        Args:
            interval: Seconds between broadcasts
        """
        while self._running:
            try:
                # Only broadcast if there are active connections
                if self.connections:
                    status_data = await self._get_system_status()
                    await self.broadcast_status(status_data)

                    # Also broadcast detailed performance metrics if collector is configured
                    await self.broadcast_performance()

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}", exc_info=True)
                await asyncio.sleep(interval)


# Global broadcaster instance and initialization lock
_system_broadcaster: SystemBroadcaster | None = None
_broadcaster_lock: asyncio.Lock | None = None
# Thread lock to protect initialization of _broadcaster_lock itself
_init_lock = threading.Lock()


def _get_broadcaster_lock() -> asyncio.Lock:
    """Get the broadcaster initialization lock (lazy initialization).

    This ensures the lock is created in a thread-safe manner and in the
    correct event loop context. Uses a threading lock to protect the
    initial creation of the asyncio lock, preventing race conditions
    when multiple coroutines attempt to initialize concurrently.

    Must be called from within an async context.

    Returns:
        asyncio.Lock for broadcaster initialization
    """
    global _broadcaster_lock  # noqa: PLW0603
    if _broadcaster_lock is None:
        with _init_lock:
            # Double-check after acquiring thread lock
            if _broadcaster_lock is None:
                _broadcaster_lock = asyncio.Lock()
    return _broadcaster_lock


def get_system_broadcaster(
    redis_client: RedisClient | None = None,
    redis_getter: Callable[[], RedisClient | None] | None = None,
) -> SystemBroadcaster:
    """Get the global SystemBroadcaster instance (synchronous version).

    On first call, creates a new SystemBroadcaster with the provided Redis client
    or getter. Subsequent calls return the existing singleton but will also update
    the Redis client if provided.

    Note: This is a synchronous function that does NOT start the broadcaster.
    Call start_broadcasting() separately, or use get_system_broadcaster_async()
    for automatic initialization with Redis pub/sub.

    Args:
        redis_client: Optional Redis client instance. If the singleton exists and
            this is provided, it will update the singleton's Redis client.
        redis_getter: Optional callable that returns a Redis client or None.
            Only used during initial creation of the singleton.

    Returns:
        SystemBroadcaster instance (not started)
    """
    global _system_broadcaster  # noqa: PLW0603
    if _system_broadcaster is None:
        _system_broadcaster = SystemBroadcaster(
            redis_client=redis_client,
            redis_getter=redis_getter,
        )
    elif redis_client is not None:
        # Update Redis client on existing singleton
        _system_broadcaster.set_redis_client(redis_client)
    return _system_broadcaster


async def get_system_broadcaster_async(
    redis_client: RedisClient | None = None,
    redis_getter: Callable[[], RedisClient | None] | None = None,
    interval: float = 5.0,
) -> SystemBroadcaster:
    """Get or create the global SystemBroadcaster instance (async version).

    This function is thread-safe and handles concurrent initialization
    attempts using an async lock to prevent race conditions. It also
    starts the broadcaster if not already running.

    Args:
        redis_client: Optional Redis client instance. If the singleton exists and
            this is provided, it will update the singleton's Redis client.
        redis_getter: Optional callable that returns a Redis client or None.
            Only used during initial creation of the singleton.
        interval: Seconds between status broadcasts (default: 5.0)

    Returns:
        SystemBroadcaster instance (started)
    """
    global _system_broadcaster  # noqa: PLW0603

    # Fast path: broadcaster already exists and is running
    if _system_broadcaster is not None and _system_broadcaster._running:
        if redis_client is not None:
            _system_broadcaster.set_redis_client(redis_client)
        return _system_broadcaster

    # Slow path: need to initialize with lock
    lock = _get_broadcaster_lock()
    async with lock:
        # Double-check after acquiring lock (another coroutine may have initialized)
        if _system_broadcaster is None:
            _system_broadcaster = SystemBroadcaster(
                redis_client=redis_client,
                redis_getter=redis_getter,
            )
        elif redis_client is not None:
            _system_broadcaster.set_redis_client(redis_client)

        # Start if not running
        if not _system_broadcaster._running:
            await _system_broadcaster.start_broadcasting(interval)
            logger.info("Global system broadcaster initialized and started")

    return _system_broadcaster


async def stop_system_broadcaster() -> None:
    """Stop the global system broadcaster instance.

    This function is thread-safe and handles concurrent stop attempts.
    """
    global _system_broadcaster  # noqa: PLW0603

    lock = _get_broadcaster_lock()
    async with lock:
        if _system_broadcaster:
            await _system_broadcaster.stop_broadcasting()
            _system_broadcaster = None
            logger.info("Global system broadcaster stopped")


def reset_broadcaster_state() -> None:
    """Reset the global broadcaster state for testing purposes.

    This function is NOT thread-safe and should only be used in test
    fixtures to ensure clean state between tests. It resets both the
    broadcaster instance and the asyncio lock.

    Warning: Only use this in test teardown, never in production code.
    """
    global _system_broadcaster, _broadcaster_lock  # noqa: PLW0603
    _system_broadcaster = None
    _broadcaster_lock = None


# Alias for explicit sync usage in tests and imports
get_system_broadcaster_sync = get_system_broadcaster
