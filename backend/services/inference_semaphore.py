"""Shared semaphore for AI inference concurrency control (NEM-1463).

This module provides a shared asyncio.Semaphore that limits concurrent AI
inference operations across all services (RT-DETR detection, Nemotron analysis).
This prevents GPU/AI service overload under high traffic conditions.

Usage:
    from backend.services.inference_semaphore import get_inference_semaphore

    async def detect_objects(...):
        semaphore = get_inference_semaphore()
        async with semaphore:
            # Perform AI inference (this block limited to N concurrent operations)
            result = await ai_client.detect(...)
        return result

Configuration:
    The semaphore limit is controlled by the AI_MAX_CONCURRENT_INFERENCES
    environment variable (default: 4). This can be tuned based on:
    - GPU VRAM capacity (lower for constrained VRAM)
    - AI service architecture (higher for distributed services)
    - Expected traffic patterns

Benefits:
    - Prevents GPU OOM errors under high load
    - Ensures predictable latency by preventing request pileup
    - Allows graceful degradation instead of service crashes
    - Shared limit ensures total AI load stays bounded

Memory Pressure Throttling (NEM-1727):
    When GPU memory pressure is detected, the semaphore permits can be
    dynamically reduced to lower concurrency and relieve memory pressure:
    - WARNING level: Reduce to 75% of original permits
    - CRITICAL level: Reduce to 50% of original permits (minimum 1)

    Use reduce_permits_for_memory_pressure() and restore_permits_after_pressure()
    to dynamically adjust concurrency based on GPU memory conditions.

Thread Safety:
    This module uses a global singleton pattern. The semaphore is created
    lazily on first access and reused across all callers. The reset function
    is provided for testing purposes.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from backend.core.config import get_settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.services.gpu_monitor import MemoryPressureLevel

logger = get_logger(__name__)

# Global singleton semaphore instance
_inference_semaphore: asyncio.Semaphore | None = None

# Track original permit count for restoration after pressure relief
_original_permit_count: int | None = None
_current_permit_count: int | None = None
_throttled_for_pressure: bool = False


def get_inference_semaphore() -> asyncio.Semaphore:
    """Get or create the global AI inference semaphore.

    Returns a shared asyncio.Semaphore that limits concurrent AI inference
    operations. The limit is configured via AI_MAX_CONCURRENT_INFERENCES
    setting (default: 4).

    Returns:
        asyncio.Semaphore: The shared inference semaphore.

    Example:
        >>> semaphore = get_inference_semaphore()
        >>> async with semaphore:
        ...     result = await ai_service.infer(...)
    """
    global _inference_semaphore, _original_permit_count, _current_permit_count  # noqa: PLW0603

    if _inference_semaphore is None:
        settings = get_settings()
        max_concurrent = settings.ai_max_concurrent_inferences

        _inference_semaphore = asyncio.Semaphore(max_concurrent)
        _original_permit_count = max_concurrent
        _current_permit_count = max_concurrent

        logger.info(
            "AI inference semaphore initialized with max_concurrent=%d",
            max_concurrent,
        )

    return _inference_semaphore


def reset_inference_semaphore() -> None:
    """Reset the global inference semaphore (for testing).

    This clears the singleton instance, causing the next call to
    get_inference_semaphore() to create a fresh semaphore with
    current settings.

    Warning:
        Only use this in tests. Resetting during production operation
        could cause inconsistent concurrency limiting.
    """
    global _inference_semaphore, _original_permit_count, _current_permit_count, _throttled_for_pressure  # noqa: PLW0603
    _inference_semaphore = None
    _original_permit_count = None
    _current_permit_count = None
    _throttled_for_pressure = False
    logger.debug("AI inference semaphore reset")


# =============================================================================
# Memory Pressure Throttling (NEM-1727)
# =============================================================================


async def reduce_permits_for_memory_pressure(
    pressure_level: MemoryPressureLevel,
) -> None:
    """Reduce semaphore permits based on memory pressure level.

    Dynamically reduces the available permits in the inference semaphore
    to lower GPU memory usage. This helps prevent OOM errors by reducing
    concurrent inference operations.

    Reduction factors:
    - NORMAL: No change
    - WARNING: Reduce to 75% of original permits
    - CRITICAL: Reduce to 50% of original permits (minimum 1)

    Args:
        pressure_level: Current GPU memory pressure level

    Note:
        This function acquires permits from the semaphore to reduce
        available capacity. The permits are tracked and can be restored
        via restore_permits_after_pressure().
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    global _throttled_for_pressure, _current_permit_count  # noqa: PLW0603

    semaphore = get_inference_semaphore()

    if pressure_level == MemoryPressureLevel.NORMAL:
        # No reduction needed for NORMAL pressure
        return

    if _original_permit_count is None or _current_permit_count is None:
        logger.warning(
            "Cannot reduce permits: semaphore not initialized",
            extra={"pressure_level": pressure_level.value},
        )
        return

    # Calculate target permits based on pressure level
    if pressure_level == MemoryPressureLevel.CRITICAL:
        # Reduce to 50% of original (minimum 1)
        target_permits = max(1, _original_permit_count // 2)
    else:  # WARNING
        # Reduce to 75% of original
        target_permits = max(1, int(_original_permit_count * 0.75))

    # Calculate how many permits to remove
    permits_to_remove = _current_permit_count - target_permits

    if permits_to_remove <= 0:
        # Already at or below target
        logger.debug(
            "Semaphore already at or below target permits",
            extra={
                "current_permits": _current_permit_count,
                "target_permits": target_permits,
                "pressure_level": pressure_level.value,
            },
        )
        return

    # Acquire permits to reduce available capacity
    # This effectively "removes" permits from the semaphore
    acquired = 0
    for _ in range(permits_to_remove):
        # Use nowait to avoid blocking if semaphore is already fully utilized
        try:
            if semaphore._value > 0:  # Check internal value
                await asyncio.wait_for(semaphore.acquire(), timeout=0.1)
                acquired += 1
        except TimeoutError:
            # Semaphore is fully utilized, can't reduce further
            break

    _current_permit_count = _original_permit_count - acquired
    _throttled_for_pressure = True

    logger.warning(
        f"Reduced inference semaphore permits for {pressure_level.value} memory pressure",
        extra={
            "original_permits": _original_permit_count,
            "current_permits": _current_permit_count,
            "acquired_permits": acquired,
            "pressure_level": pressure_level.value,
        },
    )


async def restore_permits_after_pressure() -> None:
    """Restore semaphore permits after memory pressure is relieved.

    Releases permits that were acquired during memory pressure throttling,
    restoring the semaphore to its original capacity.

    Note:
        This should be called when memory pressure returns to NORMAL.
    """
    global _throttled_for_pressure, _current_permit_count  # noqa: PLW0603

    if not _throttled_for_pressure:
        # Not currently throttled
        return

    semaphore = get_inference_semaphore()

    if _original_permit_count is None or _current_permit_count is None:
        logger.warning("Cannot restore permits: permit counts not tracked")
        return

    # Calculate permits to restore
    permits_to_restore = _original_permit_count - _current_permit_count

    if permits_to_restore <= 0:
        _throttled_for_pressure = False
        return

    # Release the acquired permits
    for _ in range(permits_to_restore):
        semaphore.release()

    _current_permit_count = _original_permit_count
    _throttled_for_pressure = False

    logger.info(
        "Restored inference semaphore permits after memory pressure relief",
        extra={
            "restored_permits": permits_to_restore,
            "current_permits": _current_permit_count,
        },
    )
