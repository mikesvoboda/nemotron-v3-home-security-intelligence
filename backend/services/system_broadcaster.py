"""WebSocket broadcaster for system status updates.

This module manages WebSocket connections and broadcasts real-time system
status updates to connected clients. It handles:

- Connection lifecycle management
- Periodic system status broadcasting
- GPU statistics
- Camera status
- Processing queue status
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import WebSocket
from sqlalchemy import func, select

from backend.core import get_session
from backend.models import Camera, GPUStats

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = logging.getLogger(__name__)


class SystemBroadcaster:
    """Manages WebSocket connections for system status broadcasts.

    This class maintains a set of active WebSocket connections and provides
    methods to broadcast system status updates to all connected clients.

    Attributes:
        connections: Set of active WebSocket connections
        _broadcast_task: Background task for periodic status updates
        _running: Flag indicating if broadcaster is running
        _redis_client: Injected Redis client instance (optional)
        _redis_getter: Callable that returns Redis client (alternative to direct injection)
    """

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
        self._running = False
        self._redis_client = redis_client
        self._redis_getter = redis_getter

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
        """Broadcast system status to all connected clients.

        Removes any connections that fail to receive the message.

        Args:
            status_data: System status data to broadcast
        """
        if not self.connections:
            return

        failed_connections = set()

        for websocket in self.connections:
            try:
                await websocket.send_json(status_data)
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
            detection_queue_len = await redis_client.get_queue_length("detection_queue")

            # Get analysis queue length
            analysis_queue_len = await redis_client.get_queue_length("analysis_queue")

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

        Args:
            interval: Seconds between broadcasts (default: 5.0)
        """
        if self._running:
            logger.warning("Broadcasting already running")
            return

        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop(interval))
        logger.info(f"Started system status broadcasting (interval: {interval}s)")

    async def stop_broadcasting(self) -> None:
        """Stop periodic broadcasting of system status."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._broadcast_task
            self._broadcast_task = None
        logger.info("Stopped system status broadcasting")

    async def _broadcast_loop(self, interval: float) -> None:
        """Background task that periodically broadcasts system status.

        Args:
            interval: Seconds between broadcasts
        """
        while self._running:
            try:
                # Only broadcast if there are active connections
                if self.connections:
                    status_data = await self._get_system_status()
                    await self.broadcast_status(status_data)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}", exc_info=True)
                await asyncio.sleep(interval)


# Global broadcaster instance
_system_broadcaster: SystemBroadcaster | None = None


def get_system_broadcaster(
    redis_client: RedisClient | None = None,
    redis_getter: Callable[[], RedisClient | None] | None = None,
) -> SystemBroadcaster:
    """Get the global SystemBroadcaster instance.

    On first call, creates a new SystemBroadcaster with the provided Redis client
    or getter. Subsequent calls return the existing singleton but will also update
    the Redis client if provided.

    Args:
        redis_client: Optional Redis client instance. If the singleton exists and
            this is provided, it will update the singleton's Redis client.
        redis_getter: Optional callable that returns a Redis client or None.
            Only used during initial creation of the singleton.

    Returns:
        SystemBroadcaster instance
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
