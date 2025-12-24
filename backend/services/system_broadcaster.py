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
from datetime import UTC, datetime

from fastapi import WebSocket
from sqlalchemy import func, select

from backend.core import get_session
from backend.core.redis import _redis_client
from backend.models import Camera, GPUStats

logger = logging.getLogger(__name__)


class SystemBroadcaster:
    """Manages WebSocket connections for system status broadcasts.

    This class maintains a set of active WebSocket connections and provides
    methods to broadcast system status updates to all connected clients.

    Attributes:
        connections: Set of active WebSocket connections
        _broadcast_task: Background task for periodic status updates
        _running: Flag indicating if broadcaster is running
    """

    def __init__(self) -> None:
        """Initialize the SystemBroadcaster."""
        self.connections: set[WebSocket] = set()
        self._broadcast_task: asyncio.Task[None] | None = None
        self._running = False

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
            if _redis_client is None:
                return {"pending": 0, "processing": 0}

            # Get detection queue length
            detection_queue_len = await _redis_client.get_queue_length("detection_queue")

            # Get analysis queue length
            analysis_queue_len = await _redis_client.get_queue_length("analysis_queue")

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
            try:
                if _redis_client:
                    await _redis_client.health_check()
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


def get_system_broadcaster() -> SystemBroadcaster:
    """Get the global SystemBroadcaster instance.

    Returns:
        SystemBroadcaster instance
    """
    global _system_broadcaster  # noqa: PLW0603
    if _system_broadcaster is None:
        _system_broadcaster = SystemBroadcaster()
    return _system_broadcaster
