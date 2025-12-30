"""GPU monitoring service using pynvml for NVIDIA GPU statistics.

This service polls GPU statistics at a configurable interval, stores them in the
database, and can expose them for real-time monitoring via WebSocket.
"""

import asyncio
import contextlib
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger, sanitize_error  # noqa: F401
from backend.models.gpu_stats import GPUStats

logger = get_logger(__name__)


class GPUMonitor:
    """Monitor NVIDIA GPU statistics using pynvml.

    Features:
    - Async polling at configurable intervals
    - Graceful handling of missing GPU or pynvml errors
    - In-memory stats history for quick access
    - Database persistence for historical analysis
    - Mock data mode when GPU is unavailable
    """

    def __init__(
        self,
        poll_interval: float | None = None,
        history_minutes: int | None = None,
        broadcaster: Any | None = None,
    ):
        """Initialize GPU monitor.

        Args:
            poll_interval: Polling interval in seconds (default from settings)
            history_minutes: Minutes of history to retain in memory (default from settings)
            broadcaster: Optional broadcaster for WebSocket updates
        """
        settings = get_settings()
        self.poll_interval = poll_interval or settings.gpu_poll_interval_seconds
        self.history_minutes = history_minutes or settings.gpu_stats_history_minutes
        self.broadcaster = broadcaster

        # Track running state
        self.running = False
        self._poll_task: asyncio.Task | None = None

        # In-memory circular buffer for stats history
        self._stats_history: deque[dict[str, Any]] = deque(maxlen=1000)

        # GPU state
        self._gpu_available = False
        self._nvml_initialized = False
        self._gpu_handle: Any = None
        self._gpu_name: str | None = None

        # Initialize pynvml
        self._initialize_nvml()

        logger.info(
            f"GPUMonitor initialized (poll_interval={self.poll_interval}s, "
            f"history_minutes={self.history_minutes}m, gpu_available={self._gpu_available})"
        )

    def _initialize_nvml(self) -> None:
        """Initialize NVIDIA Management Library (pynvml).

        Attempts to initialize pynvml and get the first GPU device.
        If this fails (no GPU, no drivers, no permissions), falls back to mock mode.
        """
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml_initialized = True

            # Try to get first GPU device
            try:
                self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self._gpu_name = pynvml.nvmlDeviceGetName(self._gpu_handle)
                self._gpu_available = True
                logger.info(f"GPU detected: {self._gpu_name}")
            except pynvml.NVMLError as e:
                logger.warning(f"No GPU device found: {e}. Will return mock data.")
                self._gpu_available = False

        except ImportError:
            logger.warning("pynvml not installed. GPU monitoring disabled. Will return mock data.")
            self._nvml_initialized = False
            self._gpu_available = False
        except Exception as e:
            logger.warning(f"Failed to initialize NVML: {e}. Will return mock data.")
            self._nvml_initialized = False
            self._gpu_available = False

    def _get_gpu_stats_real(self) -> dict[str, Any]:
        """Get real GPU statistics from pynvml.

        Returns:
            Dictionary containing GPU statistics

        Raises:
            RuntimeError: If pynvml is not initialized or GPU not available
        """
        if not self._gpu_available or not self._gpu_handle:
            raise RuntimeError("GPU not available")

        try:
            import pynvml

            # Get GPU utilization
            try:
                utilization = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                gpu_utilization = float(utilization.gpu)
            except pynvml.NVMLError:
                gpu_utilization = None

            # Get memory info
            try:
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                memory_used = int(memory_info.used / (1024 * 1024))  # Convert to MB
                memory_total = int(memory_info.total / (1024 * 1024))  # Convert to MB
            except pynvml.NVMLError:
                memory_used = None
                memory_total = None

            # Get temperature
            try:
                temperature = float(
                    pynvml.nvmlDeviceGetTemperature(self._gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
                )
            except pynvml.NVMLError:
                temperature = None

            # Get power usage
            try:
                power_usage = float(
                    pynvml.nvmlDeviceGetPowerUsage(self._gpu_handle) / 1000.0
                )  # Convert to Watts
            except pynvml.NVMLError:
                power_usage = None

            return {
                "gpu_name": self._gpu_name,
                "gpu_utilization": gpu_utilization,
                "memory_used": memory_used,
                "memory_total": memory_total,
                "temperature": temperature,
                "power_usage": power_usage,
                "recorded_at": datetime.now(UTC),
            }

        except Exception as e:
            logger.error(f"Error reading GPU stats: {e}")
            raise

    def _get_gpu_stats_mock(self) -> dict[str, Any]:
        """Get mock GPU statistics when real GPU is unavailable.

        Returns:
            Dictionary containing mock GPU statistics
        """
        return {
            "gpu_name": "Mock GPU (No NVIDIA GPU Available)",
            "gpu_utilization": None,
            "memory_used": None,
            "memory_total": None,
            "temperature": None,
            "power_usage": None,
            "recorded_at": datetime.now(UTC),
        }

    def get_current_stats(self) -> dict[str, Any]:
        """Get current GPU statistics.

        Returns:
            Dictionary containing current GPU stats (real or mock)
        """
        try:
            if self._gpu_available:
                return self._get_gpu_stats_real()
            else:
                return self._get_gpu_stats_mock()
        except Exception as e:
            logger.error(f"Failed to get GPU stats: {e}")
            return self._get_gpu_stats_mock()

    def get_stats_history(self, minutes: int | None = None) -> list[dict[str, Any]]:
        """Get GPU statistics history from memory.

        Args:
            minutes: Number of minutes of history to return (default: all available)

        Returns:
            List of GPU stats dictionaries, newest first
        """
        if minutes is None:
            # Return all history
            return list(reversed(self._stats_history))

        # Filter by time
        cutoff_time = datetime.now(UTC) - timedelta(minutes=minutes)
        filtered = [stats for stats in self._stats_history if stats["recorded_at"] >= cutoff_time]
        return list(reversed(filtered))

    async def _store_stats(self, stats: dict[str, Any]) -> None:
        """Store GPU statistics in database.

        Args:
            stats: Dictionary containing GPU statistics
        """
        try:
            async with get_session() as session:
                gpu_stats = GPUStats(
                    recorded_at=stats["recorded_at"],
                    gpu_name=stats["gpu_name"],
                    gpu_utilization=stats["gpu_utilization"],
                    memory_used=stats["memory_used"],
                    memory_total=stats["memory_total"],
                    temperature=stats["temperature"],
                    power_usage=stats["power_usage"],
                    inference_fps=None,  # Will be updated by inference services
                )
                session.add(gpu_stats)
                await session.commit()
                logger.debug(f"Stored GPU stats: {gpu_stats}")
        except Exception as e:
            logger.error(f"Failed to store GPU stats in database: {e}")

    async def _broadcast_stats(self, stats: dict[str, Any]) -> None:
        """Broadcast GPU statistics via WebSocket.

        Args:
            stats: Dictionary containing GPU statistics
        """
        if self.broadcaster is None:
            return

        try:
            # Convert datetime to ISO format for JSON serialization
            broadcast_stats = stats.copy()
            broadcast_stats["recorded_at"] = stats["recorded_at"].isoformat()

            await self.broadcaster.broadcast_gpu_stats(broadcast_stats)
            logger.debug("Broadcasted GPU stats via WebSocket")
        except Exception as e:
            logger.error(f"Failed to broadcast GPU stats: {e}")

    async def _poll_loop(self) -> None:
        """Main polling loop that collects and stores GPU statistics."""
        logger.info("GPU monitoring poll loop started")

        while self.running:
            try:
                # Get current stats
                stats = self.get_current_stats()

                # Add to in-memory history
                self._stats_history.append(stats)

                # Store in database
                await self._store_stats(stats)

                # Broadcast via WebSocket
                await self._broadcast_stats(stats)

                # Wait for next poll interval
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.debug("GPU monitor poll loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in GPU monitor poll loop: {e}")
                # Continue polling even if one iteration fails
                await asyncio.sleep(self.poll_interval)

        logger.info("GPU monitoring poll loop stopped")

    async def start(self) -> None:
        """Start GPU monitoring.

        This method is idempotent - calling it multiple times is safe.
        """
        if self.running:
            logger.warning("GPUMonitor already running")
            return

        logger.info("Starting GPU monitoring")
        self.running = True

        # Start polling task
        self._poll_task = asyncio.create_task(self._poll_loop())

        logger.info("GPU monitoring started successfully")

    async def stop(self) -> None:
        """Stop GPU monitoring and cleanup resources."""
        if not self.running:
            logger.debug("GPUMonitor not running, nothing to stop")
            return

        logger.info("Stopping GPU monitoring")
        self.running = False

        # Cancel polling task
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task

        self._poll_task = None

        # Shutdown NVML if initialized
        if self._nvml_initialized:
            try:
                import pynvml

                pynvml.nvmlShutdown()
                logger.debug("NVML shutdown successfully")
            except Exception as e:
                logger.warning(f"Error shutting down NVML: {e}")

        logger.info("GPU monitoring stopped")

    async def get_stats_from_db(
        self,
        minutes: int | None = None,
        limit: int | None = None,
    ) -> list[GPUStats]:
        """Get GPU statistics from database.

        Args:
            minutes: Number of minutes of history to retrieve
            limit: Maximum number of records to return

        Returns:
            List of GPUStats model instances, newest first
        """
        try:
            async with get_session() as session:
                query = select(GPUStats).order_by(GPUStats.recorded_at.desc())

                # Filter by time if specified
                if minutes is not None:
                    cutoff_time = datetime.now(UTC) - timedelta(minutes=minutes)
                    query = query.where(GPUStats.recorded_at >= cutoff_time)

                # Limit results if specified
                if limit is not None:
                    query = query.limit(limit)

                result = await session.execute(query)
                return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Failed to retrieve GPU stats from database: {e}")
            return []
