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

Thread Safety:
    This module uses a global singleton pattern. The semaphore is created
    lazily on first access and reused across all callers. The reset function
    is provided for testing purposes.
"""

from __future__ import annotations

import asyncio

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Global singleton semaphore instance
_inference_semaphore: asyncio.Semaphore | None = None


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
    global _inference_semaphore  # noqa: PLW0603

    if _inference_semaphore is None:
        settings = get_settings()
        max_concurrent = settings.ai_max_concurrent_inferences

        _inference_semaphore = asyncio.Semaphore(max_concurrent)

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
    global _inference_semaphore  # noqa: PLW0603
    _inference_semaphore = None
    logger.debug("AI inference semaphore reset")
