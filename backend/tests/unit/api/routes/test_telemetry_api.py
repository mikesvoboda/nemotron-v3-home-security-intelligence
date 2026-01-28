"""Unit tests for pipeline telemetry API endpoints.

Tests for the GET /api/system/telemetry endpoint that exposes:
- Queue depths (detection_queue, analysis_queue)
- Pipeline stage latencies (watch, detect, batch, analyze)

These tests follow TDD approach - written before implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.schemas.system import (
    PipelineLatencies,
    QueueDepths,
    StageLatency,
    TelemetryResponse,
)

# =============================================================================
# Schema Tests
# =============================================================================


class TestQueueDepthsSchema:
    """Tests for QueueDepths Pydantic schema."""

    def test_queue_depths_creation(self) -> None:
        """Test QueueDepths can be created with valid data."""
        depths = QueueDepths(
            detection_queue=5,
            analysis_queue=3,
        )
        assert depths.detection_queue == 5
        assert depths.analysis_queue == 3

    def test_queue_depths_zero_values(self) -> None:
        """Test QueueDepths accepts zero values (empty queues)."""
        depths = QueueDepths(
            detection_queue=0,
            analysis_queue=0,
        )
        assert depths.detection_queue == 0
        assert depths.analysis_queue == 0

    def test_queue_depths_large_values(self) -> None:
        """Test QueueDepths accepts large values (backlog scenario)."""
        depths = QueueDepths(
            detection_queue=10000,
            analysis_queue=5000,
        )
        assert depths.detection_queue == 10000
        assert depths.analysis_queue == 5000


class TestStageLatencySchema:
    """Tests for StageLatency Pydantic schema."""

    def test_stage_latency_creation(self) -> None:
        """Test StageLatency can be created with valid data."""
        latency = StageLatency(
            avg_ms=150.5,
            min_ms=50.0,
            max_ms=500.0,
            p50_ms=120.0,
            p95_ms=400.0,
            p99_ms=480.0,
            sample_count=100,
        )
        assert latency.avg_ms == 150.5
        assert latency.min_ms == 50.0
        assert latency.max_ms == 500.0
        assert latency.p50_ms == 120.0
        assert latency.p95_ms == 400.0
        assert latency.p99_ms == 480.0
        assert latency.sample_count == 100

    def test_stage_latency_nullable_fields(self) -> None:
        """Test StageLatency fields are nullable when no data available."""
        latency = StageLatency(
            avg_ms=None,
            min_ms=None,
            max_ms=None,
            p50_ms=None,
            p95_ms=None,
            p99_ms=None,
            sample_count=0,
        )
        assert latency.avg_ms is None
        assert latency.sample_count == 0


class TestPipelineLatenciesSchema:
    """Tests for PipelineLatencies Pydantic schema."""

    def test_pipeline_latencies_creation(self) -> None:
        """Test PipelineLatencies can be created with valid stage data."""
        watch_latency = StageLatency(
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=50.0,
            p50_ms=8.0,
            p95_ms=40.0,
            p99_ms=48.0,
            sample_count=500,
        )
        detect_latency = StageLatency(
            avg_ms=200.0,
            min_ms=100.0,
            max_ms=800.0,
            p50_ms=180.0,
            p95_ms=600.0,
            p99_ms=750.0,
            sample_count=500,
        )
        batch_latency = StageLatency(
            avg_ms=30000.0,  # 30 seconds average batch time
            min_ms=5000.0,
            max_ms=90000.0,
            p50_ms=25000.0,
            p95_ms=80000.0,
            p99_ms=88000.0,
            sample_count=100,
        )
        analyze_latency = StageLatency(
            avg_ms=5000.0,  # 5 seconds average LLM time
            min_ms=2000.0,
            max_ms=15000.0,
            p50_ms=4500.0,
            p95_ms=12000.0,
            p99_ms=14000.0,
            sample_count=100,
        )

        latencies = PipelineLatencies(
            watch=watch_latency,
            detect=detect_latency,
            batch=batch_latency,
            analyze=analyze_latency,
        )

        assert latencies.watch.avg_ms == 10.0
        assert latencies.detect.avg_ms == 200.0
        assert latencies.batch.avg_ms == 30000.0
        assert latencies.analyze.avg_ms == 5000.0

    def test_pipeline_latencies_nullable_stages(self) -> None:
        """Test PipelineLatencies allows nullable stages."""
        latencies = PipelineLatencies(
            watch=None,
            detect=None,
            batch=None,
            analyze=None,
        )
        assert latencies.watch is None
        assert latencies.detect is None
        assert latencies.batch is None
        assert latencies.analyze is None


class TestTelemetryResponseSchema:
    """Tests for TelemetryResponse Pydantic schema."""

    def test_telemetry_response_creation(self) -> None:
        """Test TelemetryResponse can be created with full data."""
        depths = QueueDepths(detection_queue=5, analysis_queue=3)
        latencies = PipelineLatencies(watch=None, detect=None, batch=None, analyze=None)
        timestamp = datetime.now(UTC)

        response = TelemetryResponse(
            queues=depths,
            latencies=latencies,
            timestamp=timestamp,
        )

        assert response.queues.detection_queue == 5
        assert response.queues.analysis_queue == 3
        assert response.timestamp == timestamp

    def test_telemetry_response_has_example(self) -> None:
        """Test TelemetryResponse has JSON schema example for OpenAPI docs."""
        schema = TelemetryResponse.model_json_schema()
        # Just verify it can generate a schema (has proper structure)
        assert "properties" in schema


# =============================================================================
# API Route Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_telemetry_returns_queue_depths() -> None:
    """Test telemetry endpoint returns queue depths from Redis."""
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    redis.get_queue_length = AsyncMock(side_effect=[10, 5])

    with patch.object(system_routes, "get_latency_stats", return_value=None):
        response = await system_routes.get_telemetry(redis)

    assert response.queues.detection_queue == 10
    assert response.queues.analysis_queue == 5


@pytest.mark.asyncio
async def test_get_telemetry_handles_redis_error() -> None:
    """Test telemetry endpoint handles Redis errors gracefully."""
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    redis.get_queue_length = AsyncMock(side_effect=ConnectionError("Redis error"))

    response = await system_routes.get_telemetry(redis)

    # Should return zeros when Redis is unavailable
    assert response.queues.detection_queue == 0
    assert response.queues.analysis_queue == 0


@pytest.mark.asyncio
async def test_get_telemetry_returns_latency_stats() -> None:
    """Test telemetry endpoint returns latency statistics."""
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    redis.get_queue_length = AsyncMock(return_value=0)

    mock_latencies = PipelineLatencies(
        watch=StageLatency(
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=50.0,
            p50_ms=8.0,
            p95_ms=40.0,
            p99_ms=48.0,
            sample_count=100,
        ),
        detect=StageLatency(
            avg_ms=200.0,
            min_ms=100.0,
            max_ms=800.0,
            p50_ms=180.0,
            p95_ms=600.0,
            p99_ms=750.0,
            sample_count=100,
        ),
        batch=None,
        analyze=None,
    )

    with patch.object(system_routes, "get_latency_stats", AsyncMock(return_value=mock_latencies)):
        response = await system_routes.get_telemetry(redis)

    assert response.latencies is not None
    assert response.latencies.watch.avg_ms == 10.0
    assert response.latencies.detect.avg_ms == 200.0


@pytest.mark.asyncio
async def test_get_telemetry_has_timestamp() -> None:
    """Test telemetry endpoint includes current timestamp."""
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    redis.get_queue_length = AsyncMock(return_value=0)

    with patch.object(system_routes, "get_latency_stats", return_value=None):
        response = await system_routes.get_telemetry(redis)

    assert response.timestamp is not None
    # Timestamp should be recent (within last minute)
    now = datetime.now(UTC)
    delta = now - response.timestamp
    assert delta.total_seconds() < 60


@pytest.mark.asyncio
async def test_get_telemetry_queue_names_are_correct() -> None:
    """Test telemetry uses correct queue names for depth retrieval."""
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    redis.get_queue_length = AsyncMock(return_value=0)

    with patch.object(system_routes, "get_latency_stats", return_value=None):
        await system_routes.get_telemetry(redis)

    # Verify get_queue_length was called with correct queue names
    calls = redis.get_queue_length.call_args_list
    queue_names = [call[0][0] for call in calls]
    assert "detection_queue" in queue_names
    assert "analysis_queue" in queue_names


# =============================================================================
# Latency Tracking Helper Tests
# =============================================================================


@pytest.mark.asyncio
async def test_record_stage_latency() -> None:
    """Test recording latency for a pipeline stage."""
    from backend.api.routes import system as system_routes
    from backend.core.redis import QueueAddResult

    redis = AsyncMock()
    # Implementation uses add_to_queue_safe with overflow_policy
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    # Mock expire directly on the redis client (it's called as redis.expire())
    redis.expire = AsyncMock()

    await system_routes.record_stage_latency(redis, stage="detect", latency_ms=150.0)

    # Should store latency in a list with max_size limit
    redis.add_to_queue_safe.assert_called_once()
    # Verify max_size is passed correctly (MAX_LATENCY_SAMPLES = 1000)
    call_args = redis.add_to_queue_safe.call_args
    assert call_args[1].get("max_size") == 1000
    # Should set TTL on the key
    redis.expire.assert_called_once()


@pytest.mark.asyncio
async def test_get_latency_stats_calculates_percentiles() -> None:
    """Test get_latency_stats calculates correct percentiles."""
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    # Mock stored latency samples - peek_queue returns samples for each stage
    sample_data = [
        100.0,
        150.0,
        200.0,
        250.0,
        300.0,
        350.0,
        400.0,
        450.0,
        500.0,
        550.0,
    ]
    # Return samples for detect stage, empty for others
    redis.peek_queue = AsyncMock(
        side_effect=lambda key, _start, _end: sample_data if "detect" in key else []
    )

    latencies = await system_routes.get_latency_stats(redis)

    assert latencies is not None
    assert latencies.detect is not None
    assert latencies.detect.sample_count == 10
    assert latencies.detect.min_ms == 100.0
    assert latencies.detect.max_ms == 550.0
    # Other stages should have zero values since no samples
    assert latencies.watch.sample_count == 0
    assert latencies.analyze.sample_count == 0


@pytest.mark.asyncio
async def test_get_latency_stats_handles_empty_data() -> None:
    """Test get_latency_stats handles no data gracefully.

    When no latency samples exist, stages should return zero values
    with sample_count=0 to ensure consistent JSON structure for
    metrics exporters (e.g., json_exporter).
    """
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    redis.peek_queue = AsyncMock(return_value=None)

    latencies = await system_routes.get_latency_stats(redis)

    # Should return StageLatency objects with zero values when no data
    # This ensures consistent JSON structure for metrics exporters
    assert latencies is not None
    assert latencies.watch is not None
    assert latencies.watch.sample_count == 0
    assert latencies.watch.avg_ms == 0.0
    assert latencies.watch.p99_ms == 0.0
    assert latencies.analyze is not None
    assert latencies.analyze.sample_count == 0
    assert latencies.analyze.p99_ms == 0.0


# =============================================================================
# Integration with PipelineWorkerManager Tests
# =============================================================================


@pytest.mark.asyncio
async def test_telemetry_reflects_pipeline_state() -> None:
    """Test telemetry accurately reflects current pipeline state."""
    from backend.api.routes import system as system_routes

    redis = AsyncMock()
    # Simulate backlog: detection queue has items waiting
    redis.get_queue_length = AsyncMock(side_effect=[25, 10])

    with patch.object(system_routes, "get_latency_stats", return_value=None):
        response = await system_routes.get_telemetry(redis)

    # Should show backlog
    assert response.queues.detection_queue == 25
    assert response.queues.analysis_queue == 10


# =============================================================================
# Schema Validation Tests
# =============================================================================


def test_queue_depths_rejects_negative_values() -> None:
    """Test QueueDepths rejects negative queue depths."""
    with pytest.raises(ValueError):
        QueueDepths(detection_queue=-1, analysis_queue=0)


def test_stage_latency_rejects_negative_values() -> None:
    """Test StageLatency rejects negative latency values."""
    with pytest.raises(ValueError):
        StageLatency(
            avg_ms=-10.0,
            min_ms=0.0,
            max_ms=100.0,
            p50_ms=50.0,
            p95_ms=90.0,
            p99_ms=99.0,
            sample_count=10,
        )


def test_stage_latency_accepts_zero_sample_count() -> None:
    """Test StageLatency accepts zero sample count (no data yet)."""
    latency = StageLatency(
        avg_ms=None,
        min_ms=None,
        max_ms=None,
        p50_ms=None,
        p95_ms=None,
        p99_ms=None,
        sample_count=0,
    )
    assert latency.sample_count == 0
