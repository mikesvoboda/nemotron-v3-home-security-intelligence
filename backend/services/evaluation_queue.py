"""Evaluation queue service for background AI audit evaluation.

This service manages a Redis-backed priority queue for events that need
full AI audit evaluation. Events are automatically enqueued when created,
and processed by the BackgroundEvaluator when the GPU is idle.

Queue implementation:
- Uses Redis sorted set (ZSET) for priority-based ordering
- Higher priority events (higher risk scores) are evaluated first
- Persists across restarts since it's Redis-backed
- Supports checking queue status and managing pending evaluations

Redis Key: evaluation:pending (sorted set with event_id as member, priority as score)
"""

from __future__ import annotations

from backend.core.logging import get_logger
from backend.core.redis import RedisClient

logger = get_logger(__name__)


class EvaluationQueue:
    """Priority queue for AI audit evaluations backed by Redis.

    Uses a Redis sorted set to maintain a priority queue where:
    - Members are event IDs (as strings)
    - Scores are priorities (higher = evaluated first)

    Events with higher risk scores get higher priority to ensure
    potentially dangerous events are evaluated promptly.
    """

    QUEUE_KEY = "evaluation:pending"

    def __init__(self, redis_client: RedisClient) -> None:
        """Initialize the evaluation queue.

        Args:
            redis_client: Redis client instance for queue operations.
        """
        self._redis = redis_client

    async def enqueue(self, event_id: int, priority: int = 0) -> bool:
        """Add an event to the evaluation queue.

        If the event already exists in the queue, its priority will be updated.

        Args:
            event_id: The event ID to enqueue for evaluation.
            priority: Priority score (higher = evaluated first). Typically
                      the event's risk_score (0-100) so high-risk events
                      are evaluated first.

        Returns:
            True if the event was successfully enqueued or updated.
        """
        try:
            # zadd returns number of NEW elements added (0 if updated)
            await self._redis.zadd(self.QUEUE_KEY, {str(event_id): priority})
            logger.debug(
                f"Enqueued event {event_id} for evaluation with priority {priority}",
                extra={"event_id": event_id, "priority": priority},
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to enqueue event {event_id} for evaluation: {e}",
                extra={"event_id": event_id, "error": str(e)},
            )
            return False

    async def dequeue(self) -> int | None:
        """Remove and return the highest priority event from the queue.

        Returns:
            The event ID with highest priority, or None if queue is empty.
        """
        try:
            # zpopmax returns list of (member, score) tuples for highest scores
            result = await self._redis.zpopmax(self.QUEUE_KEY)

            if not result:
                return None

            # Result is [(member, score)] - member may be bytes or str
            member = result[0][0]
            if isinstance(member, bytes):
                member = member.decode("utf-8")

            event_id = int(member)
            logger.debug(
                f"Dequeued event {event_id} for evaluation",
                extra={"event_id": event_id},
            )
            return event_id

        except Exception as e:
            logger.error(
                f"Failed to dequeue event for evaluation: {e}",
                extra={"error": str(e)},
            )
            return None

    async def get_size(self) -> int:
        """Get the number of events pending evaluation.

        Returns:
            Number of events in the queue.
        """
        try:
            return await self._redis.zcard(self.QUEUE_KEY)
        except Exception as e:
            logger.error(f"Failed to get evaluation queue size: {e}")
            return 0

    async def get_pending_events(self, limit: int = 100) -> list[int]:
        """Get list of pending event IDs.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of event IDs currently in the queue.
        """
        try:
            result = await self._redis.zrange(self.QUEUE_KEY, 0, limit - 1)
            events = []
            for item in result:
                item_str = item.decode("utf-8") if isinstance(item, bytes) else item
                events.append(int(item_str))
            return events
        except Exception as e:
            logger.error(f"Failed to get pending events: {e}")
            return []

    async def remove(self, event_id: int) -> bool:
        """Remove a specific event from the queue.

        Useful for removing events that have been deleted or already evaluated.

        Args:
            event_id: The event ID to remove.

        Returns:
            True if the event was removed, False if it wasn't in the queue.
        """
        try:
            removed = await self._redis.zrem(self.QUEUE_KEY, str(event_id))
            if removed:
                logger.debug(
                    f"Removed event {event_id} from evaluation queue",
                    extra={"event_id": event_id},
                )
            return removed > 0
        except Exception as e:
            logger.error(f"Failed to remove event {event_id} from queue: {e}")
            return False

    async def is_queued(self, event_id: int) -> bool:
        """Check if an event is currently in the queue.

        Args:
            event_id: The event ID to check.

        Returns:
            True if the event is in the queue, False otherwise.
        """
        try:
            score = await self._redis.zscore(self.QUEUE_KEY, str(event_id))
            return score is not None
        except Exception as e:
            logger.error(f"Failed to check if event {event_id} is queued: {e}")
            return False


# Singleton management
_evaluation_queue: EvaluationQueue | None = None


def get_evaluation_queue(redis_client: RedisClient) -> EvaluationQueue:
    """Get or create the evaluation queue singleton.

    Args:
        redis_client: Redis client instance for queue operations.

    Returns:
        EvaluationQueue singleton instance.
    """
    global _evaluation_queue  # noqa: PLW0603
    if _evaluation_queue is None:
        _evaluation_queue = EvaluationQueue(redis_client)
    return _evaluation_queue


def reset_evaluation_queue() -> None:
    """Reset the evaluation queue singleton (for testing)."""
    global _evaluation_queue  # noqa: PLW0603
    _evaluation_queue = None
