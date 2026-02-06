"""Batch coalescer service for merging similar detections.

Phase 5: Batching and Scheduling Optimization

This service merges compatible detections into single LLM inference calls to improve
throughput. Detections are coalescable when they share:
- Same camera
- Same primary object type
- Similar confidence levels (within tolerance)
- Combined count within max batch size

Priority Levels:
    P0 (CRITICAL): Weapon detections, unknown persons at night
    P1 (HIGH): Unknown vehicles
    P2 (NORMAL): Regular person/object detections during day
    P3 (LOW): Known faces/household members

Target: 20-40% reduction in inference count through coalescing.

Redis Keys:
    coalesce:candidates:{camera_id} - Sorted set of pending candidates by timestamp
    coalesce:candidate:{batch_id}   - JSON serialized candidate data
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Type alias for Redis client (can be sync or async mock)
type RedisClient = Any


class Priority(IntEnum):
    """Priority levels for detection processing.

    Higher numeric values indicate higher priority (processed first).
    P0 is critical/immediate, P3 is lowest priority.
    """

    P3_LOW = 1  # Known faces, household members
    P2_NORMAL = 2  # Regular daytime detections
    P1_HIGH = 3  # Unknown vehicles
    P0_CRITICAL = 4  # Weapons, unknown persons at night, fire/smoke


# Object types that indicate weapons (trigger P0)
WEAPON_TYPES: frozenset[str] = frozenset(
    {
        "gun",
        "pistol",
        "rifle",
        "firearm",
        "handgun",
        "knife",
        "machete",
        "sword",
        "weapon",
    }
)

# Object types that indicate vehicles (trigger P1)
VEHICLE_TYPES: frozenset[str] = frozenset(
    {
        "car",
        "truck",
        "van",
        "suv",
        "vehicle",
        "motorcycle",
        "bus",
    }
)

# Critical object types that always get P0 priority
CRITICAL_TYPES: frozenset[str] = frozenset(
    {
        "fire",
        "smoke",
        "intruder",
    }
)


@dataclass
class CoalesceCandidate:
    """Represents a batch that is a candidate for coalescing.

    Attributes:
        batch_id: Unique identifier for this batch
        camera_id: Camera that produced these detections
        detection_ids: List of detection IDs in this batch
        object_types: List of detected object types
        avg_confidence: Average confidence score across detections
        created_at: When this candidate was registered
        priority: Calculated priority level (optional, computed if not provided)
    """

    batch_id: str
    camera_id: str
    detection_ids: list[int]
    object_types: list[str]
    avg_confidence: float
    created_at: datetime
    priority: Priority | None = None

    def to_json(self) -> str:
        """Serialize candidate to JSON for Redis storage."""
        return json.dumps(
            {
                "batch_id": self.batch_id,
                "camera_id": self.camera_id,
                "detection_ids": self.detection_ids,
                "object_types": self.object_types,
                "avg_confidence": self.avg_confidence,
                "created_at": self.created_at.isoformat(),
                "priority": self.priority.value if self.priority else None,
            }
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> CoalesceCandidate:
        """Deserialize candidate from JSON."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        parsed = json.loads(data)
        return cls(
            batch_id=parsed["batch_id"],
            camera_id=parsed["camera_id"],
            detection_ids=parsed["detection_ids"],
            object_types=parsed["object_types"],
            avg_confidence=parsed["avg_confidence"],
            created_at=datetime.fromisoformat(parsed["created_at"]),
            priority=Priority(parsed["priority"]) if parsed.get("priority") else None,
        )

    @property
    def primary_object_type(self) -> str | None:
        """Get the most common object type in this batch."""
        if not self.object_types:
            return None
        # Find most frequent type
        type_counts: dict[str, int] = {}
        for obj_type in self.object_types:
            type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
        return max(type_counts.keys(), key=lambda t: type_counts[t])


@dataclass
class CoalesceResult:
    """Result of a batch merge operation.

    Attributes:
        merged_batch_id: ID of the resulting merged batch
        source_batch_ids: IDs of batches that were merged
        combined_detection_ids: All detection IDs in merged batch
        detection_count_before: Number of batches before merge
        detection_count_after: Number of batches after merge (always 1)
        merge_count: Number of batches that were merged
    """

    merged_batch_id: str
    source_batch_ids: list[str]
    combined_detection_ids: list[int]
    detection_count_before: int
    detection_count_after: int
    merge_count: int

    @property
    def inference_reduction_pct(self) -> float:
        """Calculate percentage reduction in inference calls.

        Returns:
            Percentage reduction (0-100). E.g., 2 batches merged = 50% reduction.
        """
        if self.detection_count_before <= 0:
            return 0.0
        reduction = self.detection_count_before - self.detection_count_after
        return (reduction / self.detection_count_before) * 100.0


@dataclass
class CoalescerMetrics:
    """Metrics tracking for coalescing operations."""

    merges_attempted: int = 0
    merges_successful: int = 0
    total_batches_processed: int = 0
    total_batches_merged: int = 0
    total_inference_reduction: float = 0.0


class BatchCoalescer:
    """Coalesces compatible detection batches to reduce inference calls.

    This service tracks pending batches as candidates for coalescing and merges
    compatible ones before LLM inference. Compatibility is determined by:
    - Same camera ID
    - Same primary object type
    - Similar confidence levels (within tolerance)
    - Combined size within max batch limit

    Example:
        >>> coalescer = BatchCoalescer(redis_client=redis)
        >>> candidate1 = CoalesceCandidate(...)
        >>> await coalescer.register_candidate(candidate1)
        >>> compatible = await coalescer.find_compatible_candidates(candidate1)
        >>> if compatible:
        ...     result = await coalescer.merge_batches([candidate1] + compatible)
    """

    # Redis key prefixes
    CANDIDATES_KEY_PREFIX = "coalesce:candidates"
    CANDIDATE_DATA_PREFIX = "coalesce:candidate"

    # TTL for candidate tracking (10 minutes)
    CANDIDATE_TTL_SECONDS = 600

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        max_batch_size: int | None = None,
        coalesce_window_seconds: float | None = None,
        confidence_tolerance: float | None = None,
    ):
        """Initialize batch coalescer.

        Args:
            redis_client: Redis client for candidate tracking
            max_batch_size: Maximum detections in a merged batch (default from settings)
            coalesce_window_seconds: Time window for finding compatible candidates
            confidence_tolerance: Max confidence difference for compatibility
        """
        self._redis = redis_client
        settings = get_settings()

        # Configuration with defaults
        self.max_batch_size: int = (
            max_batch_size
            if max_batch_size is not None
            else getattr(settings, "coalesce_max_batch_size", 10)
        )
        self.coalesce_window_seconds: float = (
            coalesce_window_seconds
            if coalesce_window_seconds is not None
            else getattr(settings, "coalesce_window_seconds", 5.0)
        )
        self.confidence_tolerance: float = (
            confidence_tolerance
            if confidence_tolerance is not None
            else getattr(settings, "coalesce_confidence_tolerance", 0.15)
        )

        # Metrics tracking
        self._metrics = CoalescerMetrics()

        logger.debug(
            "BatchCoalescer initialized",
            extra={
                "max_batch_size": self.max_batch_size,
                "coalesce_window_seconds": self.coalesce_window_seconds,
                "confidence_tolerance": self.confidence_tolerance,
            },
        )

    def is_compatible(self, batch1: CoalesceCandidate, batch2: CoalesceCandidate) -> bool:
        """Check if two batches can be coalesced.

        Batches are compatible if they have:
        - Same camera ID
        - Same primary object type
        - Similar confidence (within tolerance)
        - Combined size within max batch limit

        Args:
            batch1: First batch candidate
            batch2: Second batch candidate

        Returns:
            True if batches can be merged
        """
        # Must be same camera
        if batch1.camera_id != batch2.camera_id:
            return False

        # Must have same primary object type
        if batch1.primary_object_type != batch2.primary_object_type:
            return False

        # Combined size must not exceed max
        combined_size = len(batch1.detection_ids) + len(batch2.detection_ids)
        if combined_size > self.max_batch_size:
            return False

        # Confidence must be within tolerance
        confidence_diff = abs(batch1.avg_confidence - batch2.avg_confidence)
        return not confidence_diff > self.confidence_tolerance

    def calculate_priority(
        self,
        object_types: list[str],
        confidence: float,  # noqa: ARG002 - reserved for future confidence-based priority
        time_of_day: str = "day",
        is_known_face: bool = False,
    ) -> Priority:
        """Calculate processing priority for a detection batch.

        Priority is determined by:
        - P0 (CRITICAL): Weapons, unknown persons at night, fire/smoke
        - P1 (HIGH): Unknown vehicles
        - P2 (NORMAL): Regular detections during day
        - P3 (LOW): Known faces/household members

        Args:
            object_types: List of detected object types
            confidence: Average confidence score
            time_of_day: "day" or "night"
            is_known_face: Whether detection matches a known face

        Returns:
            Priority level for processing
        """
        # Known faces are always low priority
        if is_known_face:
            return Priority.P3_LOW

        # Normalize object types to lowercase
        types_lower = {t.lower() for t in object_types}

        # Check for weapons - always P0
        if types_lower & WEAPON_TYPES:
            return Priority.P0_CRITICAL

        # Check for critical types (fire, smoke, intruder) - always P0
        if types_lower & CRITICAL_TYPES:
            return Priority.P0_CRITICAL

        # Unknown person at night - P0
        if "person" in types_lower and time_of_day == "night":
            return Priority.P0_CRITICAL

        # Unknown vehicle - P1
        if types_lower & VEHICLE_TYPES:
            return Priority.P1_HIGH

        # Default to normal priority
        return Priority.P2_NORMAL

    async def register_candidate(self, candidate: CoalesceCandidate) -> None:
        """Register a batch as a coalesce candidate.

        Stores the candidate in Redis sorted set (by timestamp) for later
        lookup when finding compatible batches.

        Args:
            candidate: The batch candidate to register
        """
        if self._redis is None:
            logger.warning("No Redis client, skipping candidate registration")
            return

        # Store candidate data
        candidate_key = f"{self.CANDIDATE_DATA_PREFIX}:{candidate.batch_id}"
        candidates_key = f"{self.CANDIDATES_KEY_PREFIX}:{candidate.camera_id}"

        timestamp = candidate.created_at.timestamp()

        # Store the serialized candidate
        await self._redis.set(
            candidate_key,
            candidate.to_json(),
            ex=self.CANDIDATE_TTL_SECONDS,
        )

        # Add to sorted set by timestamp
        await self._redis.zadd(
            candidates_key,
            {candidate.batch_id: timestamp},
        )

        # Set TTL on sorted set
        await self._redis.expire(candidates_key, self.CANDIDATE_TTL_SECONDS)

        logger.debug(
            "Registered coalesce candidate",
            extra={
                "batch_id": candidate.batch_id,
                "camera_id": candidate.camera_id,
                "detection_count": len(candidate.detection_ids),
            },
        )

    async def find_compatible_candidates(
        self, candidate: CoalesceCandidate
    ) -> list[CoalesceCandidate]:
        """Find compatible candidates for coalescing.

        Searches Redis for candidates from the same camera within the
        coalesce time window, then filters by compatibility.

        Args:
            candidate: The candidate to find matches for

        Returns:
            List of compatible candidates (may be empty)
        """
        if self._redis is None:
            return []

        candidates_key = f"{self.CANDIDATES_KEY_PREFIX}:{candidate.camera_id}"

        # Get candidates within time window
        min_time = candidate.created_at.timestamp() - self.coalesce_window_seconds
        max_time = candidate.created_at.timestamp() + self.coalesce_window_seconds

        # Get batch IDs from sorted set
        batch_ids = await self._redis.zrangebyscore(
            candidates_key,
            min=min_time,
            max=max_time,
        )

        if not batch_ids:
            return []

        compatible: list[CoalesceCandidate] = []

        for raw_batch_id in batch_ids:
            # Decode if bytes
            if isinstance(raw_batch_id, bytes):
                batch_id_str = raw_batch_id.decode("utf-8")
            else:
                batch_id_str = raw_batch_id

            # Skip self
            if batch_id_str == candidate.batch_id:
                continue

            # Get candidate data
            candidate_key = f"{self.CANDIDATE_DATA_PREFIX}:{batch_id_str}"
            data = await self._redis.get(candidate_key)

            if data is None:
                continue

            try:
                other = CoalesceCandidate.from_json(data)
                if self.is_compatible(candidate, other):
                    compatible.append(other)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(
                    "Failed to parse candidate data",
                    extra={"batch_id": batch_id_str, "error": str(e)},
                )

        return compatible

    async def remove_candidates(self, batch_ids: list[str]) -> None:
        """Remove merged candidates from tracking.

        Cleans up Redis after batches have been merged.

        Args:
            batch_ids: List of batch IDs to remove
        """
        if self._redis is None:
            return

        for batch_id in batch_ids:
            # Delete candidate data
            candidate_key = f"{self.CANDIDATE_DATA_PREFIX}:{batch_id}"
            await self._redis.delete(candidate_key)

            # Note: We can't easily remove from sorted sets without knowing camera_id
            # The TTL will handle cleanup, but for immediate removal we'd need
            # to track camera_id -> batch_id mapping

        # For sorted sets, we use zrem with the batch_ids
        # This requires knowing which camera's set to modify
        await self._redis.zrem("coalesce:candidates:*", *batch_ids)

        logger.debug(
            "Removed coalesce candidates",
            extra={"batch_count": len(batch_ids)},
        )

    async def merge_batches(self, batches: list[CoalesceCandidate]) -> CoalesceResult:
        """Merge multiple compatible batches into one.

        Combines detection IDs from all batches in order (temporal ordering).

        Args:
            batches: List of candidates to merge

        Returns:
            CoalesceResult with merged batch information
        """
        self._metrics.merges_attempted += 1

        # Handle empty list
        if not batches:
            return CoalesceResult(
                merged_batch_id="",
                source_batch_ids=[],
                combined_detection_ids=[],
                detection_count_before=0,
                detection_count_after=0,
                merge_count=0,
            )

        # Handle single batch (no actual merge)
        if len(batches) == 1:
            return CoalesceResult(
                merged_batch_id=batches[0].batch_id,
                source_batch_ids=[batches[0].batch_id],
                combined_detection_ids=batches[0].detection_ids.copy(),
                detection_count_before=1,
                detection_count_after=1,
                merge_count=1,
            )

        # Sort batches by creation time to preserve temporal order
        sorted_batches = sorted(batches, key=lambda b: b.created_at)

        # Combine detection IDs in order
        combined_ids: list[int] = []
        source_ids: list[str] = []

        for batch in sorted_batches:
            combined_ids.extend(batch.detection_ids)
            source_ids.append(batch.batch_id)

        # Generate new merged batch ID
        merged_id = f"merged-{uuid.uuid4().hex[:8]}"

        self._metrics.merges_successful += 1
        self._metrics.total_batches_processed += len(batches)
        self._metrics.total_batches_merged += len(batches)

        result = CoalesceResult(
            merged_batch_id=merged_id,
            source_batch_ids=source_ids,
            combined_detection_ids=combined_ids,
            detection_count_before=len(batches),
            detection_count_after=1,
            merge_count=len(batches),
        )

        self._metrics.total_inference_reduction += result.inference_reduction_pct

        logger.info(
            "Merged batches",
            extra={
                "merged_batch_id": merged_id,
                "source_count": len(batches),
                "detection_count": len(combined_ids),
                "inference_reduction_pct": result.inference_reduction_pct,
            },
        )

        return result

    def get_metrics(self) -> dict[str, Any]:
        """Get coalescing metrics for monitoring.

        Returns:
            Dictionary with merge statistics
        """
        return {
            "merges_attempted": self._metrics.merges_attempted,
            "merges_successful": self._metrics.merges_successful,
            "total_batches_processed": self._metrics.total_batches_processed,
            "total_batches_merged": self._metrics.total_batches_merged,
            "total_inference_reduction": self._metrics.total_inference_reduction,
            "avg_inference_reduction_pct": (
                self._metrics.total_inference_reduction / self._metrics.merges_successful
                if self._metrics.merges_successful > 0
                else 0.0
            ),
        }

    def reset_metrics(self) -> None:
        """Reset metrics counters (for testing)."""
        self._metrics = CoalescerMetrics()


# Singleton instance
_batch_coalescer: BatchCoalescer | None = None


def get_batch_coalescer() -> BatchCoalescer:
    """Get or create the global BatchCoalescer instance.

    Returns:
        Singleton BatchCoalescer instance
    """
    global _batch_coalescer  # noqa: PLW0603
    if _batch_coalescer is None:
        _batch_coalescer = BatchCoalescer()
    return _batch_coalescer


def reset_batch_coalescer() -> None:
    """Reset the global BatchCoalescer instance (for testing)."""
    global _batch_coalescer  # noqa: PLW0603
    _batch_coalescer = None
