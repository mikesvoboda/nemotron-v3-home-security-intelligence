"""Unit tests for multi-worker pipeline support (NEM-5375)."""

from unittest.mock import AsyncMock

import pytest

from backend.core.redis import RedisClient
from backend.services.pipeline_workers import PipelineWorkerManager


@pytest.mark.asyncio
async def test_manager_creates_multiple_detection_workers():
    """Test that PipelineWorkerManager creates multiple detection workers based on config."""
    mock_redis = AsyncMock(spec=RedisClient)

    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        detection_worker_count=3,
        analysis_worker_count=2,
        enable_detection_worker=True,
        enable_analysis_worker=True,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    # Verify correct number of workers created
    assert len(manager._detection_workers) == 3
    assert len(manager._analysis_workers) == 2

    # Verify worker names are unique
    for i, worker in enumerate(manager._detection_workers):
        assert worker._worker_name == f"detection-{i}"

    for i, worker in enumerate(manager._analysis_workers):
        assert worker._worker_name == f"analysis-{i}"


@pytest.mark.asyncio
async def test_manager_get_status_with_multiple_workers():
    """Test that get_status returns correct information for multiple workers."""
    mock_redis = AsyncMock(spec=RedisClient)

    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        detection_worker_count=2,
        analysis_worker_count=3,
        enable_detection_worker=True,
        enable_analysis_worker=True,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    # Get status
    status = manager.get_status()

    # Verify status structure
    assert "workers" in status
    assert "detection" in status["workers"]
    assert "analysis" in status["workers"]

    # Verify detection worker info
    detection_info = status["workers"]["detection"]
    assert detection_info["count"] == 2
    assert len(detection_info["workers"]) == 2

    # Verify analysis worker info
    analysis_info = status["workers"]["analysis"]
    assert analysis_info["count"] == 3
    assert len(analysis_info["workers"]) == 3

    # Verify each worker has stats
    for worker_stats in detection_info["workers"]:
        assert "items_processed" in worker_stats
        assert "errors" in worker_stats
        assert "state" in worker_stats

    for worker_stats in analysis_info["workers"]:
        assert "items_processed" in worker_stats
        assert "errors" in worker_stats
        assert "state" in worker_stats


@pytest.mark.asyncio
async def test_worker_count_from_settings():
    """Test that worker counts are read from settings when not overridden."""
    from backend.core.config import get_settings

    settings = get_settings()
    mock_redis = AsyncMock(spec=RedisClient)

    # Create manager without explicit worker counts (should use settings)
    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        enable_detection_worker=True,
        enable_analysis_worker=True,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    # Verify worker counts match settings
    assert len(manager._detection_workers) == settings.detection_worker_count
    assert len(manager._analysis_workers) == settings.analysis_worker_count
