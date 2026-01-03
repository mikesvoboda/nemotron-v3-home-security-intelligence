"""GPU monitoring service using pynvml, nvidia-smi, or AI container endpoints.

This service polls GPU statistics at a configurable interval, stores them in the
database, and can expose them for real-time monitoring via WebSocket.

Fallback order:
1. pynvml (direct NVML bindings - fastest, requires GPU access)
2. nvidia-smi subprocess (works when nvidia-smi is available in PATH)
3. AI container health endpoints (RT-DETRv2 reports VRAM usage)
4. Mock data (for development environments without GPU)

Note: Nemotron (llama.cpp server) does not expose GPU metrics, so GPU stats
from AI containers are obtained exclusively from RT-DETRv2.
"""

import asyncio
import contextlib
import shutil
import subprocess
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger, sanitize_error  # noqa: F401
from backend.models.gpu_stats import GPUStats

logger = get_logger(__name__)


class GPUMonitor:
    """Monitor NVIDIA GPU statistics using pynvml, nvidia-smi, or AI container endpoints.

    Features:
    - Async polling at configurable intervals
    - Graceful handling of missing GPU or pynvml errors
    - In-memory stats history for quick access
    - Database persistence for historical analysis
    - nvidia-smi subprocess fallback when pynvml unavailable
    - AI container querying when nvidia-smi unavailable
    - Mock data mode as final fallback
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

        # nvidia-smi availability (checked once at init)
        self._nvidia_smi_available = False
        self._nvidia_smi_path: str | None = None

        # Initialize pynvml first, then check nvidia-smi as fallback
        self._initialize_nvml()

        # If pynvml unavailable, check for nvidia-smi
        if not self._gpu_available:
            self._check_nvidia_smi()

        logger.info(
            f"GPUMonitor initialized (poll_interval={self.poll_interval}s, "
            f"history_minutes={self.history_minutes}m, gpu_available={self._gpu_available}, "
            f"nvidia_smi_available={self._nvidia_smi_available})"
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
            logger.warning("pynvml not installed. Will try nvidia-smi fallback.")
            self._nvml_initialized = False
            self._gpu_available = False
        except Exception as e:
            logger.warning(f"Failed to initialize NVML: {e}. Will try nvidia-smi fallback.")
            self._nvml_initialized = False
            self._gpu_available = False

    def _check_nvidia_smi(self) -> None:
        """Check if nvidia-smi is available as a fallback for GPU stats.

        This is used when pynvml is not available (e.g., running in a container
        where the NVIDIA driver libraries aren't mounted, but nvidia-smi is in PATH).
        """
        nvidia_smi_path = shutil.which("nvidia-smi")
        if nvidia_smi_path:
            # Verify it works by running a quick test query
            try:
                # nvidia_smi_path is validated via shutil.which, not user input
                result = subprocess.run(  # noqa: S603
                    [nvidia_smi_path, "--query-gpu=name", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    self._nvidia_smi_available = True
                    self._nvidia_smi_path = nvidia_smi_path
                    self._gpu_name = result.stdout.strip().split("\n")[0]
                    logger.info(f"nvidia-smi available at {nvidia_smi_path}, GPU: {self._gpu_name}")
                else:
                    logger.warning(f"nvidia-smi found but returned error: {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                logger.warning("nvidia-smi found but timed out during test query")
            except Exception as e:
                logger.warning(f"nvidia-smi found but failed during test: {e}")
        else:
            logger.debug("nvidia-smi not found in PATH")

    def _get_gpu_stats_nvidia_smi(self) -> dict[str, Any]:
        """Get GPU statistics using nvidia-smi subprocess.

        This is a fallback for when pynvml is not available but nvidia-smi is.
        Queries temperature, power draw, utilization, and memory in a single call.

        Returns:
            Dictionary containing GPU statistics

        Raises:
            RuntimeError: If nvidia-smi fails or is not available
        """
        if not self._nvidia_smi_available or not self._nvidia_smi_path:
            raise RuntimeError("nvidia-smi not available")

        try:
            # Query all needed metrics in one call for efficiency
            # Format: temperature, power, utilization, memory_used, memory_total, name
            # self._nvidia_smi_path is validated via shutil.which at init, not user input
            result = subprocess.run(  # noqa: S603
                [
                    self._nvidia_smi_path,
                    "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(f"nvidia-smi returned error: {result.stderr.strip()}")

            # Parse CSV output: "39, 29.61, 35, 175, 24576, NVIDIA RTX A5500"
            line = result.stdout.strip().split("\n")[0]  # Take first GPU if multiple
            parts = [p.strip() for p in line.split(",")]

            if len(parts) < 5:
                raise RuntimeError(f"Unexpected nvidia-smi output format: {line}")

            # Parse values with error handling for each field
            try:
                temperature = float(parts[0]) if parts[0] and parts[0] != "[N/A]" else None
            except ValueError:
                temperature = None

            try:
                power_usage = float(parts[1]) if parts[1] and parts[1] != "[N/A]" else None
            except ValueError:
                power_usage = None

            try:
                gpu_utilization = float(parts[2]) if parts[2] and parts[2] != "[N/A]" else None
            except ValueError:
                gpu_utilization = None

            try:
                memory_used = int(float(parts[3])) if parts[3] and parts[3] != "[N/A]" else None
            except ValueError:
                memory_used = None

            try:
                memory_total = int(float(parts[4])) if parts[4] and parts[4] != "[N/A]" else None
            except ValueError:
                memory_total = None

            gpu_name = parts[5] if len(parts) > 5 else self._gpu_name

            return {
                "gpu_name": gpu_name,
                "gpu_utilization": gpu_utilization,
                "memory_used": memory_used,
                "memory_total": memory_total,
                "temperature": temperature,
                "power_usage": power_usage,
                "recorded_at": datetime.now(UTC),
            }

        except subprocess.TimeoutExpired as e:
            raise RuntimeError("nvidia-smi timed out") from e
        except Exception as e:
            raise RuntimeError(f"Failed to get GPU stats via nvidia-smi: {e}") from e

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

        Provides simulated values for development environments without a GPU.
        Values are deterministic but vary slightly based on time to simulate
        realistic GPU activity patterns.

        Returns:
            Dictionary containing mock GPU statistics with simulated values
        """
        import math

        # Generate slightly varying values based on time for realism
        # Uses seconds since epoch modulo to create small fluctuations
        now = datetime.now(UTC)
        time_factor = now.timestamp() % 100 / 100  # 0.0 to 1.0, cycling every ~100 seconds

        # Simulate utilization between 15-45% (typical idle to light workload)
        base_util = 25.0
        util_variance = 10.0 * math.sin(time_factor * 2 * math.pi)
        gpu_utilization = round(base_util + util_variance, 1)

        # Simulate memory: 2-4 GB used of 24 GB total (RTX A5500 spec)
        base_memory = 3072  # 3 GB base
        memory_variance = int(512 * math.cos(time_factor * 2 * math.pi))
        memory_used = base_memory + memory_variance
        memory_total = 24576  # 24 GB in MB

        # Simulate temperature: 35-55°C (idle to moderate)
        base_temp = 42.0
        temp_variance = 8.0 * math.sin(time_factor * 2 * math.pi + 0.5)
        temperature = round(base_temp + temp_variance, 1)

        # Simulate power usage: 30-80W (idle to light workload)
        base_power = 50.0
        power_variance = 20.0 * math.sin(time_factor * 2 * math.pi + 1.0)
        power_usage = round(base_power + power_variance, 1)

        return {
            "gpu_name": "Mock GPU (Development Mode)",
            "gpu_utilization": gpu_utilization,
            "memory_used": memory_used,
            "memory_total": memory_total,
            "temperature": temperature,
            "power_usage": power_usage,
            "recorded_at": now,
        }

    def _parse_rtdetr_response(
        self, data: dict[str, Any]
    ) -> tuple[float, str | None, float | None, int | None, float | None]:
        """Parse RT-DETRv2 health response for GPU stats.

        Returns:
            Tuple of (vram_used_mb, gpu_device_name or None, gpu_utilization or None,
                      temperature or None, power_watts or None)
        """
        vram_mb = 0.0
        device = None
        gpu_utilization = None
        temperature = None
        power_watts = None

        if data.get("vram_used_gb") is not None:
            vram_mb = data["vram_used_gb"] * 1024  # Convert GB to MB
        if data.get("device"):
            device = data["device"]
        if data.get("gpu_utilization") is not None:
            gpu_utilization = data["gpu_utilization"]
        if data.get("temperature") is not None:
            temperature = data["temperature"]
        if data.get("power_watts") is not None:
            power_watts = data["power_watts"]

        return vram_mb, device, gpu_utilization, temperature, power_watts

    def _parse_vram_metric_line(self, line: str) -> float:
        """Parse a single Prometheus metric line for VRAM value.

        Returns VRAM in MB, or 0 if parsing fails.
        """
        parts = line.split()
        if len(parts) < 2:
            return 0.0
        try:
            value = float(parts[-1])
        except ValueError:
            return 0.0

        # Convert based on unit in metric name
        line_lower = line.lower()
        if "bytes" in line_lower:
            return value / (1024 * 1024)
        if "gb" in line_lower:
            return value * 1024
        # Assume MB if unit unclear
        return value

    async def _get_gpu_stats_from_ai_containers(self) -> dict[str, Any] | None:
        """Query AI containers for GPU statistics.

        Queries RT-DETRv2 health endpoint for GPU usage information.
        RT-DETRv2 reports vram_used_gb, gpu_utilization, temperature, and power_watts.

        Note: Nemotron (llama.cpp server) does not expose a /metrics endpoint,
        so GPU stats are obtained exclusively from RT-DETRv2.

        Returns:
            Dictionary containing aggregated GPU stats from AI containers, or None if unavailable.
        """
        settings = get_settings()
        total_vram_used_mb = 0.0
        gpu_name = "NVIDIA GPU (via AI Containers)"
        gpu_utilization: float | None = None
        temperature: int | None = None
        power_watts: float | None = None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Query RT-DETRv2 health endpoint
                try:
                    resp = await client.get(f"{settings.rtdetr_url}/health")
                    if resp.status_code == 200:
                        vram_mb, device, util, temp, power = self._parse_rtdetr_response(
                            resp.json()
                        )
                        total_vram_used_mb += vram_mb
                        if device:
                            gpu_name = f"NVIDIA GPU ({device})"
                        if util is not None:
                            gpu_utilization = util
                        if temp is not None:
                            temperature = temp
                        if power is not None:
                            power_watts = power
                        logger.debug(
                            f"RT-DETRv2 GPU stats: {vram_mb / 1024:.2f} GB, "
                            f"util={gpu_utilization}%, temp={temperature}C, power={power_watts}W"
                        )
                except Exception as e:
                    logger.debug(f"Failed to query RT-DETRv2 health: {e}")

                # Note: Nemotron (llama.cpp server) does not support a /metrics endpoint.
                # The /slots endpoint is used elsewhere for active slot monitoring.
                # GPU VRAM tracking is handled by the RT-DETRv2 container which has
                # better visibility into GPU memory usage.

                if total_vram_used_mb > 0 or gpu_utilization is not None:
                    # RTX A5500 has 24GB VRAM - use this as default
                    # Use actual values from RT-DETRv2 when available
                    return {
                        "gpu_name": gpu_name,
                        "gpu_utilization": gpu_utilization if gpu_utilization is not None else 0.0,
                        "memory_used": int(total_vram_used_mb),
                        "memory_total": 24576,  # 24GB in MB (RTX A5500 default)
                        "temperature": temperature if temperature is not None else 0,
                        "power_usage": power_watts if power_watts is not None else 0.0,
                        "recorded_at": datetime.now(UTC),
                    }

        except Exception as e:
            logger.warning(f"Failed to query AI containers for GPU stats: {e}")

        return None

    async def get_current_stats_async(self) -> dict[str, Any]:
        """Get current GPU statistics asynchronously.

        Tries in order:
        1. Local pynvml (if GPU available)
        2. nvidia-smi subprocess (if available)
        3. AI container health endpoints (RT-DETRv2)
        4. Mock data as fallback

        Returns:
            Dictionary containing current GPU stats
        """
        try:
            # First try local pynvml
            if self._gpu_available:
                return self._get_gpu_stats_real()

            # Try nvidia-smi subprocess as second option
            if self._nvidia_smi_available:
                try:
                    return self._get_gpu_stats_nvidia_smi()
                except Exception as e:
                    logger.warning(f"nvidia-smi fallback failed: {e}")
                    # Continue to try other methods

            # Try AI container endpoints
            ai_stats = await self._get_gpu_stats_from_ai_containers()
            if ai_stats is not None:
                return ai_stats

            # Fallback to mock data
            return self._get_gpu_stats_mock()
        except Exception as e:
            logger.error(f"Failed to get GPU stats: {e}")
            return self._get_gpu_stats_mock()

    def get_current_stats(self) -> dict[str, Any]:
        """Get current GPU statistics (sync version).

        Note: This sync version cannot query AI containers. Use get_current_stats_async()
        for the full functionality including AI container querying.

        Tries in order:
        1. Local pynvml (if GPU available)
        2. nvidia-smi subprocess (if available)
        3. Mock data as fallback

        Returns:
            Dictionary containing current GPU stats (real or mock)
        """
        try:
            if self._gpu_available:
                return self._get_gpu_stats_real()

            # Try nvidia-smi subprocess as fallback
            if self._nvidia_smi_available:
                try:
                    return self._get_gpu_stats_nvidia_smi()
                except Exception as e:
                    logger.warning(f"nvidia-smi fallback failed: {e}")
                    # Continue to mock data

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

    async def _calculate_inference_fps(self, session: Any) -> float | None:
        """Calculate inference FPS from recent detection throughput.

        Counts detections processed in the last 60 seconds and calculates
        the frames per second rate.

        Args:
            session: SQLAlchemy async session for database queries

        Returns:
            Inference FPS as a float, or None if calculation fails
        """
        try:
            from sqlalchemy import func

            from backend.models.detection import Detection

            # Count detections in last 60 seconds
            cutoff = datetime.now(UTC) - timedelta(seconds=60)
            result = await session.execute(
                select(func.count(Detection.id)).where(Detection.detected_at >= cutoff)
            )
            count = result.scalar() or 0
            return count / 60.0 if count >= 0 else 0.0
        except Exception as e:
            logger.warning(f"Failed to calculate inference FPS: {e}")
            return None

    async def _store_stats(self, stats: dict[str, Any]) -> None:
        """Store GPU statistics in database.

        Args:
            stats: Dictionary containing GPU statistics
        """
        try:
            async with get_session() as session:
                # Calculate inference FPS from recent detections
                inference_fps = await self._calculate_inference_fps(session)

                gpu_stats = GPUStats(
                    recorded_at=stats["recorded_at"],
                    gpu_name=stats["gpu_name"],
                    gpu_utilization=stats["gpu_utilization"],
                    memory_used=stats["memory_used"],
                    memory_total=stats["memory_total"],
                    temperature=stats["temperature"],
                    power_usage=stats["power_usage"],
                    inference_fps=inference_fps,
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
                # Get current stats (use async version to query AI containers)
                stats = await self.get_current_stats_async()

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
