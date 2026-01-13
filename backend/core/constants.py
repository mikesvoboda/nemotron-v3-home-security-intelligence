"""Application-wide constants.

This module provides centralized constants for:
- Redis queue names
- DLQ (dead-letter queue) names
- Redis key prefixes
- Global key prefix for multi-instance/blue-green deployments (NEM-1621)
- Cache invalidation reason constants (NEM-2575)

Usage:
    from backend.core.constants import (
        DETECTION_QUEUE,
        ANALYSIS_QUEUE,
        DLQ_DETECTION_QUEUE,
        DLQ_ANALYSIS_QUEUE,
        get_prefixed_queue_name,
        CacheInvalidationReason,
    )

    # Queue operations (use add_to_queue_safe for proper backpressure handling)
    # Use get_prefixed_queue_name for proper key namespacing
    prefixed_queue = get_prefixed_queue_name(DETECTION_QUEUE)
    result = await redis.add_to_queue_safe(prefixed_queue, data)
    await redis.get_queue_length(get_prefixed_queue_name(ANALYSIS_QUEUE))

    # Cache invalidation with typed reasons
    await cache.invalidate_events(reason=CacheInvalidationReason.EVENT_CREATED)
"""

from enum import Enum
from functools import lru_cache


# -----------------------------------------------------------------------------
# Cache Invalidation Reasons (NEM-2575)
# -----------------------------------------------------------------------------
class CacheInvalidationReason(str, Enum):
    """Standardized reasons for cache invalidation.

    Use these constants instead of magic strings when invalidating cache entries.
    This ensures consistency and prevents typos across the codebase.

    Categories:
    - Event operations: EVENT_CREATED, EVENT_UPDATED, EVENT_DELETED, EVENT_RESTORED
    - Camera operations: CAMERA_CREATED, CAMERA_UPDATED, CAMERA_DELETED, CAMERA_RESTORED
    - Detection operations: DETECTION_CREATED, DETECTION_UPDATED, DETECTION_DELETED
    - Alert operations: ALERT_RULE_CREATED, ALERT_RULE_UPDATED, ALERT_RULE_DELETED
    - Alert state changes: ALERT_CREATED, ALERT_ACKNOWLEDGED
    - System operations: STATUS_CHANGED, GRACEFUL_SHUTDOWN, MANUAL

    Usage:
        from backend.core.constants import CacheInvalidationReason

        # In production code
        await cache.invalidate_event_stats(reason=CacheInvalidationReason.EVENT_CREATED)
        await cache.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_DELETED)

        # In tests
        mock_cache.invalidate_events.assert_called_once_with(
            reason=CacheInvalidationReason.EVENT_UPDATED
        )
    """

    # Event lifecycle operations
    EVENT_CREATED = "event_created"
    """Cache invalidation when a new event is created."""

    EVENT_UPDATED = "event_updated"
    """Cache invalidation when an event is modified."""

    EVENT_DELETED = "event_deleted"
    """Cache invalidation when an event is deleted."""

    EVENT_RESTORED = "event_restored"
    """Cache invalidation when a soft-deleted event is restored."""

    # Camera lifecycle operations
    CAMERA_CREATED = "camera_created"
    """Cache invalidation when a new camera is added."""

    CAMERA_UPDATED = "camera_updated"
    """Cache invalidation when camera settings are modified."""

    CAMERA_DELETED = "camera_deleted"
    """Cache invalidation when a camera is removed."""

    CAMERA_RESTORED = "camera_restored"
    """Cache invalidation when a soft-deleted camera is restored."""

    # Detection lifecycle operations
    DETECTION_CREATED = "detection_created"
    """Cache invalidation when a new detection is recorded."""

    DETECTION_UPDATED = "detection_updated"
    """Cache invalidation when a detection is modified."""

    DETECTION_DELETED = "detection_deleted"
    """Cache invalidation when a detection is removed."""

    DETECTION_CHANGED = "detection_changed"
    """Cache invalidation for generic detection changes (bulk operations)."""

    # Alert rule lifecycle operations
    ALERT_RULE_CREATED = "alert_rule_created"
    """Cache invalidation when a new alert rule is created."""

    ALERT_RULE_UPDATED = "alert_rule_updated"
    """Cache invalidation when an alert rule is modified."""

    ALERT_RULE_DELETED = "alert_rule_deleted"
    """Cache invalidation when an alert rule is removed."""

    # Alert state changes
    ALERT_CREATED = "alert_created"
    """Cache invalidation when a new alert is triggered."""

    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    """Cache invalidation when an alert is acknowledged."""

    # System operations
    STATUS_CHANGED = "status_changed"
    """Cache invalidation when system status changes."""

    GRACEFUL_SHUTDOWN = "graceful_shutdown"
    """Cache invalidation during graceful service shutdown."""

    MANUAL = "manual"
    """Cache invalidation triggered manually (e.g., admin action, debugging)."""

    # Test-specific reasons (used in integration/unit tests)
    CONCURRENT_TEST = "concurrent_test"
    """Cache invalidation during concurrent cache testing."""

    TEST = "test"
    """Generic test-related cache invalidation."""

    def __str__(self) -> str:
        """Return string representation of invalidation reason."""
        return self.value


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
    "CacheInvalidationReason",
    "get_dlq_name",
    "get_dlq_overflow_name",
    "get_prefixed_queue_name",
]
