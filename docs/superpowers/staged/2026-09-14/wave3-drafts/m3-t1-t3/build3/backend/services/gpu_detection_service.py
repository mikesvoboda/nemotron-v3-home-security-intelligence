"""GPU Detection Service for Multi-GPU Support.

This module provides detection and monitoring of available GPUs using pynvml
(NVIDIA Management Library) with nvidia-smi fallback for containerized environments.

Related Issues:
    - NEM-3317: Implement GPU detection service with pynvml
    - NEM-3292: Multi-GPU Support Epic

Design Document:
    See docs/plans/2025-01-23-multi-gpu-support-design.md
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# VRAM requirements in MB for AI services
# These are estimates used for strategy calculations
AI_SERVICE_VRAM_REQUIREMENTS_MB: dict[str, int] = {
    "ai-llm": 8192,  # Nemotron enrichment: ~8GB
    "ai-enrichment": 2048,  # Age/Gender/ReID models combined: ~2GB
    "ai-florence": 4096,  # Florence-2 model: ~4GB
    "ai-clip": 2048,  # CLIP model: ~2GB
    "ai-yolo26": 100,  # YOLO26m TensorRT: ~100MB
}


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class GpuDevice:
    """Represents a detected GPU device.

    Attributes:
        index: GPU index (0-based)
        name: GPU device name (e.g., "NVIDIA RTX A5500")
        vram_total_mb: Total VRAM in megabytes
        vram_used_mb: Currently used VRAM in megabytes
        uuid: Unique identifier for the GPU
        compute_capability: CUDA compute capability (e.g., "8.6")
    """

    index: int
    name: str
    vram_total_mb: int
    vram_used_mb: int
    uuid: str
    compute_capability: str | None = None

    @property
    def vram_available_mb(self) -> int:
        """Return available VRAM in megabytes."""
        return self.vram_total_mb - self.vram_used_mb

    @property
    def vram_usage_percent(self) -> float:
        """Return VRAM usage as a percentage."""
        if self.vram_total_mb == 0:
            return 0.0
        return (self.vram_used_mb / self.vram_total_mb) * 100.0


@dataclass
class GpuUtilization:
    """Represents real-time GPU utilization.

    Attributes:
        gpu_index: GPU index
        gpu_utilization_percent: GPU core utilization percentage
        memory_utilization_percent: Memory bandwidth utilization percentage
        vram_used_mb: Currently used VRAM in megabytes
        vram_total_mb: Total VRAM in megabytes
        temperature_celsius: GPU temperature in Celsius (optional)
        power_watts: Current power draw in watts (optional)
    """

    gpu_index: int
    gpu_utilization_percent: float
    memory_utilization_percent: float
    vram_used_mb: int
    vram_total_mb: int
    temperature_celsius: float | None = None
    power_watts: float | None = None


# =============================================================================
# Async subprocess helper
# =============================================================================


async def async_subprocess_run(
    cmd: list[str],
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess asynchronously.

    Args:
        cmd: Command to run as list of arguments
        timeout: Timeout in seconds

    Returns:
        CompletedProcess with stdout, stderr, and returncode

    Raises:
        subprocess.TimeoutExpired: If command times out
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except TimeoutError as err:
        proc.kill()
        await proc.wait()
        raise subprocess.TimeoutExpired(cmd=" ".join(cmd), timeout=timeout) from err

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode or 0,
        stdout=stdout_bytes.decode("utf-8") if stdout_bytes else "",
        stderr=stderr_bytes.decode("utf-8") if stderr_bytes else "",
    )


# =============================================================================
# GPU Detection Service
# =============================================================================


class GpuDetectionService:
    """Service for detecting and monitoring GPU devices.

    Supports two detection methods:
    1. pynvml (NVIDIA Management Library) - preferred, more detailed info
    2. nvidia-smi subprocess - fallback for containers without pynvml

    Usage:
        service = GpuDetectionService()
        gpus = await service.detect_gpus()
        for gpu in gpus:
            util = await service.get_gpu_utilization(gpu.index)
    """

    def __init__(self) -> None:
        """Initialize the GPU detection service."""
        self._pynvml: ModuleType | None = None
        self._nvml_available: bool = False
        self._nvidia_smi_path: str | None = None
        self._nvml_initialized: bool = False

        # Try to initialize pynvml
        self._init_pynvml()

        # Find nvidia-smi as fallback
        self._nvidia_smi_path = shutil.which("nvidia-smi")

    def _init_pynvml(self) -> None:
        """Initialize pynvml library if available."""
        try:
            import pynvml

            self._pynvml = pynvml
            pynvml.nvmlInit()
            self._nvml_available = True
            self._nvml_initialized = True
            logger.info("pynvml initialized successfully")
        except ImportError:
            logger.info("pynvml not available, will use nvidia-smi fallback")
            self._nvml_available = False
        except Exception as e:
            logger.warning(f"pynvml initialization failed: {e}, using nvidia-smi fallback")
            self._nvml_available = False

    def _ensure_nvml(self) -> bool:
        """Ensure NVML is initialized, return True if available."""
        if not self._nvml_available or self._pynvml is None:
            return False

        if not self._nvml_initialized:
            try:
                self._pynvml.nvmlInit()
                self._nvml_initialized = True
            except Exception:
                return False

        return True

    async def detect_gpus(self) -> list[GpuDevice]:
        """Detect available GPUs.

        Returns:
            List of detected GPU devices, empty list if none found
        """
        if self._ensure_nvml():
            return await self._detect_gpus_pynvml()
        elif self._nvidia_smi_path:
            return await self._detect_gpus_nvidia_smi()
        else:
            logger.warning("No GPU detection method available")
            return []

    async def _detect_gpus_pynvml(self) -> list[GpuDevice]:
        """Detect GPUs using pynvml."""
        if self._pynvml is None:
            return []

        gpus: list[GpuDevice] = []

        try:
            device_count = self._pynvml.nvmlDeviceGetCount()

            for i in range(device_count):
                try:
                    gpu = await self._get_gpu_info_pynvml(i)
                    if gpu:
                        gpus.append(gpu)
                except Exception as e:
                    logger.warning(f"Failed to get info for GPU {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"pynvml detection failed: {e}")
            # Try fallback
            if self._nvidia_smi_path:
                return await self._detect_gpus_nvidia_smi()

        return gpus

    async def _get_gpu_info_pynvml(self, index: int) -> GpuDevice | None:
        """Get GPU info for a specific index using pynvml."""
        if self._pynvml is None:
            return None

        try:
            handle = self._pynvml.nvmlDeviceGetHandleByIndex(index)

            name = self._pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            uuid = self._pynvml.nvmlDeviceGetUUID(handle)
            if isinstance(uuid, bytes):
                uuid = uuid.decode("utf-8")

            memory_info = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_total_mb = memory_info.total // (1024 * 1024)
            vram_used_mb = memory_info.used // (1024 * 1024)

            # Get compute capability (optional - may not be available on all GPUs)
            compute_capability = None
            try:
                major, minor = self._pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                compute_capability = f"{major}.{minor}"
            except Exception:  # noqa: S110
                pass  # Compute capability is optional

            return GpuDevice(
                index=index,
                name=name,
                vram_total_mb=vram_total_mb,
                vram_used_mb=vram_used_mb,
                uuid=uuid,
                compute_capability=compute_capability,
            )

        except Exception as e:
            logger.warning(f"Failed to get GPU {index} info via pynvml: {e}")
            return None

    async def _detect_gpus_nvidia_smi(self) -> list[GpuDevice]:
        """Detect GPUs using nvidia-smi."""
        if not self._nvidia_smi_path:
            return []

        try:
            result = await async_subprocess_run(
                [
                    self._nvidia_smi_path,
                    "--query-gpu=index,name,memory.total,memory.used,uuid",
                    "--format=csv,noheader,nounits",
                ],
                timeout=10.0,
            )

            if result.returncode != 0:
                logger.warning(f"nvidia-smi failed: {result.stderr}")
                return []

            gpus: list[GpuDevice] = []

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue

                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    try:
                        gpus.append(
                            GpuDevice(
                                index=int(parts[0]),
                                name=parts[1],
                                vram_total_mb=int(parts[2]),
                                vram_used_mb=int(parts[3]),
                                uuid=parts[4],
                                compute_capability=None,
                            )
                        )
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse nvidia-smi line: {line}, error: {e}")
                        continue

            return gpus

        except subprocess.TimeoutExpired:
            logger.error("nvidia-smi timed out")
            return []
        except Exception as e:
            logger.error(f"nvidia-smi detection failed: {e}")
            return []

    async def get_gpu_utilization(self, gpu_index: int) -> GpuUtilization | None:
        """Get real-time utilization for a specific GPU.

        Args:
            gpu_index: Index of the GPU to query

        Returns:
            GpuUtilization object or None if GPU not found/accessible
        """
        if self._ensure_nvml():
            return await self._get_utilization_pynvml(gpu_index)
        elif self._nvidia_smi_path:
            return await self._get_utilization_nvidia_smi(gpu_index)
        else:
            return None

    async def _get_utilization_pynvml(self, gpu_index: int) -> GpuUtilization | None:
        """Get GPU utilization using pynvml."""
        if self._pynvml is None:
            return None

        try:
            handle = self._pynvml.nvmlDeviceGetHandleByIndex(gpu_index)

            # Get utilization rates
            util_rates = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = util_rates.gpu
            mem_util = util_rates.memory

            # Get memory info
            memory_info = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_total_mb = memory_info.total // (1024 * 1024)
            vram_used_mb = memory_info.used // (1024 * 1024)

            # Get temperature (optional - may not be available on all GPUs)
            temperature = None
            try:
                temperature = float(
                    self._pynvml.nvmlDeviceGetTemperature(handle, self._pynvml.NVML_TEMPERATURE_GPU)
                )
            except Exception:  # noqa: S110
                pass  # Temperature is optional

            # Get power usage (milliwatts to watts, optional)
            power_watts = None
            try:
                power_mw = self._pynvml.nvmlDeviceGetPowerUsage(handle)
                power_watts = power_mw / 1000.0
            except Exception:  # noqa: S110
                pass  # Power usage is optional

            return GpuUtilization(
                gpu_index=gpu_index,
                gpu_utilization_percent=float(gpu_util),
                memory_utilization_percent=float(mem_util),
                vram_used_mb=vram_used_mb,
                vram_total_mb=vram_total_mb,
                temperature_celsius=temperature,
                power_watts=power_watts,
            )

        except Exception as e:
            logger.warning(f"Failed to get utilization for GPU {gpu_index}: {e}")
            return None

    async def _get_utilization_nvidia_smi(self, gpu_index: int) -> GpuUtilization | None:
        """Get GPU utilization using nvidia-smi."""
        if not self._nvidia_smi_path:
            return None

        try:
            result = await async_subprocess_run(
                [
                    self._nvidia_smi_path,
                    f"--id={gpu_index}",
                    "--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw",
                    "--format=csv,noheader,nounits",
                ],
                timeout=10.0,
            )

            if result.returncode != 0:
                return None

            line = result.stdout.strip()
            if not line:
                return None

            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                # Get total VRAM separately (nvidia-smi doesn't give utilization %)
                vram_total_mb = await self._get_gpu_vram_total_nvidia_smi(gpu_index)

                return GpuUtilization(
                    gpu_index=gpu_index,
                    gpu_utilization_percent=float(parts[0]),
                    memory_utilization_percent=0.0,  # Would need separate calculation
                    vram_used_mb=int(parts[1]),
                    vram_total_mb=vram_total_mb,
                    temperature_celsius=float(parts[2]) if parts[2] else None,
                    power_watts=float(parts[3]) if parts[3] else None,
                )

            return None

        except Exception as e:
            logger.warning(f"nvidia-smi utilization query failed: {e}")
            return None

    async def _get_gpu_vram_total_nvidia_smi(self, gpu_index: int) -> int:
        """Get total VRAM for a GPU using nvidia-smi."""
        if not self._nvidia_smi_path:
            return 0

        try:
            result = await async_subprocess_run(
                [
                    self._nvidia_smi_path,
                    f"--id={gpu_index}",
                    "--query-gpu=memory.total",
                    "--format=csv,noheader,nounits",
                ],
                timeout=5.0,
            )

            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())

        except Exception:  # noqa: S110
            pass  # Returns 0 below on any failure

        return 0

    def get_service_vram_requirements(self) -> dict[str, int]:
        """Get VRAM requirements for all AI services.

        Returns:
            Dictionary mapping service names to VRAM requirements in MB
        """
        return AI_SERVICE_VRAM_REQUIREMENTS_MB.copy()


# =============================================================================
# Singleton Pattern
# =============================================================================

_gpu_detection_service: GpuDetectionService | None = None


def get_gpu_detection_service() -> GpuDetectionService:
    """Get the singleton GPU detection service instance.

    Returns:
        GpuDetectionService instance
    """
    global _gpu_detection_service  # noqa: PLW0603
    if _gpu_detection_service is None:
        _gpu_detection_service = GpuDetectionService()
    return _gpu_detection_service


def reset_gpu_detection_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _gpu_detection_service  # noqa: PLW0603
    _gpu_detection_service = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AI_SERVICE_VRAM_REQUIREMENTS_MB",
    "GpuDetectionService",
    "GpuDevice",
    "GpuUtilization",
    "async_subprocess_run",
    "get_gpu_detection_service",
    "reset_gpu_detection_service",
]
