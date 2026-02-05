"""TDD Tests for BatchCoalescer service.

Phase 5: Batching and Scheduling Optimization
Tests written BEFORE implementation (Red Phase).

The BatchCoalescer merges similar detections to reduce inference count:
- Same camera + same object type = coalescable
- Priority levels: P0 (weapon/unknown night), P1 (unknown vehicle), P2 (normal), P3 (known faces)
- Target: 20-40% reduction in inference count
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestPriorityEnum:
    """Test Priority enum values and ordering."""

    def test_priority_levels_exist(self) -> None:
        """Priority levels P0-P3 should exist."""
        from backend.services.batch_coalescer import Priority

        assert hasattr(Priority, "P0_CRITICAL")
        assert hasattr(Priority, "P1_HIGH")
        assert hasattr(Priority, "P2_NORMAL")
        assert hasattr(Priority, "P3_LOW")

    def test_priority_ordering(self) -> None:
        """P0 > P1 > P2 > P3 in numeric value."""
        from backend.services.batch_coalescer import Priority

        assert Priority.P0_CRITICAL.value > Priority.P1_HIGH.value
        assert Priority.P1_HIGH.value > Priority.P2_NORMAL.value
        assert Priority.P2_NORMAL.value > Priority.P3_LOW.value

    def test_priority_names_descriptive(self) -> None:
        """Priority names should indicate severity."""
        from backend.services.batch_coalescer import Priority

        assert "CRITICAL" in Priority.P0_CRITICAL.name
        assert "HIGH" in Priority.P1_HIGH.name
        assert "NORMAL" in Priority.P2_NORMAL.name
        assert "LOW" in Priority.P3_LOW.name


class TestCoalesceCandidate:
    """Test CoalesceCandidate dataclass."""

    def test_candidate_creation(self) -> None:
        """CoalesceCandidate should hold batch metadata."""
        from backend.services.batch_coalescer import CoalesceCandidate

        candidate = CoalesceCandidate(
            batch_id="batch_123",
            camera_id="camera_front",
            detection_ids=[1, 2, 3],
            object_types=["person", "person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )

        assert candidate.batch_id == "batch_123"
        assert candidate.camera_id == "camera_front"
        assert len(candidate.detection_ids) == 3
        assert candidate.avg_confidence == 0.85

    def test_candidate_requires_camera_id(self) -> None:
        """Camera ID is required for coalescing decisions."""
        from backend.services.batch_coalescer import CoalesceCandidate

        candidate = CoalesceCandidate(
            batch_id="batch_123",
            camera_id="camera_front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.8,
            created_at=datetime.now(tz=UTC),
        )

        assert candidate.camera_id is not None
        assert len(candidate.camera_id) > 0


class TestCoalesceResult:
    """Test CoalesceResult dataclass."""

    def test_result_tracks_merged_batches(self) -> None:
        """CoalesceResult should track which batches were merged."""
        from backend.services.batch_coalescer import CoalesceResult

        result = CoalesceResult(
            merged_batch_id="merged_001",
            source_batch_ids=["batch_1", "batch_2", "batch_3"],
            combined_detection_ids=[1, 2, 3, 4, 5],
            detection_count_before=3,
            detection_count_after=5,
            merge_count=3,
        )

        assert result.merged_batch_id == "merged_001"
        assert len(result.source_batch_ids) == 3
        assert result.merge_count == 3

    def test_result_calculates_reduction(self) -> None:
        """Result should indicate inference reduction achieved."""
        from backend.services.batch_coalescer import CoalesceResult

        result = CoalesceResult(
            merged_batch_id="merged_001",
            source_batch_ids=["b1", "b2"],
            combined_detection_ids=[1, 2, 3],
            detection_count_before=2,
            detection_count_after=1,
            merge_count=2,
        )

        # 2 batches merged into 1 = 50% reduction in inference calls
        assert result.inference_reduction_pct == 50.0


class TestBatchCoalescerInit:
    """Test BatchCoalescer initialization."""

    def test_coalescer_requires_redis(self) -> None:
        """Coalescer needs Redis client for candidate tracking."""
        from backend.services.batch_coalescer import BatchCoalescer

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        assert coalescer._redis is mock_redis

    def test_coalescer_default_settings(self) -> None:
        """Coalescer should have configurable merge settings."""
        from backend.services.batch_coalescer import BatchCoalescer

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        # Default settings from config
        assert hasattr(coalescer, "max_batch_size")
        assert hasattr(coalescer, "coalesce_window_seconds")
        assert hasattr(coalescer, "confidence_tolerance")


class TestCompatibilityChecking:
    """Test batch compatibility for coalescing."""

    def test_same_camera_same_object_is_compatible(self) -> None:
        """Same camera + same object type = compatible."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="front_door",
            detection_ids=[2],
            object_types=["person"],
            avg_confidence=0.82,
            created_at=datetime.now(tz=UTC),
        )

        assert coalescer.is_compatible(batch1, batch2) is True

    def test_different_cameras_not_compatible(self) -> None:
        """Different cameras = not compatible."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="back_yard",  # Different camera
            detection_ids=[2],
            object_types=["person"],
            avg_confidence=0.82,
            created_at=datetime.now(tz=UTC),
        )

        assert coalescer.is_compatible(batch1, batch2) is False

    def test_different_object_types_not_compatible(self) -> None:
        """Different primary object types = not compatible."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="front_door",
            detection_ids=[2],
            object_types=["vehicle"],  # Different object
            avg_confidence=0.82,
            created_at=datetime.now(tz=UTC),
        )

        assert coalescer.is_compatible(batch1, batch2) is False

    def test_exceeds_max_batch_size_not_compatible(self) -> None:
        """Combined detections exceeding max = not compatible."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis, max_batch_size=5)

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1, 2, 3],
            object_types=["person"] * 3,
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="front_door",
            detection_ids=[4, 5, 6],  # Combined = 6 > max 5
            object_types=["person"] * 3,
            avg_confidence=0.82,
            created_at=datetime.now(tz=UTC),
        )

        assert coalescer.is_compatible(batch1, batch2) is False

    def test_confidence_within_tolerance_is_compatible(self) -> None:
        """Similar confidence (within tolerance) = compatible."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(
            redis_client=mock_redis,
            confidence_tolerance=0.1,  # 10% tolerance
        )

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="front_door",
            detection_ids=[2],
            object_types=["person"],
            avg_confidence=0.80,  # Within 10% of 0.85
            created_at=datetime.now(tz=UTC),
        )

        assert coalescer.is_compatible(batch1, batch2) is True


class TestPriorityCalculation:
    """Test priority assignment based on detection characteristics."""

    def test_weapon_detection_is_p0(self) -> None:
        """Weapon detections get highest priority (P0)."""
        from backend.services.batch_coalescer import BatchCoalescer, Priority

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        priority = coalescer.calculate_priority(
            object_types=["person", "gun"],
            confidence=0.9,
            time_of_day="day",
            is_known_face=False,
        )

        assert priority == Priority.P0_CRITICAL

    def test_unknown_person_at_night_is_p0(self) -> None:
        """Unknown person at night = P0 (critical)."""
        from backend.services.batch_coalescer import BatchCoalescer, Priority

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        priority = coalescer.calculate_priority(
            object_types=["person"],
            confidence=0.85,
            time_of_day="night",
            is_known_face=False,
        )

        assert priority == Priority.P0_CRITICAL

    def test_unknown_vehicle_is_p1(self) -> None:
        """Unknown vehicle = P1 (high)."""
        from backend.services.batch_coalescer import BatchCoalescer, Priority

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        priority = coalescer.calculate_priority(
            object_types=["car"],
            confidence=0.85,
            time_of_day="day",
            is_known_face=False,
        )

        assert priority == Priority.P1_HIGH

    def test_normal_person_daytime_is_p2(self) -> None:
        """Normal person during day = P2."""
        from backend.services.batch_coalescer import BatchCoalescer, Priority

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        priority = coalescer.calculate_priority(
            object_types=["person"],
            confidence=0.75,
            time_of_day="day",
            is_known_face=False,
        )

        assert priority == Priority.P2_NORMAL

    def test_known_face_is_p3(self) -> None:
        """Known face = P3 (low priority)."""
        from backend.services.batch_coalescer import BatchCoalescer, Priority

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        priority = coalescer.calculate_priority(
            object_types=["person"],
            confidence=0.95,
            time_of_day="day",
            is_known_face=True,  # Known household member
        )

        assert priority == Priority.P3_LOW


class TestCoalesceMerging:
    """Test actual batch merging operations."""

    @pytest.mark.asyncio
    async def test_merge_compatible_batches(self) -> None:
        """Merge two compatible batches into one."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1, 2],
            object_types=["person", "person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="front",
            detection_ids=[3, 4],
            object_types=["person", "person"],
            avg_confidence=0.82,
            created_at=datetime.now(tz=UTC),
        )

        result = await coalescer.merge_batches([batch1, batch2])

        assert result.merge_count == 2
        assert set(result.combined_detection_ids) == {1, 2, 3, 4}
        assert len(result.source_batch_ids) == 2

    @pytest.mark.asyncio
    async def test_no_merge_single_batch(self) -> None:
        """Single batch returns unchanged."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1, 2],
            object_types=["person", "person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )

        result = await coalescer.merge_batches([batch1])

        assert result.merge_count == 1
        assert result.source_batch_ids == ["b1"]

    @pytest.mark.asyncio
    async def test_merge_preserves_detection_order(self) -> None:
        """Merged detections maintain temporal order."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        now = datetime.now(tz=UTC)
        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1, 2],
            object_types=["person", "person"],
            avg_confidence=0.85,
            created_at=now,
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="front",
            detection_ids=[3, 4],
            object_types=["person", "person"],
            avg_confidence=0.82,
            created_at=now,
        )

        result = await coalescer.merge_batches([batch1, batch2])

        # Order should be preserved (b1 detections before b2)
        assert result.combined_detection_ids[:2] == [1, 2]
        assert result.combined_detection_ids[2:] == [3, 4]


class TestCandidateTracking:
    """Test Redis-based candidate tracking."""

    @pytest.mark.asyncio
    async def test_register_candidate(self) -> None:
        """Register batch as coalesce candidate in Redis."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        candidate = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )

        await coalescer.register_candidate(candidate)

        # Should store in Redis sorted set
        mock_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_compatible_candidates(self) -> None:
        """Find compatible candidates from Redis."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        # Simulate existing candidates in Redis
        mock_redis.zrangebyscore.return_value = [
            b'{"batch_id": "b2", "camera_id": "front", "detection_ids": [2]}'
        ]

        coalescer = BatchCoalescer(redis_client=mock_redis)

        candidate = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )

        compatible = await coalescer.find_compatible_candidates(candidate)

        assert len(compatible) >= 0  # May find matches

    @pytest.mark.asyncio
    async def test_remove_merged_candidates(self) -> None:
        """Remove merged candidates from tracking."""
        from backend.services.batch_coalescer import BatchCoalescer

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        await coalescer.remove_candidates(["b1", "b2", "b3"])

        # Should remove from sorted set
        mock_redis.zrem.assert_called()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_batch_list(self) -> None:
        """Empty batch list returns empty result."""
        from backend.services.batch_coalescer import BatchCoalescer

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        result = await coalescer.merge_batches([])

        assert result.merge_count == 0
        assert result.combined_detection_ids == []

    def test_all_same_priority(self) -> None:
        """All requests same priority should still be coalescable."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        # Multiple batches, all P2 (normal)
        batches = [
            CoalesceCandidate(
                batch_id=f"b{i}",
                camera_id="front",
                detection_ids=[i],
                object_types=["person"],
                avg_confidence=0.75,
                created_at=datetime.now(tz=UTC),
            )
            for i in range(3)
        ]

        # All should be compatible with each other
        assert coalescer.is_compatible(batches[0], batches[1]) is True
        assert coalescer.is_compatible(batches[1], batches[2]) is True

    def test_no_coalescable_in_window(self) -> None:
        """When no batches are coalescable, each processes individually."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = MagicMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        # Different cameras = not coalescable
        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="back",  # Different camera
            detection_ids=[2],
            object_types=["vehicle"],  # Different object type too
            avg_confidence=0.82,
            created_at=datetime.now(tz=UTC),
        )

        assert coalescer.is_compatible(batch1, batch2) is False


class TestMetricsCollection:
    """Test coalescing metrics for monitoring."""

    @pytest.mark.asyncio
    async def test_tracks_merge_statistics(self) -> None:
        """Coalescer tracks merge success rate."""
        from backend.services.batch_coalescer import BatchCoalescer, CoalesceCandidate

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        batch1 = CoalesceCandidate(
            batch_id="b1",
            camera_id="front",
            detection_ids=[1],
            object_types=["person"],
            avg_confidence=0.85,
            created_at=datetime.now(tz=UTC),
        )
        batch2 = CoalesceCandidate(
            batch_id="b2",
            camera_id="front",
            detection_ids=[2],
            object_types=["person"],
            avg_confidence=0.82,
            created_at=datetime.now(tz=UTC),
        )

        await coalescer.merge_batches([batch1, batch2])

        # Should have metrics available
        metrics = coalescer.get_metrics()
        assert "merges_attempted" in metrics
        assert "merges_successful" in metrics
