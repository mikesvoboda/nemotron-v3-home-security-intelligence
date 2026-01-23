"""Unique entity counting service using Redis HyperLogLog (NEM-3414).

This service provides probabilistic cardinality estimation for analytics using
Redis HyperLogLog data structures. HyperLogLog provides:

- ~0.81% standard error (highly accurate for analytics)
- Constant memory usage (~12KB per counter regardless of cardinality)
- O(1) time complexity for both add and count operations

Use cases:
- Count unique cameras with activity per time window
- Count unique events per day/hour
- Count unique detection types (person, vehicle, animal)
- Count unique entity IDs for re-identification tracking
- Dashboard analytics for unique counts

Example usage:
    counter = await get_unique_counter_service()

    # Count unique cameras with detections today
    await counter.add_unique_camera("camera-123")
    await counter.add_unique_camera("camera-456")
    unique_count = await counter.get_unique_camera_count()  # Returns 2

    # Count unique events this hour
    await counter.add_unique_event("event-abc")
    hourly_events = await counter.get_unique_event_count(window="hourly")

    # Get memory-efficient analytics
    stats = await counter.get_cardinality_stats()
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, init_redis

logger = get_logger(__name__)

# Time window types for HLL key organization
TimeWindow = Literal["hourly", "daily", "weekly", "monthly"]


@dataclass(slots=True, frozen=True)
class CardinalityStats:
    """Statistics about unique entity counts."""

    unique_cameras: int
    unique_events: int
    unique_detections: int
    unique_entities: int
    time_window: str
    window_start: str
    estimated_error_rate: float = 0.0081  # HyperLogLog standard error ~0.81%


def _get_time_key(window: TimeWindow) -> str:
    """Get a time-based key suffix for the given window type.

    Args:
        window: Time window type

    Returns:
        String key suffix (e.g., "2024-01-15" for daily, "2024-01-15-14" for hourly)
    """
    now = datetime.now(UTC)
    if window == "hourly":
        return now.strftime("%Y-%m-%d-%H")
    elif window == "daily":
        return now.strftime("%Y-%m-%d")
    elif window == "weekly":
        # ISO week number
        return now.strftime("%Y-W%W")
    else:  # monthly
        return now.strftime("%Y-%m")


def _get_window_start(window: TimeWindow) -> str:
    """Get ISO timestamp for the start of the current time window.

    Args:
        window: Time window type

    Returns:
        ISO format timestamp string
    """
    now = datetime.now(UTC)
    if window == "hourly":
        return now.replace(minute=0, second=0, microsecond=0).isoformat()
    elif window == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    elif window == "weekly":
        # Start of week (Monday)
        days_since_monday = now.weekday()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta

        start = start - timedelta(days=days_since_monday)
        return start.isoformat()
    else:  # monthly
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


class UniqueCounterService:
    """Service for counting unique entities using HyperLogLog.

    Provides memory-efficient unique counting for analytics dashboards.
    Each HyperLogLog uses ~12KB of memory regardless of the number of
    unique elements tracked.
    """

    def __init__(self, redis_client: RedisClient):
        """Initialize the unique counter service.

        Args:
            redis_client: Connected Redis client
        """
        self._redis = redis_client
        self._settings = get_settings()
        self._prefix = self._settings.hll_key_prefix
        self._ttl = self._settings.hll_ttl_seconds

    def _build_key(self, metric: str, window: TimeWindow = "daily") -> str:
        """Build a HyperLogLog key with prefix and time window.

        Args:
            metric: Metric name (e.g., "cameras", "events")
            window: Time window for the counter

        Returns:
            Full Redis key (e.g., "hll:cameras:2024-01-15")
        """
        global_prefix = self._settings.redis_key_prefix
        time_key = _get_time_key(window)
        return f"{global_prefix}:{self._prefix}:{metric}:{time_key}"

    # Camera counting methods

    async def add_unique_camera(
        self,
        camera_id: str,
        window: TimeWindow = "daily",
    ) -> bool:
        """Record a camera that had activity.

        Args:
            camera_id: Camera identifier
            window: Time window for counting

        Returns:
            True if the cardinality estimate changed (new unique camera)
        """
        key = self._build_key("cameras", window)
        result = await self._redis.pfadd(key, camera_id)
        # Set TTL if this is a new key
        await self._redis.expire(key, self._ttl)
        return result == 1

    async def get_unique_camera_count(
        self,
        window: TimeWindow = "daily",
    ) -> int:
        """Get the count of unique cameras with activity.

        Args:
            window: Time window for counting

        Returns:
            Approximate count of unique cameras
        """
        key = self._build_key("cameras", window)
        return await self._redis.pfcount(key)

    # Event counting methods

    async def add_unique_event(
        self,
        event_id: str,
        window: TimeWindow = "daily",
    ) -> bool:
        """Record a unique security event.

        Args:
            event_id: Event identifier
            window: Time window for counting

        Returns:
            True if the cardinality estimate changed (new unique event)
        """
        key = self._build_key("events", window)
        result = await self._redis.pfadd(key, event_id)
        await self._redis.expire(key, self._ttl)
        return result == 1

    async def get_unique_event_count(
        self,
        window: TimeWindow = "daily",
    ) -> int:
        """Get the count of unique events.

        Args:
            window: Time window for counting

        Returns:
            Approximate count of unique events
        """
        key = self._build_key("events", window)
        return await self._redis.pfcount(key)

    # Detection counting methods

    async def add_unique_detection(
        self,
        detection_id: str,
        window: TimeWindow = "daily",
    ) -> bool:
        """Record a unique detection.

        Args:
            detection_id: Detection identifier
            window: Time window for counting

        Returns:
            True if the cardinality estimate changed
        """
        key = self._build_key("detections", window)
        result = await self._redis.pfadd(key, detection_id)
        await self._redis.expire(key, self._ttl)
        return result == 1

    async def get_unique_detection_count(
        self,
        window: TimeWindow = "daily",
    ) -> int:
        """Get the count of unique detections.

        Args:
            window: Time window for counting

        Returns:
            Approximate count of unique detections
        """
        key = self._build_key("detections", window)
        return await self._redis.pfcount(key)

    # Entity (person/vehicle) counting methods

    async def add_unique_entity(
        self,
        entity_id: str,
        window: TimeWindow = "daily",
    ) -> bool:
        """Record a unique tracked entity (person/vehicle).

        Args:
            entity_id: Entity identifier from re-identification
            window: Time window for counting

        Returns:
            True if the cardinality estimate changed
        """
        key = self._build_key("entities", window)
        result = await self._redis.pfadd(key, entity_id)
        await self._redis.expire(key, self._ttl)
        return result == 1

    async def get_unique_entity_count(
        self,
        window: TimeWindow = "daily",
    ) -> int:
        """Get the count of unique tracked entities.

        Args:
            window: Time window for counting

        Returns:
            Approximate count of unique entities
        """
        key = self._build_key("entities", window)
        return await self._redis.pfcount(key)

    # Detection type counting (person, vehicle, animal, etc.)

    async def add_detection_type(
        self,
        detection_type: str,
        window: TimeWindow = "daily",
    ) -> bool:
        """Record a detection type occurrence.

        This tracks unique detection types seen, not count of each type.
        Useful for knowing "what types of objects were detected today?"

        Args:
            detection_type: Type of detection (e.g., "person", "vehicle")
            window: Time window for counting

        Returns:
            True if this is a new type for the window
        """
        key = self._build_key("detection_types", window)
        result = await self._redis.pfadd(key, detection_type)
        await self._redis.expire(key, self._ttl)
        return result == 1

    async def get_unique_detection_type_count(
        self,
        window: TimeWindow = "daily",
    ) -> int:
        """Get count of unique detection types.

        Args:
            window: Time window for counting

        Returns:
            Count of unique detection types (typically small, <20)
        """
        key = self._build_key("detection_types", window)
        return await self._redis.pfcount(key)

    # Batch operations for efficiency

    async def add_batch_cameras(
        self,
        camera_ids: list[str],
        window: TimeWindow = "daily",
    ) -> int:
        """Add multiple cameras in a single operation.

        More efficient than individual adds when processing batches.

        Args:
            camera_ids: List of camera identifiers
            window: Time window for counting

        Returns:
            1 if cardinality estimate changed, 0 otherwise
        """
        if not camera_ids:
            return 0
        key = self._build_key("cameras", window)
        result = await self._redis.pfadd(key, *camera_ids)
        await self._redis.expire(key, self._ttl)
        return result

    async def add_batch_events(
        self,
        event_ids: list[str],
        window: TimeWindow = "daily",
    ) -> int:
        """Add multiple events in a single operation.

        Args:
            event_ids: List of event identifiers
            window: Time window for counting

        Returns:
            1 if cardinality estimate changed, 0 otherwise
        """
        if not event_ids:
            return 0
        key = self._build_key("events", window)
        result = await self._redis.pfadd(key, *event_ids)
        await self._redis.expire(key, self._ttl)
        return result

    # Aggregation across time windows

    async def get_merged_count(
        self,
        metric: str,
        windows: list[str],
    ) -> int:
        """Get the union cardinality across multiple time windows.

        Useful for queries like "unique cameras in the last 7 days"
        by merging daily HLLs.

        Args:
            metric: Metric name (cameras, events, etc.)
            windows: List of time window suffixes to merge

        Returns:
            Approximate count of unique items across all windows
        """
        global_prefix = self._settings.redis_key_prefix
        keys = [f"{global_prefix}:{self._prefix}:{metric}:{w}" for w in windows]
        # Filter to only keys that exist
        existing_keys = []
        for key in keys:
            if await self._redis.exists(key):
                existing_keys.append(key)
        if not existing_keys:
            return 0
        return await self._redis.pfcount(*existing_keys)

    # Statistics aggregation

    async def get_cardinality_stats(
        self,
        window: TimeWindow = "daily",
    ) -> CardinalityStats:
        """Get all cardinality statistics for a time window.

        Args:
            window: Time window for statistics

        Returns:
            CardinalityStats dataclass with all unique counts
        """
        # Gather all counts in parallel-like fashion
        cameras = await self.get_unique_camera_count(window)
        events = await self.get_unique_event_count(window)
        detections = await self.get_unique_detection_count(window)
        entities = await self.get_unique_entity_count(window)

        return CardinalityStats(
            unique_cameras=cameras,
            unique_events=events,
            unique_detections=detections,
            unique_entities=entities,
            time_window=window,
            window_start=_get_window_start(window),
        )


# Singleton instance
_unique_counter_service: UniqueCounterService | None = None


async def get_unique_counter_service() -> UniqueCounterService:
    """Get or create the unique counter service singleton.

    Returns:
        UniqueCounterService instance connected to Redis
    """
    global _unique_counter_service  # noqa: PLW0603
    if _unique_counter_service is None:
        redis_client = await init_redis()
        _unique_counter_service = UniqueCounterService(redis_client)
    return _unique_counter_service


async def reset_unique_counter_service() -> None:
    """Reset the unique counter service singleton (for testing)."""
    global _unique_counter_service  # noqa: PLW0603
    _unique_counter_service = None
