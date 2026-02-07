"""Integration tests for BatchCoalescer metrics and coalescing validation (NEM-5530).

Validates that:
- Multiple similar batches from the same camera within the coalescing window get merged
- All detections from merged batches are present in the final result
- Prometheus metrics are correctly incremented during coalescing operations

Note: We import batch_coalescer from its module path directly (not via
backend.services) to avoid triggering the services __init__ chain which
pulls in nemotron_analyzer and its full dependency tree.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from prometheus_client import REGISTRY

# Import batch_coalescer directly to avoid backend.services.__init__ chain
# which pulls in nemotron_analyzer and its full dependency tree
_mod = importlib.import_module("backend.services.batch_coalescer")
BatchCoalescer = _mod.BatchCoalescer
CoalesceCandidate = _mod.CoalesceCandidate
CoalesceResult = _mod.CoalesceResult
reset_batch_coalescer = _mod.reset_batch_coalescer


def _get_counter_value(metric_name: str) -> float:
    """Get the current value of a Prometheus counter.

    Args:
        metric_name: Full Prometheus metric name (e.g., 'hsi_batch_coalesced_total')

    Returns:
        Current counter value, or 0.0 if not found
    """
    for metric in REGISTRY.collect():
        if metric.name == metric_name:
            for sample in metric.samples:
                if sample.name == metric_name + "_total" or sample.name == metric_name:
                    return sample.value
    return 0.0


def _get_gauge_value(metric_name: str) -> float:
    """Get the current value of a Prometheus gauge.

    Args:
        metric_name: Full Prometheus metric name

    Returns:
        Current gauge value, or 0.0 if not found
    """
    for metric in REGISTRY.collect():
        if metric.name == metric_name:
            for sample in metric.samples:
                if sample.name == metric_name:
                    return sample.value
    return 0.0


def _make_candidate(
    batch_id: str,
    camera_id: str = "front_door",
    detection_ids: list[int] | None = None,
    object_types: list[str] | None = None,
    avg_confidence: float = 0.85,
    created_at: datetime | None = None,
) -> CoalesceCandidate:
    """Create a CoalesceCandidate with sensible defaults for testing.

    Args:
        batch_id: Unique batch identifier
        camera_id: Camera that produced these detections
        detection_ids: List of detection IDs (defaults to [1])
        object_types: List of object types (defaults to ["person"])
        avg_confidence: Average detection confidence
        created_at: Creation timestamp (defaults to now)

    Returns:
        A CoalesceCandidate instance
    """
    return CoalesceCandidate(
        batch_id=batch_id,
        camera_id=camera_id,
        detection_ids=detection_ids or [1],
        object_types=object_types or ["person"],
        avg_confidence=avg_confidence,
        created_at=created_at or datetime.now(tz=UTC),
    )


def _build_mock_redis_with_candidates(
    candidates: list[CoalesceCandidate],
) -> AsyncMock:
    """Build a mock Redis client pre-loaded with candidate data.

    This simulates Redis containing registered candidates so that
    find_compatible_candidates can discover them.

    Args:
        candidates: List of candidates to pre-load into mock Redis

    Returns:
        AsyncMock Redis client with get/zrangebyscore/zadd/set/expire/delete/zrem stubs
    """
    mock_redis = AsyncMock()

    # Storage for candidate data keyed by Redis key
    storage: dict[str, str] = {}
    for c in candidates:
        key = f"coalesce:candidate:{c.batch_id}"
        storage[key] = c.to_json()

    async def mock_get(key: str) -> str | None:
        return storage.get(key)

    async def mock_zrangebyscore(key: str, min: float, max: float) -> list[bytes]:
        # Return all candidate batch_ids as bytes (simulating Redis sorted set)
        return [c.batch_id.encode() for c in candidates]

    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.zrangebyscore = AsyncMock(side_effect=mock_zrangebyscore)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.zadd = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.zrem = AsyncMock(return_value=1)

    return mock_redis


class TestCoalescingMergeValidation:
    """Validate that similar batches from the same camera get merged correctly."""

    @pytest.mark.asyncio
    async def test_similar_batches_merge_into_single_llm_call(self) -> None:
        """Multiple similar batches from the same camera within the coalescing
        window should be merged into a single batch for one LLM call."""
        now = datetime.now(tz=UTC)

        # Create 3 similar batches from the same camera, same object type,
        # similar confidence, within the time window
        batch1 = _make_candidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1, 2],
            object_types=["person", "person"],
            avg_confidence=0.85,
            created_at=now,
        )
        batch2 = _make_candidate(
            batch_id="b2",
            camera_id="front_door",
            detection_ids=[3, 4],
            object_types=["person", "person"],
            avg_confidence=0.83,
            created_at=now + timedelta(seconds=1),
        )
        batch3 = _make_candidate(
            batch_id="b3",
            camera_id="front_door",
            detection_ids=[5, 6, 7],
            object_types=["person", "person", "person"],
            avg_confidence=0.87,
            created_at=now + timedelta(seconds=2),
        )

        # Set up mock Redis with batch2 and batch3 as existing candidates
        mock_redis = _build_mock_redis_with_candidates([batch1, batch2, batch3])
        coalescer = BatchCoalescer(
            redis_client=mock_redis,
            coalesce_window_seconds=5.0,
            confidence_tolerance=0.15,
            max_batch_size=20,
        )

        # Register batch1
        await coalescer.register_candidate(batch1)

        # Find compatible candidates for batch1
        compatible = await coalescer.find_compatible_candidates(batch1)

        # batch2 and batch3 should be compatible (same camera, same type, similar confidence)
        assert len(compatible) == 2

        # Merge all batches
        all_batches = [batch1, *compatible]
        result = await coalescer.merge_batches(all_batches)

        # Verify merge result
        assert result.merge_count == 3
        assert len(result.source_batch_ids) == 3
        assert result.detection_count_before == 3
        assert result.detection_count_after == 1

        # Verify ALL detections from all batches are present
        assert set(result.combined_detection_ids) == {1, 2, 3, 4, 5, 6, 7}
        assert len(result.combined_detection_ids) == 7

        # Verify inference reduction: 3 batches -> 1 = 66.67% reduction
        assert result.inference_reduction_pct == pytest.approx(66.67, abs=0.01)

    @pytest.mark.asyncio
    async def test_different_cameras_not_merged(self) -> None:
        """Batches from different cameras should not be merged."""
        now = datetime.now(tz=UTC)

        batch1 = _make_candidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1, 2],
            created_at=now,
        )
        batch2 = _make_candidate(
            batch_id="b2",
            camera_id="back_yard",  # Different camera
            detection_ids=[3, 4],
            created_at=now,
        )

        mock_redis = _build_mock_redis_with_candidates([batch1, batch2])
        coalescer = BatchCoalescer(
            redis_client=mock_redis,
            coalesce_window_seconds=5.0,
        )

        compatible = await coalescer.find_compatible_candidates(batch1)

        # batch2 from different camera should NOT be compatible
        assert len(compatible) == 0

    @pytest.mark.asyncio
    async def test_different_object_types_not_merged(self) -> None:
        """Batches with different primary object types should not be merged."""
        now = datetime.now(tz=UTC)

        batch1 = _make_candidate(
            batch_id="b1",
            camera_id="front_door",
            detection_ids=[1],
            object_types=["person"],
            created_at=now,
        )
        batch2 = _make_candidate(
            batch_id="b2",
            camera_id="front_door",
            detection_ids=[2],
            object_types=["car"],  # Different object type
            created_at=now,
        )

        mock_redis = _build_mock_redis_with_candidates([batch1, batch2])
        coalescer = BatchCoalescer(
            redis_client=mock_redis,
            coalesce_window_seconds=5.0,
        )

        compatible = await coalescer.find_compatible_candidates(batch1)
        assert len(compatible) == 0


class TestCoalescingPrometheusMetrics:
    """Validate that Prometheus metrics are correctly updated during coalescing."""

    @pytest.mark.asyncio
    async def test_merge_increments_coalesced_counter(self) -> None:
        """Merging batches should increment hsi_batch_coalesced_total."""
        now = datetime.now(tz=UTC)

        # Read baseline counter value before merge
        baseline = _get_counter_value("hsi_batch_coalesced")

        batch1 = _make_candidate(batch_id="m1", detection_ids=[1, 2], created_at=now)
        batch2 = _make_candidate(batch_id="m2", detection_ids=[3, 4], created_at=now)

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        await coalescer.merge_batches([batch1, batch2])

        # Counter should have incremented by 2 (2 batches merged)
        current = _get_counter_value("hsi_batch_coalesced")
        assert current - baseline == 2.0

    @pytest.mark.asyncio
    async def test_merge_increments_detections_merged_counter(self) -> None:
        """Merging should increment hsi_batch_coalesce_detections_merged_total
        for additional detections added from non-primary batches."""
        now = datetime.now(tz=UTC)

        baseline = _get_counter_value("hsi_batch_coalesce_detections_merged")

        # batch1 has 2 detections, batch2 has 3 detections
        # Additional detections = 3 (from batch2, since batch1 is the first)
        batch1 = _make_candidate(batch_id="dm1", detection_ids=[1, 2], created_at=now)
        batch2 = _make_candidate(
            batch_id="dm2", detection_ids=[3, 4, 5], created_at=now + timedelta(seconds=1)
        )

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        await coalescer.merge_batches([batch1, batch2])

        current = _get_counter_value("hsi_batch_coalesce_detections_merged")
        assert current - baseline == 3.0

    @pytest.mark.asyncio
    async def test_merge_updates_merge_rate_gauge(self) -> None:
        """Merging should update the hsi_batch_coalesce_merge_rate gauge."""
        now = datetime.now(tz=UTC)

        batch1 = _make_candidate(batch_id="mr1", detection_ids=[1], created_at=now)
        batch2 = _make_candidate(batch_id="mr2", detection_ids=[2], created_at=now)

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        await coalescer.merge_batches([batch1, batch2])

        merge_rate = _get_gauge_value("hsi_batch_coalesce_merge_rate")
        # Merge rate should be > 0 after a successful merge
        assert merge_rate > 0.0

    @pytest.mark.asyncio
    async def test_find_compatible_increments_candidates_counter(self) -> None:
        """Finding compatible candidates should increment
        hsi_batch_coalesce_candidates_total for evaluated candidates."""
        now = datetime.now(tz=UTC)

        baseline = _get_counter_value("hsi_batch_coalesce_candidates")

        batch1 = _make_candidate(batch_id="fc1", detection_ids=[1], created_at=now)
        batch2 = _make_candidate(batch_id="fc2", detection_ids=[2], created_at=now)
        batch3 = _make_candidate(batch_id="fc3", detection_ids=[3], created_at=now)

        mock_redis = _build_mock_redis_with_candidates([batch1, batch2, batch3])
        coalescer = BatchCoalescer(
            redis_client=mock_redis,
            coalesce_window_seconds=5.0,
        )

        await coalescer.find_compatible_candidates(batch1)

        current = _get_counter_value("hsi_batch_coalesce_candidates")
        # Should have evaluated batch2 and batch3 (batch1 is skipped as self)
        assert current - baseline == 2.0

    @pytest.mark.asyncio
    async def test_single_batch_no_coalesce_metrics(self) -> None:
        """A single batch merge should not increment coalesced metrics
        (since no actual merge occurs)."""
        now = datetime.now(tz=UTC)

        baseline_coalesced = _get_counter_value("hsi_batch_coalesced")
        baseline_detections = _get_counter_value("hsi_batch_coalesce_detections_merged")

        batch1 = _make_candidate(batch_id="sb1", detection_ids=[1, 2], created_at=now)

        mock_redis = AsyncMock()
        coalescer = BatchCoalescer(redis_client=mock_redis)

        result = await coalescer.merge_batches([batch1])

        # Single batch = no merge, counters should not change
        assert result.merge_count == 1
        assert _get_counter_value("hsi_batch_coalesced") == baseline_coalesced
        assert _get_counter_value("hsi_batch_coalesce_detections_merged") == baseline_detections


class TestCoalescingEndToEnd:
    """End-to-end test simulating the full coalescing flow."""

    @pytest.mark.asyncio
    async def test_full_coalescing_flow_with_metrics(self) -> None:
        """Simulate the complete flow: register -> find compatible -> merge,
        verifying all metrics and detection preservation."""
        now = datetime.now(tz=UTC)

        # Capture baseline metric values
        baseline_coalesced = _get_counter_value("hsi_batch_coalesced")
        baseline_candidates = _get_counter_value("hsi_batch_coalesce_candidates")

        # Create 4 similar batches from the same camera
        batches = [
            _make_candidate(
                batch_id=f"e2e_{i}",
                camera_id="driveway",
                detection_ids=list(range(i * 3, i * 3 + 3)),
                object_types=["car"] * 3,
                avg_confidence=0.80 + i * 0.02,
                created_at=now + timedelta(seconds=i),
            )
            for i in range(4)
        ]

        mock_redis = _build_mock_redis_with_candidates(batches)
        coalescer = BatchCoalescer(
            redis_client=mock_redis,
            coalesce_window_seconds=10.0,
            confidence_tolerance=0.15,
            max_batch_size=50,
        )

        # Register all candidates
        for batch in batches:
            await coalescer.register_candidate(batch)

        # Find compatible for the first batch
        compatible = await coalescer.find_compatible_candidates(batches[0])
        assert len(compatible) == 3  # Should find the other 3

        # Merge all into one
        all_batches = [batches[0], *compatible]
        result = await coalescer.merge_batches(all_batches)

        # Verify merge result
        assert result.merge_count == 4
        assert result.detection_count_before == 4
        assert result.detection_count_after == 1

        # Verify all 12 detections preserved (4 batches * 3 detections each)
        all_expected_ids = set(range(12))
        assert set(result.combined_detection_ids) == all_expected_ids

        # Verify inference reduction: 4 -> 1 = 75%
        assert result.inference_reduction_pct == 75.0

        # Verify Prometheus metrics updated
        assert _get_counter_value("hsi_batch_coalesced") - baseline_coalesced == 4.0
        assert _get_counter_value("hsi_batch_coalesce_candidates") - baseline_candidates == 3.0

        # Clean up
        await coalescer.remove_candidates(result.source_batch_ids, camera_id="driveway")
        assert mock_redis.zrem.called
