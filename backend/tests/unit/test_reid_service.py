"""Unit tests for Re-Identification Service.

Tests cover:
- EntityEmbedding dataclass serialization and deserialization
- EntityMatch dataclass
- cosine_similarity function
- ReIdentificationService embedding storage and matching
- Redis storage pattern with TTL
- Global service singleton
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.services.reid_service import (
    DEFAULT_SIMILARITY_THRESHOLD,
    EMBEDDING_DIMENSION,
    EMBEDDING_TTL_SECONDS,
    EntityEmbedding,
    EntityMatch,
    ReIdentificationService,
    cosine_similarity,
    get_reid_service,
    reset_reid_service,
)


class TestEntityEmbedding:
    """Tests for EntityEmbedding dataclass."""

    def test_entity_embedding_creation(self) -> None:
        """Test creating an EntityEmbedding with all fields."""
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2, 0.3],
            camera_id="front_door",
            timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            detection_id="det_123",
            attributes={"clothing": "blue jacket"},
        )

        assert embedding.entity_type == "person"
        assert embedding.embedding == [0.1, 0.2, 0.3]
        assert embedding.camera_id == "front_door"
        assert embedding.detection_id == "det_123"
        assert embedding.attributes == {"clothing": "blue jacket"}

    def test_entity_embedding_default_attributes(self) -> None:
        """Test that attributes defaults to empty dict."""
        embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5, 0.6],
            camera_id="driveway",
            timestamp=datetime.now(UTC),
            detection_id="det_456",
        )

        assert embedding.attributes == {}

    def test_entity_embedding_to_dict(self) -> None:
        """Test conversion to dictionary for JSON serialization."""
        timestamp = datetime(2026, 1, 1, 14, 30, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2, 0.3],
            camera_id="garage",
            timestamp=timestamp,
            detection_id="det_789",
            attributes={"action": "walking"},
        )

        d = embedding.to_dict()

        assert d["entity_type"] == "person"
        assert d["embedding"] == [0.1, 0.2, 0.3]
        assert d["camera_id"] == "garage"
        assert d["timestamp"] == timestamp.isoformat()
        assert d["detection_id"] == "det_789"
        assert d["attributes"] == {"action": "walking"}

    def test_entity_embedding_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "entity_type": "vehicle",
            "embedding": [0.4, 0.5, 0.6],
            "camera_id": "backyard",
            "timestamp": "2026-01-01T10:00:00+00:00",
            "detection_id": "det_101",
            "attributes": {"color": "red"},
        }

        embedding = EntityEmbedding.from_dict(data)

        assert embedding.entity_type == "vehicle"
        assert embedding.embedding == [0.4, 0.5, 0.6]
        assert embedding.camera_id == "backyard"
        assert embedding.timestamp == datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        assert embedding.detection_id == "det_101"
        assert embedding.attributes == {"color": "red"}

    def test_entity_embedding_from_dict_missing_attributes(self) -> None:
        """Test from_dict with missing attributes field."""
        data = {
            "entity_type": "person",
            "embedding": [0.1],
            "camera_id": "test",
            "timestamp": "2026-01-01T12:00:00+00:00",
            "detection_id": "det_test",
        }

        embedding = EntityEmbedding.from_dict(data)

        assert embedding.attributes == {}

    def test_entity_embedding_from_dict_datetime_object(self) -> None:
        """Test from_dict when timestamp is already a datetime object."""
        timestamp = datetime(2026, 1, 1, 15, 0, 0, tzinfo=UTC)
        data = {
            "entity_type": "person",
            "embedding": [0.1],
            "camera_id": "test",
            "timestamp": timestamp,
            "detection_id": "det_test",
        }

        embedding = EntityEmbedding.from_dict(data)

        assert embedding.timestamp == timestamp

    def test_entity_embedding_roundtrip(self) -> None:
        """Test that to_dict and from_dict are inverse operations."""
        original = EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            camera_id="front_door",
            timestamp=datetime(2026, 1, 1, 12, 30, 45, tzinfo=UTC),
            detection_id="det_roundtrip",
            attributes={"clothing": "red shirt", "carrying": "backpack"},
        )

        reconstructed = EntityEmbedding.from_dict(original.to_dict())

        assert reconstructed.entity_type == original.entity_type
        assert reconstructed.embedding == original.embedding
        assert reconstructed.camera_id == original.camera_id
        assert reconstructed.timestamp == original.timestamp
        assert reconstructed.detection_id == original.detection_id
        assert reconstructed.attributes == original.attributes


class TestEntityMatch:
    """Tests for EntityMatch dataclass."""

    def test_entity_match_creation(self) -> None:
        """Test creating an EntityMatch."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2],
            camera_id="test",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
        )

        match = EntityMatch(
            entity=entity,
            similarity=0.92,
            time_gap_seconds=300.5,
        )

        assert match.entity is entity
        assert match.similarity == 0.92
        assert match.time_gap_seconds == 300.5


class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self) -> None:
        """Test cosine similarity of identical vectors is 1."""
        vec = [0.1, 0.2, 0.3, 0.4, 0.5]
        similarity = cosine_similarity(vec, vec)

        assert abs(similarity - 1.0) < 1e-6

    def test_opposite_vectors(self) -> None:
        """Test cosine similarity of opposite vectors is -1."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = cosine_similarity(vec1, vec2)

        assert abs(similarity - (-1.0)) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        """Test cosine similarity of orthogonal vectors is 0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = cosine_similarity(vec1, vec2)

        assert abs(similarity) < 1e-6

    def test_similar_vectors(self) -> None:
        """Test cosine similarity of similar vectors is high."""
        vec1 = [0.8, 0.6, 0.0]
        vec2 = [0.9, 0.5, 0.1]
        similarity = cosine_similarity(vec1, vec2)

        # These vectors are similar, expect high similarity
        assert similarity > 0.9

    def test_different_length_vectors_raises(self) -> None:
        """Test that different length vectors raise ValueError."""
        vec1 = [0.1, 0.2, 0.3]
        vec2 = [0.4, 0.5]

        with pytest.raises(ValueError, match="same dimension"):
            cosine_similarity(vec1, vec2)

    def test_zero_vector_returns_zero(self) -> None:
        """Test that zero vectors return 0 similarity."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_both_zero_vectors_returns_zero(self) -> None:
        """Test that two zero vectors return 0 similarity."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_normalized_vectors(self) -> None:
        """Test with already normalized vectors."""
        # Unit vectors
        vec1 = [1.0 / np.sqrt(2), 1.0 / np.sqrt(2), 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = cosine_similarity(vec1, vec2)

        # cos(45 degrees) = sqrt(2)/2 ~= 0.707
        expected = 1.0 / np.sqrt(2)
        assert abs(similarity - expected) < 1e-6

    def test_high_dimensional_vectors(self) -> None:
        """Test with 768-dimensional vectors (CLIP embedding size)."""
        np.random.seed(42)
        vec1 = list(np.random.randn(EMBEDDING_DIMENSION))
        vec2 = list(np.random.randn(EMBEDDING_DIMENSION))

        # Should not raise
        similarity = cosine_similarity(vec1, vec2)

        # Random vectors typically have low similarity
        assert -1.0 <= similarity <= 1.0


class TestReIdentificationService:
    """Tests for ReIdentificationService class."""

    def setup_method(self) -> None:
        """Reset service before each test."""
        reset_reid_service()

    def teardown_method(self) -> None:
        """Reset service after each test."""
        reset_reid_service()

    def test_service_init(self) -> None:
        """Test ReIdentificationService initialization."""
        service = ReIdentificationService()
        assert service is not None

    def test_global_service_singleton(self) -> None:
        """Test global service singleton."""
        service1 = get_reid_service()
        service2 = get_reid_service()

        assert service1 is service2

        reset_reid_service()

        service3 = get_reid_service()
        assert service3 is not service1

    @pytest.mark.asyncio
    async def test_generate_embedding_cropped_image(self) -> None:
        """Test generate_embedding with bounding box crop."""
        service = ReIdentificationService()

        # Create mock image
        mock_image = MagicMock()
        mock_cropped = MagicMock()
        mock_image.crop.return_value = mock_cropped

        # Create mock model
        mock_processor = MagicMock()
        mock_inputs = {"pixel_values": MagicMock()}
        mock_processor.return_value = mock_inputs

        mock_clip_model = MagicMock()

        # Mock tensor operations
        mock_features = MagicMock()
        mock_features.norm.return_value = MagicMock()
        mock_features.__truediv__ = MagicMock(return_value=mock_features)
        mock_features.__getitem__ = MagicMock(
            return_value=MagicMock(
                cpu=MagicMock(
                    return_value=MagicMock(
                        numpy=MagicMock(
                            return_value=MagicMock(tolist=MagicMock(return_value=[0.1] * 768))
                        )
                    )
                )
            )
        )
        mock_clip_model.get_image_features.return_value = mock_features

        # Mock device
        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_clip_model.parameters.return_value = iter([mock_param])

        model = {"model": mock_clip_model, "processor": mock_processor}

        # Mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        with patch.dict("sys.modules", {"torch": mock_torch}):
            embedding = await service.generate_embedding(model, mock_image, bbox=(10, 20, 100, 150))

        # Verify crop was called with bbox
        mock_image.crop.assert_called_once_with((10, 20, 100, 150))
        assert len(embedding) == 768

    @pytest.mark.asyncio
    async def test_generate_embedding_failure(self) -> None:
        """Test generate_embedding handles failures gracefully."""
        service = ReIdentificationService()

        mock_image = MagicMock()
        mock_model = {"model": None, "processor": None}

        with pytest.raises(RuntimeError, match="Embedding generation failed"):
            await service.generate_embedding(mock_model, mock_image)

    @pytest.mark.asyncio
    async def test_store_embedding_new_key(self) -> None:
        """Test storing embedding when key doesn't exist."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        timestamp = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2, 0.3],
            camera_id="front",
            timestamp=timestamp,
            detection_id="det_001",
            attributes={"clothing": "blue"},
        )

        await service.store_embedding(mock_redis, embedding)

        # Verify Redis calls
        mock_redis.get.assert_called_once_with("entity_embeddings:2026-01-01")
        mock_redis.setex.assert_called_once()

        # Check the stored data
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "entity_embeddings:2026-01-01"
        assert call_args[0][1] == EMBEDDING_TTL_SECONDS

        stored_data = json.loads(call_args[0][2])
        assert len(stored_data["persons"]) == 1
        assert stored_data["vehicles"] == []
        assert stored_data["persons"][0]["entity_type"] == "person"

    @pytest.mark.asyncio
    async def test_store_embedding_existing_key(self) -> None:
        """Test storing embedding when key already exists."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()

        existing_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": [0.1],
                    "camera_id": "back",
                    "timestamp": "2026-01-01T10:00:00+00:00",
                    "detection_id": "det_existing",
                    "attributes": {},
                }
            ],
            "vehicles": [],
        }
        mock_redis.get.return_value = json.dumps(existing_data)

        timestamp = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.2],
            camera_id="front",
            timestamp=timestamp,
            detection_id="det_new",
        )

        await service.store_embedding(mock_redis, embedding)

        # Check the stored data has both embeddings
        call_args = mock_redis.setex.call_args
        stored_data = json.loads(call_args[0][2])
        assert len(stored_data["persons"]) == 2

    @pytest.mark.asyncio
    async def test_store_embedding_vehicle(self) -> None:
        """Test storing vehicle embedding."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        timestamp = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5, 0.6],
            camera_id="driveway",
            timestamp=timestamp,
            detection_id="det_car",
            attributes={"color": "white"},
        )

        await service.store_embedding(mock_redis, embedding)

        call_args = mock_redis.setex.call_args
        stored_data = json.loads(call_args[0][2])
        assert len(stored_data["vehicles"]) == 1
        assert stored_data["persons"] == []

    @pytest.mark.asyncio
    async def test_find_matching_entities_no_matches(self) -> None:
        """Test find_matching_entities when no matches exist."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        matches = await service.find_matching_entities(
            mock_redis, [0.1, 0.2, 0.3], entity_type="person"
        )

        assert matches == []

    @pytest.mark.asyncio
    async def test_find_matching_entities_with_matches(self) -> None:
        """Test find_matching_entities with matching entities."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()

        # Create stored embedding that will match
        vec1 = [0.8, 0.6, 0.0]  # Normalize
        norm1 = np.linalg.norm(vec1)
        normalized_vec1 = [v / norm1 for v in vec1]

        stored_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": normalized_vec1,
                    "camera_id": "back",
                    "timestamp": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                    "detection_id": "det_stored",
                    "attributes": {"clothing": "red"},
                }
            ],
            "vehicles": [],
        }

        today_key = f"entity_embeddings:{datetime.now(UTC).strftime('%Y-%m-%d')}"

        # Only return data for one date (today), return None for other dates
        async def mock_get(key: str) -> str | None:
            if key == today_key:
                return json.dumps(stored_data)
            return None

        mock_redis.get = mock_get

        # Query with very similar embedding
        query_vec = [0.81, 0.59, 0.01]
        norm_q = np.linalg.norm(query_vec)
        normalized_query = [v / norm_q for v in query_vec]

        matches = await service.find_matching_entities(
            mock_redis,
            normalized_query,
            entity_type="person",
            threshold=0.95,
        )

        assert len(matches) == 1
        assert matches[0].similarity > 0.95
        assert matches[0].entity.detection_id == "det_stored"
        assert matches[0].time_gap_seconds > 0

    @pytest.mark.asyncio
    async def test_find_matching_entities_below_threshold(self) -> None:
        """Test find_matching_entities filters out low similarity."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()

        # Create stored embedding that won't match
        stored_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": [1.0, 0.0, 0.0],
                    "camera_id": "back",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "detection_id": "det_stored",
                    "attributes": {},
                }
            ],
            "vehicles": [],
        }
        mock_redis.get.return_value = json.dumps(stored_data)

        # Query with very different embedding
        matches = await service.find_matching_entities(
            mock_redis,
            [0.0, 0.0, 1.0],
            entity_type="person",
            threshold=0.85,
        )

        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_find_matching_entities_excludes_same_detection(self) -> None:
        """Test find_matching_entities excludes the same detection ID."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()

        vec = [0.5, 0.5, 0.5]
        stored_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": vec,
                    "camera_id": "front",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "detection_id": "det_same",
                    "attributes": {},
                }
            ],
            "vehicles": [],
        }
        mock_redis.get.return_value = json.dumps(stored_data)

        # Query with same vector and same detection_id
        matches = await service.find_matching_entities(
            mock_redis,
            vec,
            entity_type="person",
            threshold=0.0,  # Accept any similarity
            exclude_detection_id="det_same",
        )

        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_find_matching_entities_sorted_by_similarity(self) -> None:
        """Test find_matching_entities returns results sorted by similarity."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()

        stored_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": [0.9, 0.1, 0.0],  # Less similar
                    "camera_id": "front",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "detection_id": "det_1",
                    "attributes": {},
                },
                {
                    "entity_type": "person",
                    "embedding": [0.99, 0.01, 0.0],  # More similar
                    "camera_id": "back",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "detection_id": "det_2",
                    "attributes": {},
                },
            ],
            "vehicles": [],
        }

        today_key = f"entity_embeddings:{datetime.now(UTC).strftime('%Y-%m-%d')}"

        # Only return data for one date (today), return None for other dates
        async def mock_get(key: str) -> str | None:
            if key == today_key:
                return json.dumps(stored_data)
            return None

        mock_redis.get = mock_get

        matches = await service.find_matching_entities(
            mock_redis,
            [1.0, 0.0, 0.0],
            entity_type="person",
            threshold=0.8,
        )

        assert len(matches) == 2
        # Higher similarity first
        assert matches[0].similarity > matches[1].similarity
        assert matches[0].entity.detection_id == "det_2"

    @pytest.mark.asyncio
    async def test_find_matching_entities_handles_error(self) -> None:
        """Test find_matching_entities handles Redis errors gracefully."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis connection failed")

        matches = await service.find_matching_entities(mock_redis, [0.1, 0.2], entity_type="person")

        assert matches == []

    @pytest.mark.asyncio
    async def test_get_entity_history_empty(self) -> None:
        """Test get_entity_history when no data exists."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        history = await service.get_entity_history(mock_redis, "person")

        assert history == []

    @pytest.mark.asyncio
    async def test_get_entity_history_with_data(self) -> None:
        """Test get_entity_history returns stored embeddings."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()

        stored_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": [0.1],
                    "camera_id": "front",
                    "timestamp": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
                    "detection_id": "det_old",
                    "attributes": {},
                },
                {
                    "entity_type": "person",
                    "embedding": [0.2],
                    "camera_id": "back",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "detection_id": "det_new",
                    "attributes": {},
                },
            ],
            "vehicles": [],
        }

        today_key = f"entity_embeddings:{datetime.now(UTC).strftime('%Y-%m-%d')}"

        # Only return data for one date (today), return None for other dates
        async def mock_get(key: str) -> str | None:
            if key == today_key:
                return json.dumps(stored_data)
            return None

        mock_redis.get = mock_get

        history = await service.get_entity_history(mock_redis, "person")

        assert len(history) == 2
        # Should be sorted by timestamp (newest first)
        assert history[0].detection_id == "det_new"
        assert history[1].detection_id == "det_old"

    @pytest.mark.asyncio
    async def test_get_entity_history_filter_by_camera(self) -> None:
        """Test get_entity_history filters by camera_id."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()

        stored_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": [0.1],
                    "camera_id": "front",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "detection_id": "det_front",
                    "attributes": {},
                },
                {
                    "entity_type": "person",
                    "embedding": [0.2],
                    "camera_id": "back",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "detection_id": "det_back",
                    "attributes": {},
                },
            ],
            "vehicles": [],
        }

        today_key = f"entity_embeddings:{datetime.now(UTC).strftime('%Y-%m-%d')}"

        # Only return data for one date (today), return None for other dates
        async def mock_get(key: str) -> str | None:
            if key == today_key:
                return json.dumps(stored_data)
            return None

        mock_redis.get = mock_get

        history = await service.get_entity_history(mock_redis, "person", camera_id="front")

        assert len(history) == 1
        assert history[0].detection_id == "det_front"

    @pytest.mark.asyncio
    async def test_get_entity_history_handles_error(self) -> None:
        """Test get_entity_history handles errors gracefully."""
        service = ReIdentificationService()
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")

        history = await service.get_entity_history(mock_redis, "person")

        assert history == []


class TestConstants:
    """Tests for module constants."""

    def test_embedding_ttl_seconds(self) -> None:
        """Test EMBEDDING_TTL_SECONDS is 24 hours."""
        assert EMBEDDING_TTL_SECONDS == 86400

    def test_default_similarity_threshold(self) -> None:
        """Test DEFAULT_SIMILARITY_THRESHOLD is 0.85."""
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.85

    def test_embedding_dimension(self) -> None:
        """Test EMBEDDING_DIMENSION is 768."""
        assert EMBEDDING_DIMENSION == 768


class TestCLIPLoader:
    """Tests for CLIP model loader."""

    @pytest.mark.asyncio
    async def test_load_clip_model_import_error(self) -> None:
        """Test load_clip_model raises ImportError when transformers missing."""
        from backend.services.clip_loader import load_clip_model

        with (
            patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'transformers'"),
            ),
            pytest.raises(ImportError, match="transformers"),
        ):
            await load_clip_model("openai/clip-vit-large-patch14")

    @pytest.mark.asyncio
    async def test_load_clip_model_runtime_error(self) -> None:
        """Test load_clip_model raises RuntimeError on load failure."""
        from backend.services.clip_loader import load_clip_model

        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.side_effect = ValueError("Model not found")

        with (
            patch.dict("sys.modules", {"transformers": mock_transformers}),
            pytest.raises(RuntimeError, match="Failed to load CLIP model"),
        ):
            await load_clip_model("invalid/model")


class TestModelZooCLIPIntegration:
    """Tests for CLIP model in Model Zoo."""

    def setup_method(self) -> None:
        """Reset model zoo before each test."""
        from backend.services.model_zoo import reset_model_zoo

        reset_model_zoo()

    def teardown_method(self) -> None:
        """Reset model zoo after each test."""
        from backend.services.model_zoo import reset_model_zoo

        reset_model_zoo()

    def test_clip_model_in_registry(self) -> None:
        """Test that CLIP ViT-L is in the MODEL_ZOO registry."""
        from backend.services.model_zoo import get_model_zoo

        zoo = get_model_zoo()

        assert "clip-vit-l" in zoo
        config = zoo["clip-vit-l"]

        assert config.name == "clip-vit-l"
        assert config.path == "openai/clip-vit-large-patch14"
        assert config.category == "embedding"
        assert config.vram_mb == 800
        assert config.enabled is True
        assert config.available is False

    def test_get_clip_model_config(self) -> None:
        """Test getting CLIP model config."""
        from backend.services.model_zoo import get_model_config

        config = get_model_config("clip-vit-l")

        assert config is not None
        assert config.name == "clip-vit-l"
        assert config.vram_mb == 800

    def test_clip_in_enabled_models(self) -> None:
        """Test that CLIP is in enabled models list."""
        from backend.services.model_zoo import get_enabled_models

        enabled = get_enabled_models()
        enabled_names = [m.name for m in enabled]

        assert "clip-vit-l" in enabled_names
