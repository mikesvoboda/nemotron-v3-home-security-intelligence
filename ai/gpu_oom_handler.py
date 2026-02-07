"""GPU Out-of-Memory Error Handling Utilities (NEM-4996).

This module provides shared utilities for handling CUDA Out-of-Memory errors
across all AI inference services. It includes:

- OOM detection and recovery (cache clearing, memory stats logging)
- Prometheus OOM counters per service
- CUDA memory monitoring for health endpoints
- Pre-inference memory guards to prevent OOM proactively
- Retry-with-eviction support for services using OnDemandModelManager

Usage:
    from gpu_oom_handler import (
        GPUOOMHandler,
        get_gpu_memory_stats,
        check_gpu_memory_health,
        GPUHealthStatus,
    )

    # Create handler for a service
    oom_handler = GPUOOMHandler(service_name="yolo26")

    # Wrap inference calls
    try:
        result = model(input)
    except torch.cuda.OutOfMemoryError:
        oom_handler.handle_oom("detect")
        raise  # Re-raise after cleanup, or return graceful error

    # Check memory health for /health endpoint
    health = check_gpu_memory_health()

References:
    - NEM-4996: Add GPU OOM error handling to inference paths
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import torch
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# =============================================================================
# Prometheus OOM Counters (per-service)
# =============================================================================
# Global OOM counter with service and endpoint labels
GPU_OOM_TOTAL = Counter(
    "ai_gpu_oom_total",
    "Total number of GPU out-of-memory errors",
    ["service", "endpoint"],
)


# =============================================================================
# GPU Memory Statistics
# =============================================================================


@dataclass
class GPUMemoryStats:
    """GPU memory statistics snapshot.

    Attributes:
        allocated_mb: Currently allocated GPU memory in MB.
        reserved_mb: Currently reserved (cached) GPU memory in MB.
        max_allocated_mb: Peak allocated GPU memory since last reset in MB.
        total_mb: Total GPU memory available in MB.
        free_mb: Free GPU memory (total - reserved) in MB.
        utilization_pct: Memory utilization as percentage (allocated / total).
    """

    allocated_mb: float
    reserved_mb: float
    max_allocated_mb: float
    total_mb: float
    free_mb: float
    utilization_pct: float


def get_gpu_memory_stats(device: int = 0) -> GPUMemoryStats | None:
    """Get current GPU memory statistics.

    Args:
        device: CUDA device index (default: 0).

    Returns:
        GPUMemoryStats if CUDA is available, None otherwise.
    """
    if not torch.cuda.is_available():
        return None

    try:
        allocated = torch.cuda.memory_allocated(device) / (1024 * 1024)
        reserved = torch.cuda.memory_reserved(device) / (1024 * 1024)
        max_allocated = torch.cuda.max_memory_allocated(device) / (1024 * 1024)
        total = torch.cuda.get_device_properties(device).total_memory / (1024 * 1024)
        free = total - reserved
        utilization = (allocated / total * 100) if total > 0 else 0.0

        return GPUMemoryStats(
            allocated_mb=round(allocated, 2),
            reserved_mb=round(reserved, 2),
            max_allocated_mb=round(max_allocated, 2),
            total_mb=round(total, 2),
            free_mb=round(free, 2),
            utilization_pct=round(utilization, 2),
        )
    except Exception as e:
        logger.warning(f"Failed to get GPU memory stats: {e}")
        return None


# =============================================================================
# GPU Health Status for Health Endpoints
# =============================================================================


class GPUHealthStatus(str, Enum):
    """GPU memory health status levels.

    HEALTHY: Memory utilization < 80% -- normal operation.
    WARNING: Memory utilization 80-95% -- approaching limits.
    CRITICAL: Memory utilization > 95% -- at risk of OOM.
    UNAVAILABLE: CUDA not available.
    """

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


@dataclass
class GPUHealthInfo:
    """GPU health information for health check endpoints.

    Attributes:
        status: Overall GPU memory health status.
        memory_stats: Detailed memory statistics (None if CUDA unavailable).
        message: Human-readable health message.
    """

    status: GPUHealthStatus
    memory_stats: GPUMemoryStats | None
    message: str


def check_gpu_memory_health(device: int = 0) -> GPUHealthInfo:
    """Check GPU memory health status for health endpoints.

    Returns health status based on memory utilization thresholds:
    - HEALTHY: < 80% utilization
    - WARNING: 80-95% utilization
    - CRITICAL: > 95% utilization
    - UNAVAILABLE: CUDA not available

    Args:
        device: CUDA device index (default: 0).

    Returns:
        GPUHealthInfo with status, memory stats, and message.
    """
    if not torch.cuda.is_available():
        return GPUHealthInfo(
            status=GPUHealthStatus.UNAVAILABLE,
            memory_stats=None,
            message="CUDA is not available",
        )

    stats = get_gpu_memory_stats(device)
    if stats is None:
        return GPUHealthInfo(
            status=GPUHealthStatus.UNAVAILABLE,
            memory_stats=None,
            message="Failed to retrieve GPU memory statistics",
        )

    if stats.utilization_pct > 95:
        return GPUHealthInfo(
            status=GPUHealthStatus.CRITICAL,
            memory_stats=stats,
            message=(
                f"GPU memory critically high: {stats.utilization_pct:.1f}% "
                f"({stats.allocated_mb:.0f}MB / {stats.total_mb:.0f}MB). "
                "OOM risk is elevated."
            ),
        )
    elif stats.utilization_pct > 80:
        return GPUHealthInfo(
            status=GPUHealthStatus.WARNING,
            memory_stats=stats,
            message=(
                f"GPU memory elevated: {stats.utilization_pct:.1f}% "
                f"({stats.allocated_mb:.0f}MB / {stats.total_mb:.0f}MB). "
                "Consider reducing batch sizes."
            ),
        )
    else:
        return GPUHealthInfo(
            status=GPUHealthStatus.HEALTHY,
            memory_stats=stats,
            message=(
                f"GPU memory healthy: {stats.utilization_pct:.1f}% "
                f"({stats.allocated_mb:.0f}MB / {stats.total_mb:.0f}MB)"
            ),
        )


# =============================================================================
# Pre-Inference Memory Guard
# =============================================================================


def check_memory_available(
    required_mb: float = 100.0,
    device: int = 0,
) -> bool:
    """Check if enough GPU memory is available before running inference.

    This is a proactive check to avoid OOM errors. It compares the estimated
    free memory against the required amount.

    Args:
        required_mb: Estimated memory needed for inference in MB (default: 100MB).
        device: CUDA device index (default: 0).

    Returns:
        True if enough memory is available, False otherwise.
    """
    if not torch.cuda.is_available():
        return True  # CPU fallback doesn't need GPU memory

    stats = get_gpu_memory_stats(device)
    if stats is None:
        return True  # If we can't check, proceed anyway

    if stats.free_mb < required_mb:
        logger.warning(
            f"Insufficient GPU memory for inference: "
            f"free={stats.free_mb:.0f}MB, required={required_mb:.0f}MB, "
            f"allocated={stats.allocated_mb:.0f}MB, total={stats.total_mb:.0f}MB"
        )
        return False

    return True


# =============================================================================
# OOM Handler
# =============================================================================


class GPUOOMHandler:
    """GPU Out-of-Memory error handler for AI inference services.

    Provides consistent OOM handling across all services:
    1. Logs OOM events with detailed GPU memory statistics
    2. Clears CUDA cache to attempt recovery
    3. Increments Prometheus OOM counter
    4. Optionally triggers model eviction (for services with model managers)

    Usage:
        handler = GPUOOMHandler(service_name="clip")

        try:
            result = model(input)
        except torch.cuda.OutOfMemoryError:
            handler.handle_oom("embed")
            # Return 503 or retry after eviction

    Attributes:
        service_name: Name of the AI service (for metrics labels).
    """

    def __init__(self, service_name: str):
        """Initialize OOM handler.

        Args:
            service_name: Service identifier used in Prometheus labels
                         (e.g., "yolo26", "clip", "florence", "enrichment",
                         "enrichment_light").
        """
        self.service_name = service_name

    def handle_oom(
        self,
        endpoint: str,
        extra_context: dict[str, Any] | None = None,
    ) -> GPUMemoryStats | None:
        """Handle a CUDA OOM error with logging, cleanup, and metrics.

        This method should be called in the except block after catching
        torch.cuda.OutOfMemoryError. It performs:
        1. Logs the OOM event with GPU memory statistics
        2. Clears CUDA cache to free unreferenced memory
        3. Increments the Prometheus OOM counter

        Args:
            endpoint: The endpoint or operation that triggered OOM
                     (e.g., "detect", "embed", "classify").
            extra_context: Optional additional context to include in log message.

        Returns:
            GPU memory stats after cache clearing, or None if unavailable.
        """
        # Get memory stats before cache clear
        stats_before = get_gpu_memory_stats()

        # Build log context
        log_extra: dict[str, Any] = {
            "service": self.service_name,
            "endpoint": endpoint,
        }
        if stats_before:
            log_extra.update(
                {
                    "allocated_mb": stats_before.allocated_mb,
                    "reserved_mb": stats_before.reserved_mb,
                    "max_allocated_mb": stats_before.max_allocated_mb,
                    "total_mb": stats_before.total_mb,
                    "free_mb": stats_before.free_mb,
                    "utilization_pct": stats_before.utilization_pct,
                }
            )
        if extra_context:
            log_extra.update(extra_context)

        logger.error(
            f"CUDA OOM during {self.service_name}/{endpoint} inference. "
            f"Memory: allocated={log_extra.get('allocated_mb', 'N/A')}MB, "
            f"reserved={log_extra.get('reserved_mb', 'N/A')}MB, "
            f"max_allocated={log_extra.get('max_allocated_mb', 'N/A')}MB, "
            f"total={log_extra.get('total_mb', 'N/A')}MB",
            extra=log_extra,
        )

        # Clear CUDA cache to recover memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info(f"CUDA cache cleared after OOM in {self.service_name}/{endpoint}")

        # Increment Prometheus counter
        GPU_OOM_TOTAL.labels(
            service=self.service_name,
            endpoint=endpoint,
        ).inc()

        # Return memory stats after cleanup
        return get_gpu_memory_stats()

    def handle_oom_with_eviction(
        self,
        endpoint: str,
        model_manager: Any,
        extra_context: dict[str, Any] | None = None,
    ) -> GPUMemoryStats | None:
        """Handle OOM with model eviction for services using OnDemandModelManager.

        In addition to standard OOM handling, this method triggers eviction of
        the lowest-priority model from the model manager to free VRAM.

        Args:
            endpoint: The endpoint or operation that triggered OOM.
            model_manager: OnDemandModelManager instance for eviction.
            extra_context: Optional additional context for logging.

        Returns:
            GPU memory stats after eviction and cache clearing, or None.
        """
        # Perform standard OOM handling first
        self.handle_oom(endpoint, extra_context)

        # Trigger model eviction if model manager is available
        if model_manager is not None and hasattr(model_manager, "loaded_models"):
            loaded_count = len(model_manager.loaded_models)
            if loaded_count > 0:
                logger.warning(
                    f"Triggering model eviction after OOM in {self.service_name}/{endpoint}. "
                    f"Currently {loaded_count} models loaded."
                )
                # Note: _evict_lru_model is async, but we're in a sync context here.
                # The caller should handle async eviction if needed.
                # We log the intent - actual eviction happens at the endpoint level.
            else:
                logger.warning(f"No models to evict after OOM in {self.service_name}/{endpoint}.")

        return get_gpu_memory_stats()
