"""Unit tests for the scene baseline service.

Tests for backend/services/scene_baseline.py which provides CLIP-based
scene anomaly detection with baseline embedding management.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from backend.services.scene_baseline import (
    DEFAULT_BASELINE_TTL_SECONDS,
    DEFAULT_DECAY_FACTOR,
    EMBEDDING_DIMENSION,
    MIN_SAMPLES_FOR_RELIABLE_BASELINE,
    BaselineNotFoundError,
    InvalidEmbeddingError,
    SceneBaselineError,
    SceneBaselineService,
    get_scene_baseline_service,
    reset_scene_baseline_service,
)


def create_mock_redis_with_pipeline(
    get_results: list[Any] | None = None,
    set_results: list[Any] | None = None,
    pipeline_results_sequence: list[list[Any]] | None = None,
) -> AsyncMock:
    """Create a mock Redis client with pipeline support.

    This helper creates a mock that handles both the old-style individual
    get/set methods AND the new pipeline-based approach.

    Args:
        get_results: List of results for single pipeline GET operations
        set_results: List of results for single pipeline SETEX operations (default True)
        pipeline_results_sequence: List of lists for multiple pipeline executions
            (e.g., [[get1, get2, get3], [set1, set2, set3]] for get then set)

    Returns:
        AsyncMock configured for pipeline operations
    """
    mock_redis = AsyncMock()

    # Track which pipeline call we're on
    call_count = [0]
    pipelines: list[MagicMock] = []

    def create_pipeline() -> MagicMock:
        mock_pipeline = MagicMock()

        # Configure pipeline.get() to track calls
        def track_get(key: str) -> MagicMock:
            return mock_pipeline

        # Configure pipeline.setex() to track calls
        def track_setex(key: str, ttl: int, value: str) -> MagicMock:
            return mock_pipeline

        mock_pipeline.get = MagicMock(side_effect=track_get)
        mock_pipeline.setex = MagicMock(side_effect=track_setex)

        # Configure execute to return results based on sequence
        if pipeline_results_sequence is not None:
            idx = call_count[0]
            if idx < len(pipeline_results_sequence):
                mock_pipeline.execute = AsyncMock(return_value=pipeline_results_sequence[idx])
            else:
                mock_pipeline.execute = AsyncMock(return_value=[True, True, True])
            call_count[0] += 1
        elif get_results is not None:
            mock_pipeline.execute = AsyncMock(return_value=get_results)
        elif set_results is not None:
            mock_pipeline.execute = AsyncMock(return_value=set_results)
        else:
            mock_pipeline.execute = AsyncMock(return_value=[])

        pipelines.append(mock_pipeline)
        return mock_pipeline

    # Configure _client.pipeline()
    mock_redis._client = MagicMock()
    mock_redis._client.pipeline = MagicMock(side_effect=create_pipeline)

    # Also keep old-style methods for backward compatibility
    mock_redis.exists = AsyncMock(return_value=0)
    mock_redis.delete = AsyncMock(return_value=0)

    return mock_redis


class TestSceneBaselineService:
    """Tests for SceneBaselineService class."""

    def test_initialization_default_params(self) -> None:
        """Test service initialization with default parameters."""
        mock_redis = MagicMock()
        service = SceneBaselineService(mock_redis)

        assert service._redis is mock_redis
        assert service._clip is None
        assert service._decay_factor == DEFAULT_DECAY_FACTOR
        assert service._baseline_ttl == DEFAULT_BASELINE_TTL_SECONDS

    def test_initialization_custom_params(self) -> None:
        """Test service initialization with custom parameters."""
        mock_redis = MagicMock()
        mock_clip = MagicMock()
        service = SceneBaselineService(
            mock_redis,
            clip_client=mock_clip,
            decay_factor=0.5,
            baseline_ttl=3600,
        )

        assert service._redis is mock_redis
        assert service._clip is mock_clip
        assert service._decay_factor == 0.5
        assert service._baseline_ttl == 3600

    def test_initialization_invalid_decay_factor_zero(self) -> None:
        """Test initialization fails with decay_factor = 0."""
        mock_redis = MagicMock()
        with pytest.raises(ValueError, match="decay_factor must be between"):
            SceneBaselineService(mock_redis, decay_factor=0.0)

    def test_initialization_invalid_decay_factor_negative(self) -> None:
        """Test initialization fails with negative decay_factor."""
        mock_redis = MagicMock()
        with pytest.raises(ValueError, match="decay_factor must be between"):
            SceneBaselineService(mock_redis, decay_factor=-0.1)

    def test_initialization_invalid_decay_factor_too_large(self) -> None:
        """Test initialization fails with decay_factor > 1."""
        mock_redis = MagicMock()
        with pytest.raises(ValueError, match="decay_factor must be between"):
            SceneBaselineService(mock_redis, decay_factor=1.5)

    def test_redis_key_generation(self) -> None:
        """Test Redis key generation for camera baselines."""
        mock_redis = MagicMock()
        service = SceneBaselineService(mock_redis)

        assert service._get_embedding_key("cam1") == "scene_baseline:cam1:embedding"
        assert service._get_count_key("cam1") == "scene_baseline:cam1:count"
        assert service._get_updated_key("cam1") == "scene_baseline:cam1:updated"

    @pytest.mark.asyncio
    async def test_has_baseline_exists(self) -> None:
        """Test has_baseline returns True when baseline exists."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)

        service = SceneBaselineService(mock_redis)
        result = await service.has_baseline("camera_1")

        assert result is True
        mock_redis.exists.assert_called_once_with("scene_baseline:camera_1:embedding")

    @pytest.mark.asyncio
    async def test_has_baseline_not_exists(self) -> None:
        """Test has_baseline returns False when baseline doesn't exist."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)

        service = SceneBaselineService(mock_redis)
        result = await service.has_baseline("camera_1")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_baseline_success(self) -> None:
        """Test get_baseline returns embedding, count, and timestamp."""
        embedding = [0.1] * EMBEDDING_DIMENSION
        timestamp = datetime.now(UTC).isoformat()

        mock_redis = create_mock_redis_with_pipeline(
            get_results=[
                json.dumps(embedding),  # embedding
                "10",  # count
                timestamp,  # updated
            ]
        )

        service = SceneBaselineService(mock_redis)
        result_embedding, count, updated = await service.get_baseline("camera_1")

        assert result_embedding == embedding
        assert count == 10
        assert updated is not None

    @pytest.mark.asyncio
    async def test_get_baseline_not_found(self) -> None:
        """Test get_baseline raises error when no baseline exists."""
        mock_redis = create_mock_redis_with_pipeline(
            get_results=[None, None, None]  # No embedding found
        )

        service = SceneBaselineService(mock_redis)

        with pytest.raises(BaselineNotFoundError, match="No baseline found"):
            await service.get_baseline("camera_1")

    @pytest.mark.asyncio
    async def test_get_baseline_info_exists(self) -> None:
        """Test get_baseline_info returns metadata when baseline exists."""
        embedding = [0.1] * EMBEDDING_DIMENSION
        timestamp = datetime.now(UTC).isoformat()

        mock_redis = create_mock_redis_with_pipeline(
            get_results=[
                json.dumps(embedding),
                "10",
                timestamp,
            ]
        )

        service = SceneBaselineService(mock_redis)
        info = await service.get_baseline_info("camera_1")

        assert info["exists"] is True
        assert info["sample_count"] == 10
        assert info["is_reliable"] is True

    @pytest.mark.asyncio
    async def test_get_baseline_info_not_exists(self) -> None:
        """Test get_baseline_info returns default when no baseline exists."""
        mock_redis = create_mock_redis_with_pipeline(
            get_results=[None, None, None]  # No embedding found
        )

        service = SceneBaselineService(mock_redis)
        info = await service.get_baseline_info("camera_1")

        assert info["exists"] is False
        assert info["sample_count"] == 0
        assert info["is_reliable"] is False

    @pytest.mark.asyncio
    async def test_get_baseline_info_not_reliable(self) -> None:
        """Test get_baseline_info shows not reliable with few samples."""
        embedding = [0.1] * EMBEDDING_DIMENSION
        timestamp = datetime.now(UTC).isoformat()

        # Only 2 samples - below MIN_SAMPLES_FOR_RELIABLE_BASELINE
        mock_redis = create_mock_redis_with_pipeline(
            get_results=[
                json.dumps(embedding),
                "2",
                timestamp,
            ]
        )

        service = SceneBaselineService(mock_redis)
        info = await service.get_baseline_info("camera_1")

        assert info["exists"] is True
        assert info["sample_count"] == 2
        assert info["is_reliable"] is False

    @pytest.mark.asyncio
    async def test_update_baseline_first_sample(self) -> None:
        """Test update_baseline with first sample creates baseline."""
        # First pipeline call: get returns None (no existing baseline)
        # Second pipeline call: set operations
        mock_redis = create_mock_redis_with_pipeline(
            pipeline_results_sequence=[
                [None, None, None],  # No existing baseline
                [True, True, True],  # SET operations succeed
            ]
        )

        service = SceneBaselineService(mock_redis)
        embedding = [0.1] * EMBEDDING_DIMENSION

        result, count = await service.update_baseline("camera_1", embedding)

        assert count == 1
        assert len(result) == EMBEDDING_DIMENSION
        # Verify pipeline was called twice (get + set)
        assert mock_redis._client.pipeline.call_count == 2

    @pytest.mark.asyncio
    async def test_update_baseline_ema_update(self) -> None:
        """Test update_baseline applies EMA to existing baseline."""
        old_embedding = [1.0] * EMBEDDING_DIMENSION
        timestamp = datetime.now(UTC).isoformat()

        # First pipeline call: get existing baseline
        # Second pipeline call: set updated baseline
        mock_redis = create_mock_redis_with_pipeline(
            pipeline_results_sequence=[
                [json.dumps(old_embedding), "5", timestamp],  # Existing baseline
                [True, True, True],  # SET operations succeed
            ]
        )

        service = SceneBaselineService(mock_redis, decay_factor=0.9)
        new_embedding = [0.0] * EMBEDDING_DIMENSION

        _, count = await service.update_baseline("camera_1", new_embedding)

        assert count == 6
        # With decay_factor=0.9, new = 0.9 * old + 0.1 * new = 0.9 * 1.0 + 0.1 * 0.0 = 0.9
        # (before normalization)

    @pytest.mark.asyncio
    async def test_update_baseline_invalid_dimension(self) -> None:
        """Test update_baseline raises error for wrong dimension."""
        mock_redis = AsyncMock()
        service = SceneBaselineService(mock_redis)

        # Wrong dimension
        embedding = [0.1] * 512

        with pytest.raises(InvalidEmbeddingError, match="768 dimensions"):
            await service.update_baseline("camera_1", embedding)

    @pytest.mark.asyncio
    async def test_set_baseline(self) -> None:
        """Test set_baseline replaces existing baseline."""
        mock_redis = create_mock_redis_with_pipeline(set_results=[True, True, True])

        service = SceneBaselineService(mock_redis)
        embedding = [0.1] * EMBEDDING_DIMENSION

        await service.set_baseline("camera_1", embedding, sample_count=100)

        # Verify pipeline was used with setex
        assert mock_redis._client.pipeline.call_count == 1

    @pytest.mark.asyncio
    async def test_set_baseline_invalid_dimension(self) -> None:
        """Test set_baseline raises error for wrong dimension."""
        mock_redis = AsyncMock()
        service = SceneBaselineService(mock_redis)

        embedding = [0.1] * 256

        with pytest.raises(InvalidEmbeddingError, match="768 dimensions"):
            await service.set_baseline("camera_1", embedding)

    @pytest.mark.asyncio
    async def test_delete_baseline_success(self) -> None:
        """Test delete_baseline removes baseline data."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=3)

        service = SceneBaselineService(mock_redis)
        result = await service.delete_baseline("camera_1")

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_baseline_not_exists(self) -> None:
        """Test delete_baseline returns False when no baseline exists."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=0)

        service = SceneBaselineService(mock_redis)
        result = await service.delete_baseline("camera_1")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_anomaly_score_no_clip_client(self) -> None:
        """Test get_anomaly_score raises error without CLIP client."""
        mock_redis = AsyncMock()
        service = SceneBaselineService(mock_redis)  # No clip_client

        image = Image.new("RGB", (224, 224))

        with pytest.raises(SceneBaselineError, match="CLIP client not configured"):
            await service.get_anomaly_score("camera_1", image)

    @pytest.mark.asyncio
    async def test_get_anomaly_score_success(self) -> None:
        """Test get_anomaly_score computes anomaly using CLIP."""
        embedding = [0.1] * EMBEDDING_DIMENSION
        timestamp = datetime.now(UTC).isoformat()

        mock_redis = create_mock_redis_with_pipeline(
            get_results=[
                json.dumps(embedding),
                str(MIN_SAMPLES_FOR_RELIABLE_BASELINE),  # Reliable baseline
                timestamp,
            ]
        )

        mock_clip = AsyncMock()
        mock_clip.anomaly_score = AsyncMock(return_value=(0.3, 0.7))

        service = SceneBaselineService(mock_redis, clip_client=mock_clip)
        image = Image.new("RGB", (224, 224))

        anomaly, similarity = await service.get_anomaly_score("camera_1", image)

        assert anomaly == 0.3
        assert similarity == 0.7
        mock_clip.anomaly_score.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_anomaly_score_no_baseline(self) -> None:
        """Test get_anomaly_score raises error without baseline."""
        mock_redis = create_mock_redis_with_pipeline(
            get_results=[None, None, None]  # No baseline found
        )

        mock_clip = AsyncMock()

        service = SceneBaselineService(mock_redis, clip_client=mock_clip)
        image = Image.new("RGB", (224, 224))

        with pytest.raises(BaselineNotFoundError):
            await service.get_anomaly_score("camera_1", image)

    @pytest.mark.asyncio
    async def test_update_baseline_from_image_no_clip_client(self) -> None:
        """Test update_baseline_from_image raises error without CLIP client."""
        mock_redis = AsyncMock()
        service = SceneBaselineService(mock_redis)

        image = Image.new("RGB", (224, 224))

        with pytest.raises(SceneBaselineError, match="CLIP client not configured"):
            await service.update_baseline_from_image("camera_1", image)

    @pytest.mark.asyncio
    async def test_update_baseline_from_image_success(self) -> None:
        """Test update_baseline_from_image extracts and updates embedding."""
        # First pipeline call: get returns None (no existing baseline)
        # Second pipeline call: set operations
        mock_redis = create_mock_redis_with_pipeline(
            pipeline_results_sequence=[
                [None, None, None],  # No existing baseline
                [True, True, True],  # SET operations succeed
            ]
        )

        mock_clip = AsyncMock()
        embedding = [0.1] * EMBEDDING_DIMENSION
        mock_clip.embed = AsyncMock(return_value=embedding)

        service = SceneBaselineService(mock_redis, clip_client=mock_clip)
        image = Image.new("RGB", (224, 224))

        result, count = await service.update_baseline_from_image("camera_1", image)

        assert count == 1
        assert len(result) == EMBEDDING_DIMENSION
        mock_clip.embed.assert_called_once_with(image)


class TestGlobalServiceFunctions:
    """Tests for global service singleton functions."""

    def test_get_scene_baseline_service_singleton(self) -> None:
        """Test get_scene_baseline_service returns singleton instance."""
        reset_scene_baseline_service()

        mock_redis = MagicMock()
        service1 = get_scene_baseline_service(mock_redis)
        service2 = get_scene_baseline_service(mock_redis)

        assert service1 is service2

        reset_scene_baseline_service()

    def test_reset_scene_baseline_service(self) -> None:
        """Test reset_scene_baseline_service clears the singleton."""
        reset_scene_baseline_service()

        mock_redis = MagicMock()
        service1 = get_scene_baseline_service(mock_redis)
        reset_scene_baseline_service()
        service2 = get_scene_baseline_service(mock_redis)

        assert service1 is not service2

        reset_scene_baseline_service()


class TestExceptions:
    """Tests for custom exceptions."""

    def test_scene_baseline_error(self) -> None:
        """Test SceneBaselineError base exception."""
        error = SceneBaselineError("Test error")
        assert str(error) == "Test error"

    def test_baseline_not_found_error(self) -> None:
        """Test BaselineNotFoundError exception."""
        error = BaselineNotFoundError("No baseline for camera_1")
        assert str(error) == "No baseline for camera_1"
        assert isinstance(error, SceneBaselineError)

    def test_invalid_embedding_error(self) -> None:
        """Test InvalidEmbeddingError exception."""
        error = InvalidEmbeddingError("Wrong dimension")
        assert str(error) == "Wrong dimension"
        assert isinstance(error, SceneBaselineError)


class TestRedisPipelining:
    """Tests for Redis pipelining optimization (NEM-1060)."""

    @pytest.mark.asyncio
    async def test_get_baseline_uses_pipeline(self) -> None:
        """Test get_baseline uses Redis pipeline for fetching all keys at once."""
        # Create mock Redis client with pipeline support
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()

        embedding = [0.1] * EMBEDDING_DIMENSION
        timestamp = datetime.now(UTC).isoformat()

        # Mock pipeline.execute() returns list of results
        mock_pipeline.execute = AsyncMock(
            return_value=[
                json.dumps(embedding),  # embedding
                "10",  # count
                timestamp,  # updated
            ]
        )

        # Mock _client.pipeline() to return our mock pipeline
        mock_redis._client = AsyncMock()
        mock_redis._client.pipeline = MagicMock(return_value=mock_pipeline)

        service = SceneBaselineService(mock_redis)
        result_embedding, count, _updated = await service.get_baseline("camera_1")

        # Verify pipeline was used
        mock_redis._client.pipeline.assert_called_once()

        # Verify all three GET commands were added to pipeline
        assert mock_pipeline.get.call_count == 3
        mock_pipeline.get.assert_any_call("scene_baseline:camera_1:embedding")
        mock_pipeline.get.assert_any_call("scene_baseline:camera_1:count")
        mock_pipeline.get.assert_any_call("scene_baseline:camera_1:updated")

        # Verify results are correctly parsed
        assert result_embedding == embedding
        assert count == 10

    @pytest.mark.asyncio
    async def test_update_baseline_uses_pipeline_for_set(self) -> None:
        """Test update_baseline uses Redis pipeline for setting all keys at once."""
        mock_redis = AsyncMock()

        # First, get_baseline will be called (which now uses pipeline)
        # Then set operations will use pipeline
        mock_get_pipeline = AsyncMock()
        mock_get_pipeline.execute = AsyncMock(
            return_value=[None, None, None]
        )  # No existing baseline

        mock_set_pipeline = AsyncMock()
        mock_set_pipeline.execute = AsyncMock(return_value=[True, True, True])

        # Pipeline is called twice: once for get, once for set
        call_count = [0]

        def get_pipeline():
            if call_count[0] == 0:
                call_count[0] += 1
                return mock_get_pipeline
            return mock_set_pipeline

        mock_redis._client = AsyncMock()
        mock_redis._client.pipeline = MagicMock(side_effect=get_pipeline)

        service = SceneBaselineService(mock_redis)
        embedding = [0.1] * EMBEDDING_DIMENSION

        _result, count = await service.update_baseline("camera_1", embedding)

        # Verify set pipeline was used with all three SET commands
        assert mock_set_pipeline.setex.call_count == 3
        mock_set_pipeline.execute.assert_called_once()

        assert count == 1

    @pytest.mark.asyncio
    async def test_set_baseline_uses_pipeline(self) -> None:
        """Test set_baseline uses Redis pipeline for setting all keys at once."""
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[True, True, True])

        mock_redis._client = AsyncMock()
        mock_redis._client.pipeline = MagicMock(return_value=mock_pipeline)

        service = SceneBaselineService(mock_redis)
        embedding = [0.1] * EMBEDDING_DIMENSION

        await service.set_baseline("camera_1", embedding, sample_count=100)

        # Verify pipeline was used
        mock_redis._client.pipeline.assert_called_once()

        # Verify all three SETEX commands were added
        assert mock_pipeline.setex.call_count == 3
        mock_pipeline.execute.assert_called_once()


class TestConstants:
    """Tests for module constants."""

    def test_embedding_dimension(self) -> None:
        """Test EMBEDDING_DIMENSION is correct for CLIP ViT-L."""
        assert EMBEDDING_DIMENSION == 768

    def test_default_ttl(self) -> None:
        """Test default TTL is 7 days."""
        assert DEFAULT_BASELINE_TTL_SECONDS == 7 * 24 * 60 * 60

    def test_default_decay_factor(self) -> None:
        """Test default decay factor is reasonable."""
        assert 0 < DEFAULT_DECAY_FACTOR <= 1

    def test_min_samples_for_reliable(self) -> None:
        """Test minimum samples for reliable baseline."""
        assert MIN_SAMPLES_FOR_RELIABLE_BASELINE == 5
