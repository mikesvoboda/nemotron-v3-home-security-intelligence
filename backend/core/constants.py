"""Application-wide constants.

This module provides centralized constants for:
- Redis queue names
- DLQ (dead-letter queue) names
- Redis key prefixes
- Global key prefix for multi-instance/blue-green deployments (NEM-1621)

Usage:
    from backend.core.constants import (
        DETECTION_QUEUE,
        ANALYSIS_QUEUE,
        DLQ_DETECTION_QUEUE,
        DLQ_ANALYSIS_QUEUE,
        get_prefixed_queue_name,
    )

    # Queue operations (use add_to_queue_safe for proper backpressure handling)
    # Use get_prefixed_queue_name for proper key namespacing
    prefixed_queue = get_prefixed_queue_name(DETECTION_QUEUE)
    result = await redis.add_to_queue_safe(prefixed_queue, data)
    await redis.get_queue_length(get_prefixed_queue_name(ANALYSIS_QUEUE))
"""

from functools import lru_cache

# -----------------------------------------------------------------------------
# Redis Queue Names
# -----------------------------------------------------------------------------
# Main processing queues
DETECTION_QUEUE = "detection_queue"
"""Queue for incoming detection jobs (images/videos from file watcher)."""

ANALYSIS_QUEUE = "analysis_queue"
"""Queue for batched detections ready for LLM analysis."""

# -----------------------------------------------------------------------------
# Dead-Letter Queue (DLQ) Names
# -----------------------------------------------------------------------------
DLQ_PREFIX = "dlq:"
"""Prefix for all dead-letter queues."""

DLQ_DETECTION_QUEUE = f"{DLQ_PREFIX}{DETECTION_QUEUE}"
"""DLQ for failed detection jobs."""

DLQ_ANALYSIS_QUEUE = f"{DLQ_PREFIX}{ANALYSIS_QUEUE}"
"""DLQ for failed LLM analysis jobs."""

# DLQ overflow prefix (for queue overflow policy)
DLQ_OVERFLOW_PREFIX = "dlq:overflow:"
"""Prefix for overflow DLQ queues when main queue is full."""


def get_dlq_name(queue_name: str) -> str:
    """Get the DLQ name for a given queue.

    Handles both with and without dlq: prefix - returns the full DLQ name.

    Args:
        queue_name: Original queue name (e.g., "detection_queue")

    Returns:
        Full DLQ name (e.g., "dlq:detection_queue")

    Examples:
        >>> get_dlq_name("detection_queue")
        "dlq:detection_queue"
        >>> get_dlq_name("dlq:detection_queue")
        "dlq:detection_queue"
    """
    if queue_name.startswith(DLQ_PREFIX):
        return queue_name
    return f"{DLQ_PREFIX}{queue_name}"


def get_dlq_overflow_name(queue_name: str) -> str:
    """Get the overflow DLQ name for a given queue.

    Args:
        queue_name: Original queue name (e.g., "detection_queue")

    Returns:
        Overflow DLQ name (e.g., "dlq:overflow:detection_queue")

    Examples:
        >>> get_dlq_overflow_name("detection_queue")
        "dlq:overflow:detection_queue"
    """
    # Strip any existing prefix to avoid double-prefixing
    clean_name = queue_name.removeprefix(DLQ_PREFIX).removeprefix("overflow:")
    return f"{DLQ_OVERFLOW_PREFIX}{clean_name}"


# -----------------------------------------------------------------------------
# Global Key Prefix Functions (NEM-1621)
# -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_redis_key_prefix() -> str:
    """Get the global Redis key prefix from settings.

    This is cached to avoid repeated settings lookups. The cache is cleared
    when settings change (e.g., in tests).

    Returns:
        The global Redis key prefix (default: "hsi")
    """
    # Import here to avoid circular imports
    from backend.core.config import get_settings

    return get_settings().redis_key_prefix


def get_prefixed_queue_name(queue_name: str) -> str:
    """Get a queue name with the global prefix applied.

    This function prepends the global Redis key prefix to queue names,
    enabling key isolation for multi-instance and blue-green deployments.

    Args:
        queue_name: Raw queue name (e.g., "detection_queue")

    Returns:
        Prefixed queue name (e.g., "hsi:queue:detection_queue")

    Examples:
        >>> get_prefixed_queue_name("detection_queue")
        "hsi:queue:detection_queue"
        >>> get_prefixed_queue_name("dlq:detection_queue")
        "hsi:queue:dlq:detection_queue"
    """
    prefix = _get_redis_key_prefix()
    return f"{prefix}:queue:{queue_name}"


# -----------------------------------------------------------------------------
# All exports
# -----------------------------------------------------------------------------
__all__ = [
    "ANALYSIS_QUEUE",
    "DETECTION_QUEUE",
    "DLQ_ANALYSIS_QUEUE",
    "DLQ_DETECTION_QUEUE",
    "DLQ_OVERFLOW_PREFIX",
    "DLQ_PREFIX",
    "get_dlq_name",
    "get_dlq_overflow_name",
    "get_prefixed_queue_name",
]
