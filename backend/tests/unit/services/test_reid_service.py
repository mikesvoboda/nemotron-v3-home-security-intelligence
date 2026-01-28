"""Unit tests for ReIdentification service.

Tests cover:
- ReIdentificationService initialization
- Feature extraction via CLIP client
- Cosine similarity calculations
- Redis storage and retrieval of embeddings
- Entity matching with similarity thresholds
- Prompt formatting functions
- Error handling
- Global singleton functions
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.services.clip_client import CLIPUnavailableError
from backend.services.reid_service import (
    DEFAULT_SIMILARITY_THRESHOLD,
    EMBEDDING_DIMENSION,
    EMBEDDING_TTL_SECONDS,
    EntityEmbedding,
    EntityMatch,
    ReIdentificationService,
    batch_cosine_similarity,
    clean_vqa_output,
    cosine_similarity,
    format_entity_match,
    format_full_reid_context,
    format_reid_context,
    format_reid_summary,
    get_reid_service,
    reset_reid_service,
)

# =============================================================================
# Module-level Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def mock_get_settings_for_reid():
    """Mock get_settings() for all tests in this module.

    ReIdentificationService.__init__() calls get_settings() to read
    configuration values. This fixture ensures that tests can instantiate
    the service without triggering real Settings validation.

    The mock settings object provides default values for all ReID-related
    configuration parameters.
    """
    mock_settings = MagicMock()
    # ReID-specific settings
    mock_settings.reid_max_concurrent_requests = 10
    mock_settings.reid_embedding_timeout = 30.0
    mock_settings.reid_max_retries = 3

    # Database and Redis settings (required by Settings validation)
    mock_settings.database_url = (
        "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    )
    mock_settings.redis_url = "redis://localhost:6379/15"

    with patch("backend.services.reid_service.get_settings", return_value=mock_settings):
        yield mock_settings


# =============================================================================
# EntityEmbedding Dataclass Tests
# =============================================================================


class TestEntityEmbedding:
    """Tests for EntityEmbedding dataclass."""

    def test_entity_embedding_creation(self) -> None:
        """Test creating an EntityEmbedding instance."""
        now = datetime.now(UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_123",
            attributes={"clothing": "blue jacket"},
        )

        assert embedding.entity_type == "person"
        assert len(embedding.embedding) == EMBEDDING_DIMENSION
        assert embedding.camera_id == "front_door"
        assert embedding.timestamp == now
        assert embedding.detection_id == "det_123"
        assert embedding.attributes == {"clothing": "blue jacket"}

    def test_entity_embedding_default_attributes(self) -> None:
        """Test that attributes defaults to empty dict."""
        embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * EMBEDDING_DIMENSION,
            camera_id="garage",
            timestamp=datetime.now(UTC),
            detection_id="det_456",
        )

        assert embedding.attributes == {}

    def test_entity_embedding_to_dict(self) -> None:
        """Test converting EntityEmbedding to dictionary."""
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2, 0.3],
            camera_id="front_door",
            timestamp=now,
            detection_id="det_123",
            attributes={"clothing": "red shirt"},
        )

        result = embedding.to_dict()

        assert result["entity_type"] == "person"
        assert result["embedding"] == [0.1, 0.2, 0.3]
        assert result["camera_id"] == "front_door"
        assert result["timestamp"] == "2025-12-25T12:00:00+00:00"
        assert result["detection_id"] == "det_123"
        assert result["attributes"] == {"clothing": "red shirt"}

    def test_entity_embedding_from_dict_with_string_timestamp(self) -> None:
        """Test creating EntityEmbedding from dict with string timestamp."""
        data = {
            "entity_type": "person",
            "embedding": [0.1, 0.2, 0.3],
            "camera_id": "front_door",
            "timestamp": "2025-12-25T12:00:00+00:00",
            "detection_id": "det_123",
            "attributes": {"clothing": "blue jacket"},
        }

        embedding = EntityEmbedding.from_dict(data)

        assert embedding.entity_type == "person"
        assert embedding.embedding == [0.1, 0.2, 0.3]
        assert embedding.camera_id == "front_door"
        assert embedding.timestamp == datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        assert embedding.detection_id == "det_123"
        assert embedding.attributes == {"clothing": "blue jacket"}

    def test_entity_embedding_from_dict_with_datetime_timestamp(self) -> None:
        """Test creating EntityEmbedding from dict with datetime timestamp."""
        now = datetime.now(UTC)
        data = {
            "entity_type": "vehicle",
            "embedding": [0.5] * 10,
            "camera_id": "garage",
            "timestamp": now,
            "detection_id": "det_456",
        }

        embedding = EntityEmbedding.from_dict(data)

        assert embedding.timestamp == now

    def test_entity_embedding_from_dict_missing_attributes(self) -> None:
        """Test creating EntityEmbedding from dict without attributes."""
        data = {
            "entity_type": "person",
            "embedding": [0.1],
            "camera_id": "camera_1",
            "timestamp": "2025-12-25T12:00:00+00:00",
            "detection_id": "det_789",
        }

        embedding = EntityEmbedding.from_dict(data)

        assert embedding.attributes == {}

    def test_entity_embedding_roundtrip(self) -> None:
        """Test that to_dict and from_dict are inverse operations."""
        original = EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            camera_id="front_door",
            timestamp=datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC),
            detection_id="det_123",
            attributes={"clothing": "green hat", "carrying": "backpack"},
        )

        reconstructed = EntityEmbedding.from_dict(original.to_dict())

        assert reconstructed.entity_type == original.entity_type
        assert reconstructed.embedding == original.embedding
        assert reconstructed.camera_id == original.camera_id
        assert reconstructed.timestamp == original.timestamp
        assert reconstructed.detection_id == original.detection_id
        assert reconstructed.attributes == original.attributes


# =============================================================================
# Cosine Similarity Tests
# =============================================================================


class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self) -> None:
        """Test cosine similarity of identical vectors is 1."""
        vec = [1.0, 2.0, 3.0, 4.0, 5.0]
        similarity = cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001

    def test_orthogonal_vectors(self) -> None:
        """Test cosine similarity of orthogonal vectors is 0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.0001

    def test_opposite_vectors(self) -> None:
        """Test cosine similarity of opposite vectors is -1."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 0.0001

    def test_similar_vectors(self) -> None:
        """Test cosine similarity of similar vectors is high."""
        vec1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        vec2 = [1.1, 2.1, 3.1, 4.1, 5.1]
        similarity = cosine_similarity(vec1, vec2)
        assert similarity > 0.99

    def test_different_length_vectors_raises_error(self) -> None:
        """Test that vectors of different lengths raise ValueError."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]
        with pytest.raises(ValueError) as exc_info:
            cosine_similarity(vec1, vec2)
        assert "same dimension" in str(exc_info.value)

    def test_zero_vector_first(self) -> None:
        """Test cosine similarity with zero vector returns 0."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_zero_vector_second(self) -> None:
        """Test cosine similarity with zero vector returns 0."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_both_zero_vectors(self) -> None:
        """Test cosine similarity of two zero vectors returns 0."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [0.0, 0.0, 0.0]
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_large_vectors(self) -> None:
        """Test cosine similarity works with large vectors."""
        vec1 = [float(i) for i in range(EMBEDDING_DIMENSION)]
        vec2 = [float(i + 0.1) for i in range(EMBEDDING_DIMENSION)]
        similarity = cosine_similarity(vec1, vec2)
        assert similarity > 0.99

    def test_normalized_vectors(self) -> None:
        """Test cosine similarity with normalized vectors."""
        import math

        vec1 = [3.0, 4.0]  # magnitude 5
        vec2 = [4.0, 3.0]  # magnitude 5

        # Normalize
        mag1 = math.sqrt(sum(x * x for x in vec1))
        mag2 = math.sqrt(sum(x * x for x in vec2))
        norm1 = [x / mag1 for x in vec1]
        norm2 = [x / mag2 for x in vec2]

        similarity = cosine_similarity(norm1, norm2)
        # Both normalized, similarity = dot product
        expected = (3 / 5) * (4 / 5) + (4 / 5) * (3 / 5)
        assert abs(similarity - expected) < 0.0001


# =============================================================================
# Batch Cosine Similarity Tests (NEM-1071)
# =============================================================================


class TestBatchCosineSimilarity:
    """Tests for batch_cosine_similarity function.

    NEM-1071: Optimize ReIdentificationService with batch matrix operations.
    This function computes cosine similarities between one query vector and
    multiple candidate vectors in a single vectorized operation.
    """

    def test_batch_identical_vectors(self) -> None:
        """Test batch similarity with identical vectors returns all 1.0."""

        query = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidates = [[1.0, 2.0, 3.0, 4.0, 5.0]] * 5

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 5
        for sim in similarities:
            assert abs(sim - 1.0) < 0.0001

    def test_batch_orthogonal_vectors(self) -> None:
        """Test batch similarity with orthogonal vectors returns 0."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 2
        for sim in similarities:
            assert abs(sim) < 0.0001

    def test_batch_opposite_vectors(self) -> None:
        """Test batch similarity with opposite vectors returns -1."""
        query = [1.0, 2.0, 3.0]
        candidates = [
            [-1.0, -2.0, -3.0],
            [-2.0, -4.0, -6.0],  # Same direction as first candidate
        ]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 2
        for sim in similarities:
            assert abs(sim - (-1.0)) < 0.0001

    def test_batch_mixed_similarities(self) -> None:
        """Test batch with candidates of varying similarity."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            [1.0, 0.0, 0.0],  # Same direction -> 1.0
            [0.0, 1.0, 0.0],  # Orthogonal -> 0.0
            [-1.0, 0.0, 0.0],  # Opposite -> -1.0
            [0.707, 0.707, 0.0],  # 45 degrees -> ~0.707
        ]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 4
        assert abs(similarities[0] - 1.0) < 0.0001
        assert abs(similarities[1] - 0.0) < 0.0001
        assert abs(similarities[2] - (-1.0)) < 0.0001
        assert abs(similarities[3] - 0.707) < 0.01

    def test_batch_empty_candidates(self) -> None:
        """Test batch with empty candidates list."""
        query = [1.0, 2.0, 3.0]
        candidates: list[list[float]] = []

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 0
        assert isinstance(similarities, list)

    def test_batch_single_candidate(self) -> None:
        """Test batch with single candidate."""
        query = [1.0, 2.0, 3.0]
        candidates = [[1.0, 2.0, 3.0]]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 1
        assert abs(similarities[0] - 1.0) < 0.0001

    def test_batch_large_vectors(self) -> None:
        """Test batch works with large vectors (CLIP embedding size)."""

        query = [float(i) for i in range(EMBEDDING_DIMENSION)]
        # Create candidates with slight variations
        candidates = [
            [float(i + 0.1) for i in range(EMBEDDING_DIMENSION)],
            [float(i + 0.5) for i in range(EMBEDDING_DIMENSION)],
            [float(i - 0.1) for i in range(EMBEDDING_DIMENSION)],
        ]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 3
        # All should be very similar to the query
        for sim in similarities:
            assert sim > 0.99

    def test_batch_many_candidates(self) -> None:
        """Test batch handles large number of candidates efficiently."""

        query = [float(i % 10) for i in range(100)]
        # 1000 candidates
        candidates = [[float((i + j) % 10) for j in range(100)] for i in range(1000)]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 1000
        # All should be valid similarity values
        for sim in similarities:
            assert -1.0 <= sim <= 1.0

    def test_batch_zero_query_vector(self) -> None:
        """Test batch handles zero query vector."""
        query = [0.0, 0.0, 0.0]
        candidates = [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 2
        # Zero vectors should return 0 similarity
        for sim in similarities:
            assert sim == 0.0

    def test_batch_zero_candidate_vectors(self) -> None:
        """Test batch handles zero candidate vectors."""
        query = [1.0, 2.0, 3.0]
        candidates = [
            [0.0, 0.0, 0.0],
            [1.0, 2.0, 3.0],
        ]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 2
        assert similarities[0] == 0.0  # Zero candidate
        assert abs(similarities[1] - 1.0) < 0.0001  # Same as query

    def test_batch_matches_single_similarity(self) -> None:
        """Test that batch results match individual cosine_similarity calls."""
        query = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidates = [
            [5.0, 4.0, 3.0, 2.0, 1.0],
            [1.1, 2.1, 3.1, 4.1, 5.1],
            [0.5, 1.0, 1.5, 2.0, 2.5],
            [-1.0, -2.0, -3.0, -4.0, -5.0],
        ]

        batch_results = batch_cosine_similarity(query, candidates)
        single_results = [cosine_similarity(query, c) for c in candidates]

        assert len(batch_results) == len(single_results)
        for batch_sim, single_sim in zip(batch_results, single_results, strict=True):
            assert abs(batch_sim - single_sim) < 0.0001

    def test_batch_returns_python_list(self) -> None:
        """Test that batch returns a Python list, not numpy array."""
        query = [1.0, 2.0, 3.0]
        candidates = [[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]]

        similarities = batch_cosine_similarity(query, candidates)

        assert isinstance(similarities, list)
        for sim in similarities:
            assert isinstance(sim, float)


# =============================================================================
# ReIdentificationService Initialization Tests
# =============================================================================


class TestReIdentificationServiceInit:
    """Tests for ReIdentificationService initialization."""

    def test_init_without_clip_client(self) -> None:
        """Test initialization without providing clip_client."""
        service = ReIdentificationService()
        assert service._clip_client is None

    def test_init_with_clip_client(self) -> None:
        """Test initialization with custom clip_client."""
        mock_client = MagicMock()
        service = ReIdentificationService(clip_client=mock_client)
        assert service._clip_client is mock_client

    def test_clip_client_property_returns_provided_client(self) -> None:
        """Test clip_client property returns provided client."""
        mock_client = MagicMock()
        service = ReIdentificationService(clip_client=mock_client)
        assert service.clip_client is mock_client

    @patch("backend.services.reid_service.get_clip_client")
    def test_clip_client_property_gets_global_client(self, mock_get_client: MagicMock) -> None:
        """Test clip_client property gets global client when none provided."""
        mock_global_client = MagicMock()
        mock_get_client.return_value = mock_global_client

        service = ReIdentificationService()
        client = service.clip_client

        mock_get_client.assert_called_once()
        assert client is mock_global_client


# =============================================================================
# ReIdentificationService.generate_embedding Tests
# =============================================================================


class TestGenerateEmbedding:
    """Tests for ReIdentificationService.generate_embedding method."""

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self) -> None:
        """Test successful embedding generation."""
        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.1] * EMBEDDING_DIMENSION

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (100, 100), color="red")

        embedding = await service.generate_embedding(image)

        assert len(embedding) == EMBEDDING_DIMENSION
        mock_client.embed.assert_called_once_with(image)

    @pytest.mark.asyncio
    async def test_generate_embedding_with_bbox(self) -> None:
        """Test embedding generation with bounding box crop."""
        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.5] * EMBEDDING_DIMENSION

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (200, 200), color="blue")

        embedding = await service.generate_embedding(image, bbox=(50, 50, 150, 150))

        assert len(embedding) == EMBEDDING_DIMENSION
        # Verify embed was called with a cropped image
        called_image = mock_client.embed.call_args[0][0]
        assert called_image.size == (100, 100)

    @pytest.mark.asyncio
    async def test_generate_embedding_deprecated_model_param(self) -> None:
        """Test that model parameter logs a warning but works."""
        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.1] * EMBEDDING_DIMENSION

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (100, 100), color="green")

        with patch("backend.services.reid_service.logger") as mock_logger:
            embedding = await service.generate_embedding(image, model={"some": "model"})

            mock_logger.warning.assert_called()
            assert "deprecated" in str(mock_logger.warning.call_args).lower()

        assert len(embedding) == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_generate_embedding_clip_unavailable(self) -> None:
        """Test embedding generation when CLIP service is unavailable."""
        mock_client = AsyncMock()
        mock_client.embed.side_effect = CLIPUnavailableError("Service down")

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (100, 100), color="yellow")

        with pytest.raises(CLIPUnavailableError):
            await service.generate_embedding(image)

    @pytest.mark.asyncio
    @patch("backend.services.reid_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_generate_embedding_generic_error(self, mock_sleep: AsyncMock) -> None:
        """Test embedding generation with generic error raises RuntimeError."""
        mock_client = AsyncMock()
        mock_client.embed.side_effect = ValueError("Some error")

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (100, 100), color="purple")

        with pytest.raises(RuntimeError) as exc_info:
            await service.generate_embedding(image)

        assert "Embedding generation failed" in str(exc_info.value)


# =============================================================================
# ReIdentificationService.store_embedding Tests
# =============================================================================


class TestStoreEmbedding:
    """Tests for ReIdentificationService.store_embedding method."""

    @pytest.mark.asyncio
    async def test_store_person_embedding(self) -> None:
        """Test storing a person embedding."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No existing data

        service = ReIdentificationService()
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_123",
        )

        await service.store_embedding(mock_redis, embedding)

        # Verify set was called with correct key and TTL
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "entity_embeddings:2025-12-25"
        # Mock is not a RedisClient instance, so code uses 'ex' (raw redis-py API)
        assert call_args.kwargs.get("ex") == EMBEDDING_TTL_SECONDS

        # Verify stored data structure
        stored_data = json.loads(call_args[0][1])
        assert "persons" in stored_data
        assert len(stored_data["persons"]) == 1
        assert stored_data["persons"][0]["detection_id"] == "det_123"

    @pytest.mark.asyncio
    async def test_store_vehicle_embedding(self) -> None:
        """Test storing a vehicle embedding."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=now,
            detection_id="det_456",
        )

        await service.store_embedding(mock_redis, embedding)

        stored_data = json.loads(mock_redis.set.call_args[0][1])
        assert "vehicles" in stored_data
        assert len(stored_data["vehicles"]) == 1
        assert stored_data["vehicles"][0]["detection_id"] == "det_456"

    @pytest.mark.asyncio
    async def test_store_embedding_appends_to_existing(self) -> None:
        """Test that new embeddings are appended to existing data."""
        existing_data = {
            "persons": [
                {
                    "entity_type": "person",
                    "embedding": [0.1] * 10,
                    "camera_id": "back_door",
                    "timestamp": "2025-12-25T11:00:00+00:00",
                    "detection_id": "det_old",
                    "attributes": {},
                }
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(existing_data)

        service = ReIdentificationService()
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.2] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_new",
        )

        await service.store_embedding(mock_redis, embedding)

        stored_data = json.loads(mock_redis.set.call_args[0][1])
        assert len(stored_data["persons"]) == 2
        assert stored_data["persons"][0]["detection_id"] == "det_old"
        assert stored_data["persons"][1]["detection_id"] == "det_new"

    @pytest.mark.asyncio
    async def test_store_embedding_redis_error(self) -> None:
        """Test that Redis errors are propagated."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis connection failed")

        service = ReIdentificationService()
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
        )

        with pytest.raises(Exception) as exc_info:
            await service.store_embedding(mock_redis, embedding)

        assert "Redis connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_embedding_uses_correct_ttl_parameter(self) -> None:
        """Test that store_embedding correctly passes TTL parameter.

        The code detects if the client is a RedisClient wrapper (uses 'expire')
        or raw redis-py client (uses 'ex'). With AsyncMock, it's not a RedisClient
        instance, so it uses 'ex'.
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_123",
        )

        await service.store_embedding(mock_redis, embedding)

        # Verify set was called with 'ex' (mock is not a RedisClient instance)
        mock_redis.set.assert_called_once()
        call_kwargs = mock_redis.set.call_args.kwargs

        # Should have 'ex' parameter (raw redis-py API for non-RedisClient)
        assert "ex" in call_kwargs
        assert call_kwargs["ex"] == EMBEDDING_TTL_SECONDS

        # Should NOT have 'expire' parameter (that's for RedisClient wrapper)
        assert "expire" not in call_kwargs

    @pytest.mark.asyncio
    async def test_store_embedding_ttl_value_correct(self) -> None:
        """Test that store_embedding sets correct TTL value (24 hours)."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        now = datetime.now(UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=now,
            detection_id="det_456",
        )

        await service.store_embedding(mock_redis, embedding)

        # Verify TTL is 24 hours (86400 seconds)
        # Mock is not a RedisClient instance, so code uses 'ex'
        call_kwargs = mock_redis.set.call_args.kwargs
        assert call_kwargs["ex"] == 86400
        assert call_kwargs["ex"] == EMBEDDING_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_store_embedding_works_with_raw_redis_client(self) -> None:
        """Test that store_embedding works with raw redis-py client.

        This test simulates the raw redis-py client behavior to ensure
        the method call signature is correct. Mock is not a RedisClient instance.
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        # Mock set to verify it's called correctly with 'ex' parameter
        async def mock_set(key: str, value: str, ex: int | None = None) -> bool:
            # This matches raw redis-py set() signature
            assert ex is not None, "ex parameter should be provided"
            assert ex == EMBEDDING_TTL_SECONDS
            return True

        mock_redis.set = AsyncMock(side_effect=mock_set)

        service = ReIdentificationService()
        now = datetime.now(UTC)
        embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.7] * 10,
            camera_id="driveway",
            timestamp=now,
            detection_id="det_789",
        )

        # Should not raise any exceptions
        await service.store_embedding(mock_redis, embedding)

        # Verify set was called
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_embedding_parameter_order(self) -> None:
        """Test that store_embedding passes parameters in correct order.

        Verifies positional and keyword arguments are correct.
        Mock is not a RedisClient instance, so code uses 'ex'.
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        now = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.2] * 10,
            camera_id="back_door",
            timestamp=now,
            detection_id="det_abc",
        )

        await service.store_embedding(mock_redis, embedding)

        # Verify call structure
        call_args = mock_redis.set.call_args
        positional_args = call_args[0]
        keyword_args = call_args[1]

        # First arg should be key
        assert positional_args[0] == "entity_embeddings:2025-06-15"

        # Second arg should be JSON data
        stored_data = json.loads(positional_args[1])
        assert "persons" in stored_data

        # TTL should be in keyword args as 'ex' (mock is not RedisClient instance)
        assert "ex" in keyword_args
        assert keyword_args["ex"] == EMBEDDING_TTL_SECONDS


# =============================================================================
# ReIdentificationService.find_matching_entities Tests
# =============================================================================


class TestFindMatchingEntities:
    """Tests for ReIdentificationService.find_matching_entities method."""

    @pytest.mark.asyncio
    async def test_find_matching_no_data(self) -> None:
        """Test finding matches when no data exists."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(mock_redis, embedding)

        assert matches == []

    @pytest.mark.asyncio
    async def test_find_matching_person(self) -> None:
        """Test finding matching persons."""
        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",
            timestamp=now - timedelta(minutes=5),
            detection_id="det_stored",
        )

        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        # Return same data for both today and yesterday keys
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        # Use same embedding for exact match
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis, query_embedding, entity_type="person", threshold=0.9
        )

        # May find match from both today and yesterday (same data), check at least 1
        assert len(matches) >= 1
        assert matches[0].entity.detection_id == "det_stored"
        assert matches[0].similarity >= 0.99  # Near-identical embeddings

    @pytest.mark.asyncio
    async def test_find_matching_excludes_detection(self) -> None:
        """Test that exclude_detection_id filters out the specified detection."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * EMBEDDING_DIMENSION,
                    camera_id="front_door",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_exclude",
                ).to_dict(),
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * EMBEDDING_DIMENSION,
                    camera_id="back_door",
                    timestamp=now - timedelta(minutes=10),
                    detection_id="det_include",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis,
            query_embedding,
            entity_type="person",
            threshold=0.9,
            exclude_detection_id="det_exclude",
        )

        # All matches should be for det_include (det_exclude is filtered)
        assert len(matches) >= 1
        for match in matches:
            assert match.entity.detection_id == "det_include"

    @pytest.mark.asyncio
    async def test_find_matching_respects_threshold(self) -> None:
        """Test that matches below threshold are filtered out."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * EMBEDDING_DIMENSION,  # Different from query
                    camera_id="front_door",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        # Use completely different embedding
        query_embedding = [1.0] * EMBEDDING_DIMENSION

        # High threshold should filter out the match
        matches = await service.find_matching_entities(
            mock_redis, query_embedding, entity_type="person", threshold=0.999
        )

        # Similarity between [0.1,...] and [1.0,...] is about 1.0 (same direction)
        # So this actually matches. Let's use opposite vectors instead
        query_embedding = [-0.1] * EMBEDDING_DIMENSION
        matches = await service.find_matching_entities(
            mock_redis, query_embedding, entity_type="person", threshold=0.5
        )

        # Opposite vectors have similarity -1, below threshold
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_find_matching_sorted_by_similarity(self) -> None:
        """Test that matches are sorted by similarity (highest first)."""
        now = datetime.now(UTC)
        # Use more distinct embeddings for clearer differentiation
        embedding_exact = [0.1, 0.2, 0.3] + [0.1] * (EMBEDDING_DIMENSION - 3)
        embedding_similar = [0.15, 0.25, 0.35] + [0.15] * (EMBEDDING_DIMENSION - 3)

        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=embedding_similar,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
                EntityEmbedding(
                    entity_type="person",
                    embedding=embedding_exact,
                    camera_id="camera_2",
                    timestamp=now - timedelta(minutes=10),
                    detection_id="det_2",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        # Only return data once to avoid duplicates
        call_count = [0]

        async def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(stored_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()
        query_embedding = embedding_exact  # Match det_2 exactly

        matches = await service.find_matching_entities(
            mock_redis, query_embedding, entity_type="person", threshold=0.9
        )

        assert len(matches) == 2
        # Exact match (det_2) should be first
        assert matches[0].entity.detection_id == "det_2"
        assert matches[0].similarity > matches[1].similarity

    @pytest.mark.asyncio
    async def test_find_matching_vehicle(self) -> None:
        """Test finding matching vehicles."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [],
            "vehicles": [
                EntityEmbedding(
                    entity_type="vehicle",
                    embedding=[0.5] * EMBEDDING_DIMENSION,
                    camera_id="garage",
                    timestamp=now - timedelta(minutes=30),
                    detection_id="det_car",
                    attributes={"color": "blue"},
                ).to_dict(),
            ],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        query_embedding = [0.5] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis, query_embedding, entity_type="vehicle", threshold=0.9
        )

        # May find duplicates from today/yesterday if same data returned
        assert len(matches) >= 1
        assert matches[0].entity.detection_id == "det_car"
        assert matches[0].entity.attributes == {"color": "blue"}

    @pytest.mark.asyncio
    async def test_find_matching_checks_multiple_dates(self) -> None:
        """Test that matching checks both today's and yesterday's data."""
        now = datetime.now(UTC)
        today_str = now.strftime("%Y-%m-%d")
        yesterday = now - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")

        today_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * EMBEDDING_DIMENSION,
                    camera_id="front_door",
                    timestamp=now - timedelta(hours=1),
                    detection_id="det_today",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        yesterday_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * EMBEDDING_DIMENSION,
                    camera_id="back_door",
                    timestamp=yesterday,
                    detection_id="det_yesterday",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()

        def get_side_effect(key: str) -> str | None:
            if today_str in key:
                return json.dumps(today_data)
            elif yesterday_str in key:
                return json.dumps(yesterday_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis, query_embedding, entity_type="person", threshold=0.9
        )

        # Should find both today's and yesterday's detections
        detection_ids = {m.entity.detection_id for m in matches}
        assert "det_today" in detection_ids
        assert "det_yesterday" in detection_ids

    @pytest.mark.asyncio
    async def test_find_matching_handles_redis_error(self) -> None:
        """Test that Redis errors return empty list."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")

        service = ReIdentificationService()

        matches = await service.find_matching_entities(
            mock_redis, [0.1] * EMBEDDING_DIMENSION, entity_type="person"
        )

        assert matches == []


# =============================================================================
# ReIdentificationService.get_entity_history Tests
# =============================================================================


class TestGetEntityHistory:
    """Tests for ReIdentificationService.get_entity_history method."""

    @pytest.mark.asyncio
    async def test_get_entity_history_no_data(self) -> None:
        """Test getting history when no data exists."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()

        history = await service.get_entity_history(mock_redis, "person")

        assert history == []

    @pytest.mark.asyncio
    async def test_get_entity_history_all_cameras(self) -> None:
        """Test getting history for all cameras."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * 10,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.2] * 10,
                    camera_id="camera_2",
                    timestamp=now - timedelta(minutes=10),
                    detection_id="det_2",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        # Only return data once to avoid duplicates from today/yesterday
        call_count = [0]

        def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(stored_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()

        history = await service.get_entity_history(mock_redis, "person")

        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_entity_history_filtered_by_camera(self) -> None:
        """Test getting history filtered by camera ID."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * 10,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.2] * 10,
                    camera_id="camera_2",
                    timestamp=now - timedelta(minutes=10),
                    detection_id="det_2",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        # Only return data once to avoid duplicates from today/yesterday
        call_count = [0]

        def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(stored_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()

        history = await service.get_entity_history(mock_redis, "person", camera_id="camera_1")

        assert len(history) == 1
        assert history[0].camera_id == "camera_1"

    @pytest.mark.asyncio
    async def test_get_entity_history_sorted_by_timestamp(self) -> None:
        """Test that history is sorted by timestamp (newest first)."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * 10,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=10),  # Older
                    detection_id="det_old",
                ).to_dict(),
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.2] * 10,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),  # Newer
                    detection_id="det_new",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        # Only return data once to avoid duplicates from today/yesterday
        call_count = [0]

        def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(stored_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()

        history = await service.get_entity_history(mock_redis, "person")

        assert len(history) == 2
        assert history[0].detection_id == "det_new"  # Newest first
        assert history[1].detection_id == "det_old"

    @pytest.mark.asyncio
    async def test_get_entity_history_vehicles(self) -> None:
        """Test getting vehicle history."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [],
            "vehicles": [
                EntityEmbedding(
                    entity_type="vehicle",
                    embedding=[0.5] * 10,
                    camera_id="garage",
                    timestamp=now - timedelta(hours=1),
                    detection_id="det_car",
                ).to_dict(),
            ],
        }

        mock_redis = AsyncMock()
        # Only return data once to avoid duplicates from today/yesterday
        call_count = [0]

        def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(stored_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()

        history = await service.get_entity_history(mock_redis, "vehicle")

        assert len(history) == 1
        assert history[0].entity_type == "vehicle"

    @pytest.mark.asyncio
    async def test_get_entity_history_handles_redis_error(self) -> None:
        """Test that Redis errors return empty list."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")

        service = ReIdentificationService()

        history = await service.get_entity_history(mock_redis, "person")

        assert history == []

    @pytest.mark.asyncio
    async def test_get_entity_history_handles_malformed_string_entity_data(
        self,
    ) -> None:
        """Test that malformed entity data (string instead of dict) is skipped.

        Regression test for: 'str' object has no attribute 'get' error.
        When Redis returns entity data where an entity is a string instead of a dict,
        the service should skip that entry and continue processing.
        """
        now = datetime.now(UTC)
        # Malformed data where one entity is a string instead of a dict
        stored_data = {
            "persons": [
                "malformed_string_entry",  # This is the problematic case
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * 10,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        call_count = [0]

        def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(stored_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()

        # Should not raise AttributeError: 'str' object has no attribute 'get'
        history = await service.get_entity_history(mock_redis, "person")

        # Should have only the valid entry
        assert len(history) == 1
        assert history[0].detection_id == "det_1"

    @pytest.mark.asyncio
    async def test_get_entity_history_handles_dict_from_redis_client_wrapper(
        self,
    ) -> None:
        """Test that pre-decoded dict from RedisClient wrapper is handled correctly.

        The RedisClient wrapper may return already-decoded JSON as a dict,
        which should not be passed through json.loads() again.
        """
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * 10,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        call_count = [0]

        def get_side_effect(key: str) -> dict | None:
            call_count[0] += 1
            if call_count[0] == 1:
                # Return dict directly (as RedisClient wrapper might)
                return stored_data
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()

        history = await service.get_entity_history(mock_redis, "person")

        assert len(history) == 1
        assert history[0].detection_id == "det_1"


# =============================================================================
# Malformed Redis Data Edge Cases Tests
# =============================================================================


class TestMalformedRedisDataHandling:
    """Tests for handling malformed Redis data in find_matching_entities."""

    @pytest.mark.asyncio
    async def test_find_matching_entities_handles_malformed_string_entity(
        self,
    ) -> None:
        """Test that malformed entity data (string instead of dict) is skipped in matching.

        Regression test for: 'str' object has no attribute 'get' error.
        """
        now = datetime.now(UTC)
        # Malformed data where one entity is a string instead of a dict
        stored_data = {
            "persons": [
                "malformed_string_entry",  # This is the problematic case
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.9] * 10,  # Similar embedding
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        call_count = [0]

        def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(stored_data)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()
        query_embedding = [0.9] * 10

        # Should not raise AttributeError
        matches = await service.find_matching_entities(
            mock_redis, query_embedding, "person", threshold=0.5
        )

        # Should find the valid entity
        assert len(matches) == 1
        assert matches[0].entity.detection_id == "det_1"

    @pytest.mark.asyncio
    async def test_find_matching_entities_handles_dict_from_redis_wrapper(
        self,
    ) -> None:
        """Test that pre-decoded dict from RedisClient wrapper is handled correctly."""
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.9] * 10,
                    camera_id="camera_1",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_1",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        call_count = [0]

        def get_side_effect(key: str) -> dict | None:
            call_count[0] += 1
            if call_count[0] == 1:
                # Return dict directly (as RedisClient wrapper might)
                return stored_data
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()
        query_embedding = [0.9] * 10

        matches = await service.find_matching_entities(
            mock_redis, query_embedding, "person", threshold=0.5
        )

        assert len(matches) == 1
        assert matches[0].entity.detection_id == "det_1"

    @pytest.mark.asyncio
    async def test_find_matching_entities_handles_non_dict_top_level_data(
        self,
    ) -> None:
        """Test that non-dict top-level data results in empty entity list."""
        mock_redis = AsyncMock()
        call_count = [0]

        def get_side_effect(key: str) -> str | None:
            call_count[0] += 1
            if call_count[0] == 1:
                # Return a string instead of dict structure
                return json.dumps("invalid_top_level_string")
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ReIdentificationService()
        query_embedding = [0.9] * 10

        # Should return empty list, not crash
        matches = await service.find_matching_entities(
            mock_redis, query_embedding, "person", threshold=0.5
        )

        assert matches == []


# =============================================================================
# Singleton Function Tests
# =============================================================================


class TestSingletonFunctions:
    """Tests for get_reid_service and reset_reid_service."""

    def test_get_reid_service_creates_singleton(self) -> None:
        """Test that get_reid_service creates a singleton."""
        reset_reid_service()

        service1 = get_reid_service()
        service2 = get_reid_service()

        assert service1 is service2
        reset_reid_service()

    def test_reset_reid_service_clears_singleton(self) -> None:
        """Test that reset_reid_service clears the singleton."""
        service1 = get_reid_service()
        reset_reid_service()
        service2 = get_reid_service()

        assert service1 is not service2
        reset_reid_service()


# =============================================================================
# Prompt Formatting Tests
# =============================================================================


class TestFormatEntityMatch:
    """Tests for format_entity_match function."""

    def test_format_match_seconds_ago(self) -> None:
        """Test formatting a match from seconds ago."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC) - timedelta(seconds=30),
            detection_id="det_123",
        )
        match = EntityMatch(entity=entity, similarity=0.95, time_gap_seconds=30)

        result = format_entity_match(match)

        assert "front_door" in result
        assert "30 seconds ago" in result
        assert "95%" in result

    def test_format_match_minutes_ago(self) -> None:
        """Test formatting a match from minutes ago."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="back_door",
            timestamp=datetime.now(UTC) - timedelta(minutes=15),
            detection_id="det_456",
        )
        match = EntityMatch(entity=entity, similarity=0.88, time_gap_seconds=15 * 60)

        result = format_entity_match(match)

        assert "back_door" in result
        assert "15 minutes ago" in result
        assert "88%" in result

    def test_format_match_hours_ago(self) -> None:
        """Test formatting a match from hours ago."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="garage",
            timestamp=datetime.now(UTC) - timedelta(hours=2, minutes=30),
            detection_id="det_789",
        )
        match = EntityMatch(entity=entity, similarity=0.92, time_gap_seconds=2.5 * 3600)

        result = format_entity_match(match)

        assert "garage" in result
        assert "2.5 hours ago" in result
        assert "92%" in result

    def test_format_match_with_clothing_attribute(self) -> None:
        """Test formatting a match with clothing attributes."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
            attributes={"clothing": "blue jacket"},
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=60)

        result = format_entity_match(match)

        assert "wearing blue jacket" in result

    def test_format_match_with_carrying_attribute(self) -> None:
        """Test formatting a match with carrying attribute."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
            attributes={"carrying": "backpack"},
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=60)

        result = format_entity_match(match)

        assert "carrying backpack" in result

    def test_format_match_with_vehicle_attributes(self) -> None:
        """Test formatting a vehicle match with color and type."""
        entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="driveway",
            timestamp=datetime.now(UTC),
            detection_id="det_car",
            attributes={"color": "red", "vehicle_type": "SUV"},
        )
        match = EntityMatch(entity=entity, similarity=0.85, time_gap_seconds=300)

        result = format_entity_match(match)

        assert "red" in result
        assert "SUV" in result


class TestFormatReidContext:
    """Tests for format_reid_context function."""

    def test_format_context_empty(self) -> None:
        """Test formatting empty matches."""
        result = format_reid_context({}, "person")

        assert "No person re-identification matches found" in result

    def test_format_context_with_matches(self) -> None:
        """Test formatting context with matches."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC) - timedelta(minutes=5),
            detection_id="det_stored",
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=300)

        matches_by_entity = {"det_query": [match]}

        result = format_reid_context(matches_by_entity, "person")

        assert "det_query" in result
        assert "1 time(s) before" in result
        assert "front_door" in result

    def test_format_context_limits_to_three_matches(self) -> None:
        """Test that context limits to top 3 matches."""
        matches = []
        for i in range(5):
            entity = EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 10,
                camera_id=f"camera_{i}",
                timestamp=datetime.now(UTC) - timedelta(minutes=i * 5),
                detection_id=f"det_{i}",
            )
            matches.append(
                EntityMatch(entity=entity, similarity=0.9 - i * 0.01, time_gap_seconds=i * 300)
            )

        matches_by_entity = {"det_query": matches}

        result = format_reid_context(matches_by_entity, "person")

        # Should only include cameras 0, 1, 2 (first 3)
        assert "camera_0" in result
        assert "camera_1" in result
        assert "camera_2" in result
        assert "camera_3" not in result
        assert "camera_4" not in result

    def test_format_context_empty_matches_list(self) -> None:
        """Test formatting with empty matches list."""
        matches_by_entity = {"det_query": []}

        result = format_reid_context(matches_by_entity, "person")

        assert "No person re-identification matches found" in result


class TestFormatFullReidContext:
    """Tests for format_full_reid_context function."""

    def test_format_full_context_no_matches(self) -> None:
        """Test formatting when no matches exist."""
        result = format_full_reid_context()

        assert "No entities matched with previous sightings" in result

    def test_format_full_context_only_persons(self) -> None:
        """Test formatting with only person matches."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC) - timedelta(minutes=5),
            detection_id="det_person",
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=300)

        result = format_full_reid_context(person_matches={"det_query": [match]})

        assert "Person Re-Identification" in result
        assert "Vehicle Re-Identification" not in result

    def test_format_full_context_only_vehicles(self) -> None:
        """Test formatting with only vehicle matches."""
        entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            detection_id="det_car",
        )
        match = EntityMatch(entity=entity, similarity=0.85, time_gap_seconds=3600)

        result = format_full_reid_context(vehicle_matches={"det_query": [match]})

        assert "Vehicle Re-Identification" in result
        assert "Person Re-Identification" not in result

    def test_format_full_context_both(self) -> None:
        """Test formatting with both person and vehicle matches."""
        person_entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC) - timedelta(minutes=5),
            detection_id="det_person",
        )
        person_match = EntityMatch(entity=person_entity, similarity=0.9, time_gap_seconds=300)

        vehicle_entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            detection_id="det_car",
        )
        vehicle_match = EntityMatch(entity=vehicle_entity, similarity=0.85, time_gap_seconds=3600)

        result = format_full_reid_context(
            person_matches={"det_p": [person_match]},
            vehicle_matches={"det_v": [vehicle_match]},
        )

        assert "Person Re-Identification" in result
        assert "Vehicle Re-Identification" in result


class TestFormatReidSummary:
    """Tests for format_reid_summary function."""

    def test_format_summary_no_matches(self) -> None:
        """Test summary when no matches exist."""
        result = format_reid_summary()

        assert "All entities appear to be new" in result

    def test_format_summary_only_persons(self) -> None:
        """Test summary with only person matches."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_person",
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=300)

        result = format_reid_summary(person_matches={"det1": [match], "det2": [match]})

        assert "2 person(s) seen before" in result

    def test_format_summary_only_vehicles(self) -> None:
        """Test summary with only vehicle matches."""
        entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=datetime.now(UTC),
            detection_id="det_car",
        )
        match = EntityMatch(entity=entity, similarity=0.85, time_gap_seconds=3600)

        result = format_reid_summary(vehicle_matches={"det1": [match]})

        assert "1 vehicle(s) seen before" in result

    def test_format_summary_both(self) -> None:
        """Test summary with both person and vehicle matches."""
        person_entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_person",
        )
        person_match = EntityMatch(entity=person_entity, similarity=0.9, time_gap_seconds=300)

        vehicle_entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=datetime.now(UTC),
            detection_id="det_car",
        )
        vehicle_match = EntityMatch(entity=vehicle_entity, similarity=0.85, time_gap_seconds=3600)

        result = format_reid_summary(
            person_matches={"det1": [person_match]},
            vehicle_matches={"det2": [vehicle_match], "det3": [vehicle_match]},
        )

        assert "1 person(s) seen before" in result
        assert "2 vehicle(s) seen before" in result

    def test_format_summary_empty_match_lists(self) -> None:
        """Test summary with empty match lists."""
        result = format_reid_summary(person_matches={"det1": []}, vehicle_matches={"det2": []})

        assert "All entities appear to be new" in result


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_embedding_ttl_seconds(self) -> None:
        """Test EMBEDDING_TTL_SECONDS is 24 hours."""
        assert EMBEDDING_TTL_SECONDS == 86400  # 24 * 60 * 60

    def test_default_similarity_threshold(self) -> None:
        """Test DEFAULT_SIMILARITY_THRESHOLD value."""
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.85

    def test_embedding_dimension(self) -> None:
        """Test EMBEDDING_DIMENSION is 768 for CLIP ViT-L."""
        assert EMBEDDING_DIMENSION == 768


# =============================================================================
# Rate Limiting Tests (NEM-1072)
# =============================================================================


class TestRateLimitingConfiguration:
    """Tests for rate limiting configuration in ReIdentificationService."""

    def test_service_has_max_concurrent_requests_attribute(self) -> None:
        """Test that service has configurable max_concurrent_requests."""
        service = ReIdentificationService()
        assert hasattr(service, "max_concurrent_requests")
        # Default should be a reasonable value
        assert service.max_concurrent_requests > 0

    def test_service_accepts_custom_max_concurrent_requests(self) -> None:
        """Test service can be initialized with custom concurrency limit."""
        service = ReIdentificationService(max_concurrent_requests=5)
        assert service.max_concurrent_requests == 5

    def test_service_has_semaphore_for_rate_limiting(self) -> None:
        """Test that service has an asyncio.Semaphore for rate limiting."""
        service = ReIdentificationService(max_concurrent_requests=3)
        assert hasattr(service, "_rate_limit_semaphore")
        # Semaphore should be initialized with the configured limit
        assert service._rate_limit_semaphore._value == 3


class TestRateLimitingBehavior:
    """Tests for rate limiting behavior in ReIdentificationService operations."""

    @pytest.mark.asyncio
    async def test_generate_embedding_respects_rate_limit(self) -> None:
        """Test that generate_embedding operations are rate limited."""
        import asyncio

        mock_client = AsyncMock()

        # Add a small delay to simulate processing time
        async def slow_embed(image: Image.Image) -> list[float]:
            await asyncio.sleep(0.1)
            return [0.1] * EMBEDDING_DIMENSION

        mock_client.embed.side_effect = slow_embed

        # Create service with max 2 concurrent requests
        service = ReIdentificationService(clip_client=mock_client, max_concurrent_requests=2)
        image = Image.new("RGB", (100, 100), color="red")

        # Launch 5 concurrent requests
        start_time = asyncio.get_event_loop().time()
        tasks = [service.generate_embedding(image) for _ in range(5)]
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        # With max 2 concurrent and 5 requests at 0.1s each:
        # First batch (2 concurrent): 0.1s
        # Second batch (2 concurrent): 0.1s
        # Third batch (1 remaining): 0.1s
        # Total minimum: 0.3s (without rate limiting it would be ~0.1s)
        elapsed = end_time - start_time
        assert elapsed >= 0.25, f"Rate limiting not effective, elapsed: {elapsed}s"

    @pytest.mark.asyncio
    async def test_store_embedding_respects_rate_limit(self) -> None:
        """Test that store_embedding operations are rate limited."""
        import asyncio

        mock_redis = AsyncMock()

        # Add delay to storage operation
        async def slow_set(*args: object, **kwargs: object) -> None:
            await asyncio.sleep(0.1)

        mock_redis.get.return_value = None
        mock_redis.set.side_effect = slow_set

        service = ReIdentificationService(max_concurrent_requests=2)
        now = datetime.now(UTC)

        # Create multiple embeddings
        embeddings = [
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 10,
                camera_id="front_door",
                timestamp=now,
                detection_id=f"det_{i}",
            )
            for i in range(5)
        ]

        start_time = asyncio.get_event_loop().time()
        tasks = [service.store_embedding(mock_redis, emb) for emb in embeddings]
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        elapsed = end_time - start_time
        # With rate limiting of 2, should take at least 0.25s for 5 operations
        assert elapsed >= 0.25, f"Rate limiting not effective, elapsed: {elapsed}s"

    @pytest.mark.asyncio
    async def test_find_matching_entities_respects_rate_limit(self) -> None:
        """Test that find_matching_entities operations are rate limited."""
        import asyncio

        mock_redis = AsyncMock()

        async def slow_get(key: str) -> str | None:
            await asyncio.sleep(0.1)
            return None

        mock_redis.get.side_effect = slow_get

        service = ReIdentificationService(max_concurrent_requests=2)

        start_time = asyncio.get_event_loop().time()
        tasks = [
            service.find_matching_entities(mock_redis, [0.1] * EMBEDDING_DIMENSION)
            for _ in range(4)
        ]
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        elapsed = end_time - start_time
        # With rate limiting of 2, should take at least 0.2s for 4 operations
        assert elapsed >= 0.15, f"Rate limiting not effective, elapsed: {elapsed}s"

    @pytest.mark.asyncio
    async def test_rate_limit_does_not_block_when_under_limit(self) -> None:
        """Test that requests proceed immediately when under the rate limit."""
        import asyncio

        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.1] * EMBEDDING_DIMENSION

        # High limit, should not block
        service = ReIdentificationService(clip_client=mock_client, max_concurrent_requests=100)
        image = Image.new("RGB", (100, 100), color="blue")

        start_time = asyncio.get_event_loop().time()
        tasks = [service.generate_embedding(image) for _ in range(5)]
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        elapsed = end_time - start_time
        # Should complete almost instantly since we're under the limit
        assert elapsed < 0.5, f"Rate limiting incorrectly blocking, elapsed: {elapsed}s"


class TestRateLimitingWithConfig:
    """Tests for rate limiting configuration from Settings."""

    def test_service_uses_settings_for_default_rate_limit(
        self, mock_get_settings_for_reid: MagicMock
    ) -> None:
        """Test that service uses Settings for default rate limit when not provided."""
        # Configure the autouse fixture's mock settings
        mock_get_settings_for_reid.reid_max_concurrent_requests = 10

        # Service created without explicit max_concurrent_requests should use settings
        service = ReIdentificationService()
        assert service.max_concurrent_requests == 10

    def test_explicit_max_concurrent_overrides_settings(self) -> None:
        """Test that explicit parameter overrides settings."""
        # Even if settings has a different value, explicit parameter takes precedence
        service = ReIdentificationService(max_concurrent_requests=7)
        assert service.max_concurrent_requests == 7


class TestRateLimitingEdgeCases:
    """Tests for rate limiting edge cases and error handling."""

    @pytest.mark.asyncio
    @patch("backend.services.reid_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_rate_limit_released_on_exception(self, mock_sleep: AsyncMock) -> None:
        """Test that semaphore is released even when operation raises exception."""
        import asyncio

        mock_client = AsyncMock()
        mock_client.embed.side_effect = RuntimeError("Test error")

        service = ReIdentificationService(clip_client=mock_client, max_concurrent_requests=1)
        image = Image.new("RGB", (100, 100), color="green")

        # First request should fail but release semaphore
        with pytest.raises(RuntimeError):
            await service.generate_embedding(image)

        # Second request should not be blocked (semaphore was released)
        mock_client.embed.side_effect = None
        mock_client.embed.return_value = [0.1] * EMBEDDING_DIMENSION

        # This should complete without hanging
        async with asyncio.timeout(1.0):
            result = await service.generate_embedding(image)
            assert len(result) == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_concurrent_operations_stay_within_limit(self) -> None:
        """Test that concurrent operations never exceed the configured limit."""
        import asyncio

        mock_client = AsyncMock()
        concurrent_count = 0
        max_observed_concurrent = 0
        lock = asyncio.Lock()

        async def tracking_embed(image: Image.Image) -> list[float]:
            nonlocal concurrent_count, max_observed_concurrent
            async with lock:
                concurrent_count += 1
                max_observed_concurrent = max(max_observed_concurrent, concurrent_count)
            await asyncio.sleep(0.05)  # Simulate work
            async with lock:
                concurrent_count -= 1
            return [0.1] * EMBEDDING_DIMENSION

        mock_client.embed.side_effect = tracking_embed

        service = ReIdentificationService(clip_client=mock_client, max_concurrent_requests=3)
        image = Image.new("RGB", (100, 100), color="yellow")

        # Launch many concurrent requests
        tasks = [service.generate_embedding(image) for _ in range(20)]
        await asyncio.gather(*tasks)

        # Should never have exceeded the limit
        assert max_observed_concurrent <= 3, (
            f"Exceeded rate limit: max concurrent was {max_observed_concurrent}"
        )


# =============================================================================
# Async Timeout and Retry Tests (NEM-1085)
# =============================================================================


class TestReIDTimeoutConfiguration:
    """Tests for ReID embedding timeout configuration."""

    def test_service_has_timeout_attribute(self) -> None:
        """Test that service has configurable embedding_timeout."""
        service = ReIdentificationService()
        assert hasattr(service, "_embedding_timeout")
        # Default should be a reasonable value (30 seconds)
        assert service._embedding_timeout > 0

    def test_service_accepts_custom_timeout(self) -> None:
        """Test service can be initialized with custom timeout."""
        service = ReIdentificationService(embedding_timeout=60.0)
        assert service._embedding_timeout == 60.0

    def test_service_uses_settings_for_default_timeout(
        self, mock_get_settings_for_reid: MagicMock
    ) -> None:
        """Test that service uses Settings for default timeout when not provided."""
        # Configure the autouse fixture's mock settings
        mock_get_settings_for_reid.reid_embedding_timeout = 45.0
        mock_get_settings_for_reid.reid_max_concurrent_requests = 10
        mock_get_settings_for_reid.reid_max_retries = 3

        service = ReIdentificationService()
        assert service._embedding_timeout == 45.0


class TestReIDRetryConfiguration:
    """Tests for ReID embedding retry configuration."""

    def test_service_has_max_retries_attribute(self) -> None:
        """Test that service has configurable max_retries."""
        service = ReIdentificationService()
        assert hasattr(service, "_max_retries")
        # Default should be 3 attempts
        assert service._max_retries == 3

    def test_service_accepts_custom_max_retries(self) -> None:
        """Test service can be initialized with custom max_retries."""
        service = ReIdentificationService(max_retries=5)
        assert service._max_retries == 5

    def test_service_uses_settings_for_default_max_retries(
        self, mock_get_settings_for_reid: MagicMock
    ) -> None:
        """Test that service uses Settings for default max_retries when not provided."""
        # Configure the autouse fixture's mock settings
        mock_get_settings_for_reid.reid_max_retries = 4
        mock_get_settings_for_reid.reid_embedding_timeout = 30.0
        mock_get_settings_for_reid.reid_max_concurrent_requests = 10

        service = ReIdentificationService()
        assert service._max_retries == 4


class TestReIDTimeoutBehavior:
    """Tests for ReID embedding timeout behavior."""

    @pytest.mark.asyncio
    async def test_generate_embedding_times_out(self) -> None:
        """Test that generate_embedding times out for slow operations."""
        import asyncio

        mock_client = AsyncMock()

        async def slow_embed(image: Image.Image) -> list[float]:
            await asyncio.sleep(0.5)  # Longer than 0.1s timeout
            return [0.1] * EMBEDDING_DIMENSION

        mock_client.embed.side_effect = slow_embed

        # Use very short timeout
        service = ReIdentificationService(
            clip_client=mock_client,
            embedding_timeout=0.1,
            max_retries=1,  # Only 1 attempt to fail fast
        )
        image = Image.new("RGB", (100, 100), color="red")

        with pytest.raises(RuntimeError) as exc_info:
            await service.generate_embedding(image)

        # Should mention timeout in the error
        assert (
            "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_completes_before_timeout(self) -> None:
        """Test that generate_embedding succeeds when operation is fast enough."""
        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.1] * EMBEDDING_DIMENSION

        # Use reasonable timeout
        service = ReIdentificationService(clip_client=mock_client, embedding_timeout=30.0)
        image = Image.new("RGB", (100, 100), color="green")

        embedding = await service.generate_embedding(image)

        assert len(embedding) == EMBEDDING_DIMENSION


class TestReIDRetryBehavior:
    """Tests for ReID embedding retry behavior with exponential backoff."""

    @pytest.mark.asyncio
    @patch("backend.services.reid_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_on_transient_error(self, mock_sleep: AsyncMock) -> None:
        """Test that transient errors trigger retry."""
        mock_client = AsyncMock()
        call_count = 0

        async def failing_then_succeeding(image: Image.Image) -> list[float]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary connection failure")
            return [0.1] * EMBEDDING_DIMENSION

        mock_client.embed.side_effect = failing_then_succeeding

        service = ReIdentificationService(
            clip_client=mock_client, max_retries=3, embedding_timeout=30.0
        )
        image = Image.new("RGB", (100, 100), color="blue")

        embedding = await service.generate_embedding(image)

        assert len(embedding) == EMBEDDING_DIMENSION
        assert call_count == 3  # 2 failures + 1 success
        # Verify sleep was called for backoff (2 retries = 2 sleeps)
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    @patch("backend.services.reid_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_exhausted_raises_error(self, mock_sleep: AsyncMock) -> None:
        """Test that error is raised when all retries are exhausted."""
        mock_client = AsyncMock()
        mock_client.embed.side_effect = ConnectionError("Persistent failure")

        service = ReIdentificationService(
            clip_client=mock_client, max_retries=3, embedding_timeout=30.0
        )
        image = Image.new("RGB", (100, 100), color="purple")

        with pytest.raises(RuntimeError) as exc_info:
            await service.generate_embedding(image)

        assert "failed" in str(exc_info.value).lower()
        # Should have tried 3 times
        assert mock_client.embed.call_count == 3
        # Should have slept between retries (2 sleeps for 3 attempts)
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_clip_unavailable_error(self) -> None:
        """Test that CLIPUnavailableError is not retried."""
        mock_client = AsyncMock()
        mock_client.embed.side_effect = CLIPUnavailableError("CLIP service down")

        service = ReIdentificationService(
            clip_client=mock_client, max_retries=3, embedding_timeout=30.0
        )
        image = Image.new("RGB", (100, 100), color="orange")

        with pytest.raises(CLIPUnavailableError):
            await service.generate_embedding(image)

        # Should not retry - only called once
        assert mock_client.embed.call_count == 1

    @pytest.mark.asyncio
    @patch("backend.services.reid_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_exponential_backoff_timing(self, mock_sleep: AsyncMock) -> None:
        """Test that retry uses exponential backoff (2^attempt seconds)."""
        mock_client = AsyncMock()
        mock_client.embed.side_effect = ConnectionError("Temporary failure")

        service = ReIdentificationService(
            clip_client=mock_client, max_retries=3, embedding_timeout=30.0
        )
        image = Image.new("RGB", (100, 100), color="cyan")

        try:
            await service.generate_embedding(image)
        except RuntimeError:
            pass

        # Should have 3 attempts
        assert mock_client.embed.call_count == 3

        # Verify exponential backoff delays were requested
        # Delay after 1st failure: 1 second (2^0)
        # Delay after 2nd failure: 2 seconds (2^1)
        assert mock_sleep.call_count == 2
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == 1.0, f"First delay should be 1s, got {sleep_calls[0]}"
        assert sleep_calls[1] == 2.0, f"Second delay should be 2s, got {sleep_calls[1]}"


class TestReIDRetryLogging:
    """Tests for retry logging behavior."""

    @pytest.mark.asyncio
    @patch("backend.services.reid_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_logs_warning(self, mock_sleep: AsyncMock) -> None:
        """Test that retry attempts are logged at warning level."""
        mock_client = AsyncMock()
        call_count = 0

        async def failing_then_succeeding(image: Image.Image) -> list[float]:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return [0.1] * EMBEDDING_DIMENSION

        mock_client.embed.side_effect = failing_then_succeeding

        service = ReIdentificationService(
            clip_client=mock_client, max_retries=3, embedding_timeout=30.0
        )
        image = Image.new("RGB", (100, 100), color="magenta")

        with patch("backend.services.reid_service.logger") as mock_logger:
            await service.generate_embedding(image)

            # Should have logged a warning for the retry
            mock_logger.warning.assert_called()
            # Check that the warning mentions retry
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any("retry" in call.lower() for call in warning_calls)


# =============================================================================
# Hybrid Storage Integration Tests (NEM-2499)
# =============================================================================


class TestHybridStorageInitialization:
    """Tests for ReIdentificationService initialization with hybrid_storage.

    NEM-2499: Update ReIdentificationService to Use Hybrid Storage.
    Phase 2.2 of the Hybrid Entity Storage Architecture epic.
    """

    def test_init_without_hybrid_storage(self) -> None:
        """Test initialization without providing hybrid_storage (backward compat)."""
        service = ReIdentificationService()
        assert service._hybrid_storage is None

    def test_init_with_hybrid_storage(self) -> None:
        """Test initialization with custom hybrid_storage."""
        mock_hybrid_storage = MagicMock()
        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        assert service._hybrid_storage is mock_hybrid_storage

    def test_hybrid_storage_with_all_parameters(self) -> None:
        """Test initialization with hybrid_storage and all other parameters."""
        mock_clip_client = MagicMock()
        mock_hybrid_storage = MagicMock()

        service = ReIdentificationService(
            clip_client=mock_clip_client,
            max_concurrent_requests=5,
            embedding_timeout=60.0,
            max_retries=5,
            hybrid_storage=mock_hybrid_storage,
        )

        assert service._clip_client is mock_clip_client
        assert service.max_concurrent_requests == 5
        assert service._embedding_timeout == 60.0
        assert service._max_retries == 5
        assert service._hybrid_storage is mock_hybrid_storage


class TestStoreEmbeddingWithHybridStorage:
    """Tests for store_embedding with hybrid storage and persist_to_postgres parameter.

    NEM-2499: Update ReIdentificationService to Use Hybrid Storage.
    """

    @pytest.mark.asyncio
    async def test_store_embedding_persist_to_postgres_false_redis_only(self) -> None:
        """Test storing embedding with persist_to_postgres=False (Redis only).

        When persist_to_postgres=False, embedding should only be stored in Redis.
        This preserves the existing Redis-only behavior.
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_123",
        )

        result = await service.store_embedding(mock_redis, embedding, persist_to_postgres=False)

        # Should return None (no entity UUID since not persisted to PostgreSQL)
        assert result is None
        # Should still store in Redis
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_embedding_persist_to_postgres_true_without_hybrid_storage(self) -> None:
        """Test storing embedding with persist_to_postgres=True but no hybrid_storage.

        When persist_to_postgres=True but hybrid_storage is not configured,
        should only store in Redis and return None (graceful degradation).
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        # No hybrid_storage configured
        service = ReIdentificationService()
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_456",
        )

        result = await service.store_embedding(mock_redis, embedding, persist_to_postgres=True)

        # Should return None (no hybrid_storage configured)
        assert result is None
        # Should still store in Redis
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_embedding_persist_to_postgres_true_with_hybrid_storage(self) -> None:
        """Test storing embedding with persist_to_postgres=True and hybrid_storage configured.

        When persist_to_postgres=True and hybrid_storage is configured,
        should store in both Redis and PostgreSQL via hybrid_storage.
        """
        from uuid import uuid4

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_hybrid_storage = AsyncMock()
        entity_uuid = uuid4()
        # Return (entity_id, is_new_entity)
        mock_hybrid_storage.store_detection_embedding.return_value = (entity_uuid, True)

        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_789",
            attributes={"clothing": "blue jacket"},
        )

        result = await service.store_embedding(mock_redis, embedding, persist_to_postgres=True)

        # Should return entity UUID from hybrid_storage
        assert result == entity_uuid

        # Should store in Redis
        mock_redis.set.assert_called_once()

        # Should call hybrid_storage.store_detection_embedding
        mock_hybrid_storage.store_detection_embedding.assert_called_once()
        call_kwargs = mock_hybrid_storage.store_detection_embedding.call_args.kwargs
        assert call_kwargs["entity_type"] == "person"
        assert call_kwargs["embedding"] == [0.1] * 10
        assert call_kwargs["camera_id"] == "front_door"
        assert call_kwargs["attributes"] == {"clothing": "blue jacket"}

    @pytest.mark.asyncio
    async def test_store_embedding_default_persist_to_postgres_is_true(self) -> None:
        """Test that persist_to_postgres defaults to True for hybrid storage.

        When hybrid_storage is configured and persist_to_postgres is not specified,
        it should default to True (store in both Redis and PostgreSQL).
        """
        from uuid import uuid4

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_hybrid_storage = AsyncMock()
        entity_uuid = uuid4()
        mock_hybrid_storage.store_detection_embedding.return_value = (entity_uuid, False)

        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=now,
            detection_id="det_vehicle",
        )

        # Call without persist_to_postgres (should default to True)
        result = await service.store_embedding(mock_redis, embedding)

        # Should return entity UUID (because hybrid_storage is configured)
        assert result == entity_uuid
        mock_hybrid_storage.store_detection_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_embedding_backward_compatibility_no_hybrid_storage(self) -> None:
        """Test that existing behavior is preserved when hybrid_storage is None.

        This ensures backward compatibility: when no hybrid_storage is configured,
        store_embedding() returns None just like the original implementation.
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()  # No hybrid_storage
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_compat",
        )

        # Original store_embedding returned None implicitly
        result = await service.store_embedding(mock_redis, embedding)

        assert result is None
        # Should still store in Redis as before
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_embedding_hybrid_storage_error_handled_gracefully(self) -> None:
        """Test that hybrid_storage errors are handled gracefully.

        If hybrid_storage.store_detection_embedding fails, Redis storage should
        still succeed and the error should be logged (not raised).
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_hybrid_storage = AsyncMock()
        mock_hybrid_storage.store_detection_embedding.side_effect = Exception("PostgreSQL error")

        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="det_error",
        )

        with patch("backend.services.reid_service.logger") as mock_logger:
            result = await service.store_embedding(mock_redis, embedding, persist_to_postgres=True)

            # Should return None due to error
            assert result is None
            # Should still store in Redis
            mock_redis.set.assert_called_once()
            # Should log warning about PostgreSQL failure
            mock_logger.warning.assert_called()


class TestFindMatchingEntitiesWithHybridStorage:
    """Tests for find_matching_entities with hybrid storage and include_historical parameter.

    NEM-2499: Update ReIdentificationService to Use Hybrid Storage.
    """

    @pytest.mark.asyncio
    async def test_find_matching_include_historical_false_redis_only(self) -> None:
        """Test finding matches with include_historical=False (Redis only).

        When include_historical=False, should only search Redis for recent
        entities (existing behavior preserved).
        """
        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",
            timestamp=now - timedelta(minutes=5),
            detection_id="det_redis",
        )
        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()  # No hybrid_storage
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis,
            query_embedding,
            entity_type="person",
            threshold=0.9,
            include_historical=False,
        )

        # Should find Redis match
        assert len(matches) >= 1
        assert matches[0].entity.detection_id == "det_redis"

    @pytest.mark.asyncio
    async def test_find_matching_include_historical_true_without_hybrid_storage(self) -> None:
        """Test finding matches with include_historical=True but no hybrid_storage.

        When include_historical=True but hybrid_storage is not configured,
        should fall back to Redis-only behavior (graceful degradation).
        """
        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",
            timestamp=now - timedelta(minutes=5),
            detection_id="det_fallback",
        )
        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        # No hybrid_storage configured
        service = ReIdentificationService()
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis,
            query_embedding,
            entity_type="person",
            threshold=0.9,
            include_historical=True,  # Ignored without hybrid_storage
        )

        # Should still find Redis match
        assert len(matches) >= 1
        assert matches[0].entity.detection_id == "det_fallback"

    @pytest.mark.asyncio
    async def test_find_matching_include_historical_true_with_hybrid_storage(self) -> None:
        """Test finding matches with include_historical=True and hybrid_storage configured.

        When include_historical=True and hybrid_storage is configured,
        should use hybrid_storage.find_matches() for combined Redis + PostgreSQL search.
        """
        from backend.services.hybrid_entity_storage import HybridEntityMatch

        mock_redis = AsyncMock()

        # Create mock hybrid matches
        mock_hybrid_match = MagicMock(spec=HybridEntityMatch)
        mock_hybrid_match.entity_id = "entity_uuid_1"
        mock_hybrid_match.entity_type = "person"
        mock_hybrid_match.embedding = [0.1] * EMBEDDING_DIMENSION
        mock_hybrid_match.camera_id = "front_door"
        mock_hybrid_match.timestamp = datetime.now(UTC) - timedelta(minutes=5)
        mock_hybrid_match.detection_id = "det_hybrid"
        mock_hybrid_match.attributes = {}
        mock_hybrid_match.similarity = 0.95
        mock_hybrid_match.time_gap_seconds = 300.0
        mock_hybrid_match.source = "postgresql"

        mock_hybrid_storage = AsyncMock()
        mock_hybrid_storage.find_matches.return_value = [mock_hybrid_match]

        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis,
            query_embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=True,
        )

        # Should call hybrid_storage.find_matches
        mock_hybrid_storage.find_matches.assert_called_once()
        call_kwargs = mock_hybrid_storage.find_matches.call_args.kwargs
        assert call_kwargs["embedding"] == query_embedding
        assert call_kwargs["entity_type"] == "person"
        assert call_kwargs["threshold"] == 0.85
        assert call_kwargs["include_historical"] is True

        # Should return converted matches
        assert len(matches) >= 1

    @pytest.mark.asyncio
    async def test_find_matching_default_include_historical_is_false(self) -> None:
        """Test that include_historical defaults to False (backward compat).

        When include_historical is not specified, should default to False
        for backward compatibility with existing Redis-only behavior.
        """
        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",
            timestamp=now - timedelta(minutes=5),
            detection_id="det_default",
        )
        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        mock_hybrid_storage = AsyncMock()
        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        # Call without include_historical (should default to False)
        matches = await service.find_matching_entities(
            mock_redis,
            query_embedding,
            entity_type="person",
            threshold=0.9,
        )

        # Should NOT call hybrid_storage.find_matches (include_historical=False)
        mock_hybrid_storage.find_matches.assert_not_called()

        # Should use Redis-only search
        assert len(matches) >= 1
        assert matches[0].entity.detection_id == "det_default"

    @pytest.mark.asyncio
    async def test_find_matching_hybrid_converts_results_to_entity_match(self) -> None:
        """Test that hybrid storage results are converted to EntityMatch objects.

        The method should convert HybridEntityMatch objects back to EntityMatch
        objects so that existing consumers of find_matching_entities() continue
        to work without modification.
        """
        from backend.services.hybrid_entity_storage import HybridEntityMatch

        mock_redis = AsyncMock()

        # Create mock hybrid match with all required fields
        now = datetime.now(UTC)
        mock_hybrid_match = MagicMock(spec=HybridEntityMatch)
        mock_hybrid_match.entity_id = "entity_uuid_1"
        mock_hybrid_match.entity_type = "person"
        mock_hybrid_match.embedding = [0.5] * EMBEDDING_DIMENSION
        mock_hybrid_match.camera_id = "back_door"
        mock_hybrid_match.timestamp = now - timedelta(hours=2)
        mock_hybrid_match.detection_id = "det_pg_123"
        mock_hybrid_match.attributes = {"clothing": "green hat"}
        mock_hybrid_match.similarity = 0.92
        mock_hybrid_match.time_gap_seconds = 7200.0
        mock_hybrid_match.source = "postgresql"

        mock_hybrid_storage = AsyncMock()
        mock_hybrid_storage.find_matches.return_value = [mock_hybrid_match]

        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        query_embedding = [0.5] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis,
            query_embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=True,
        )

        # Should return EntityMatch objects
        assert len(matches) == 1
        match = matches[0]
        assert isinstance(match, EntityMatch)
        assert match.similarity == 0.92
        assert match.time_gap_seconds == 7200.0
        assert match.entity.entity_type == "person"
        assert match.entity.camera_id == "back_door"
        assert match.entity.detection_id == "det_pg_123"
        assert match.entity.attributes == {"clothing": "green hat"}

    @pytest.mark.asyncio
    async def test_find_matching_exclude_detection_id_with_hybrid_storage(self) -> None:
        """Test that exclude_detection_id is passed to hybrid storage."""
        mock_redis = AsyncMock()

        mock_hybrid_storage = AsyncMock()
        mock_hybrid_storage.find_matches.return_value = []

        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        await service.find_matching_entities(
            mock_redis,
            query_embedding,
            entity_type="person",
            threshold=0.85,
            exclude_detection_id="det_exclude_me",
            include_historical=True,
        )

        # Should pass exclude_detection_id to hybrid_storage
        call_kwargs = mock_hybrid_storage.find_matches.call_args.kwargs
        assert call_kwargs["exclude_detection_id"] == "det_exclude_me"

    @pytest.mark.asyncio
    async def test_find_matching_backward_compatibility_no_hybrid_storage(self) -> None:
        """Test that existing behavior is preserved when hybrid_storage is None.

        This ensures backward compatibility: when no hybrid_storage is configured,
        find_matching_entities() works exactly like the original implementation.
        """
        now = datetime.now(UTC)
        stored_data = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * EMBEDDING_DIMENSION,
                    camera_id="front_door",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_compat",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()  # No hybrid_storage
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        matches = await service.find_matching_entities(
            mock_redis, query_embedding, entity_type="person", threshold=0.9
        )

        # Should find match just like before
        assert len(matches) >= 1
        assert matches[0].entity.detection_id == "det_compat"
        # Should be EntityMatch object
        assert isinstance(matches[0], EntityMatch)


class TestHybridStorageProperty:
    """Tests for hybrid_storage property access."""

    def test_hybrid_storage_property_returns_none_when_not_set(self) -> None:
        """Test that hybrid_storage returns None when not configured."""
        service = ReIdentificationService()
        assert service.hybrid_storage is None

    def test_hybrid_storage_property_returns_instance_when_set(self) -> None:
        """Test that hybrid_storage returns the configured instance."""
        mock_hybrid_storage = MagicMock()
        service = ReIdentificationService(hybrid_storage=mock_hybrid_storage)
        assert service.hybrid_storage is mock_hybrid_storage


# =============================================================================
# VQA Output Cleaning Tests
# =============================================================================


class TestCleanVqaOutput:
    """Tests for clean_vqa_output function.

    The clean_vqa_output function removes Florence-2 VQA artifacts from
    raw output text, including:
    - VQA> prefix and query text
    - <loc_N> location tokens (bounding box coordinates)
    """

    def test_clean_vqa_output_with_none_returns_none(self) -> None:
        """Test that None input returns None."""
        assert clean_vqa_output(None) is None

    def test_clean_vqa_output_with_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        assert clean_vqa_output("") is None

    def test_clean_vqa_output_with_whitespace_only_returns_none(self) -> None:
        """Test that whitespace-only string returns None."""
        assert clean_vqa_output("   ") is None

    def test_clean_vqa_output_removes_vqa_prefix(self) -> None:
        """Test that VQA> prefix and query text is removed."""
        raw = "VQA>person wearing<loc_71><loc_86>blue jacket"
        result = clean_vqa_output(raw)
        assert result == "blue jacket"
        assert "VQA>" not in result
        assert "person wearing" not in result

    def test_clean_vqa_output_removes_location_tokens(self) -> None:
        """Test that <loc_N> tokens are removed."""
        raw = "<loc_10><loc_20>backpack<loc_30><loc_40>"
        result = clean_vqa_output(raw)
        assert result == "backpack"
        assert "<loc_" not in result

    def test_clean_vqa_output_removes_multiple_location_tokens(self) -> None:
        """Test removing multiple location tokens with various numbers."""
        raw = "<loc_71><loc_86><loc_920><loc_916>red shirt, dark pants"
        result = clean_vqa_output(raw)
        assert result == "red shirt, dark pants"

    def test_clean_vqa_output_handles_query_with_only_artifacts(self) -> None:
        """Test that if cleaning leaves nothing, None is returned."""
        raw = "VQA>Is this person carrying anything<loc_1><loc_2>"
        result = clean_vqa_output(raw)
        assert result is None

    def test_clean_vqa_output_preserves_clean_text(self) -> None:
        """Test that clean text without artifacts is unchanged."""
        clean_text = "blue jacket, dark pants"
        result = clean_vqa_output(clean_text)
        assert result == "blue jacket, dark pants"

    def test_clean_vqa_output_normalizes_whitespace(self) -> None:
        """Test that extra whitespace is normalized."""
        raw = "<loc_10>  <loc_20>   backpack   "
        result = clean_vqa_output(raw)
        assert result == "backpack"

    def test_clean_vqa_output_complex_example(self) -> None:
        """Test a complex real-world example with all artifact types."""
        raw = "VQA>What is this person wearing<loc_100><loc_200><loc_300><loc_400>black hoodie and jeans"
        result = clean_vqa_output(raw)
        assert result == "black hoodie and jeans"

    def test_clean_vqa_output_partial_vqa_prefix(self) -> None:
        """Test handling of VQA prefix with query text containing angle brackets."""
        raw = "VQA>Is the person<loc_50>carrying a bag"
        result = clean_vqa_output(raw)
        # The pattern VQA>[^<]* will match "VQA>Is the person" and stop at <loc_50>
        assert "VQA>" not in result
        assert "carrying a bag" in result


class TestFormatEntityMatchWithVqaArtifacts:
    """Tests for format_entity_match handling of VQA artifacts in attributes."""

    def test_format_match_cleans_clothing_vqa_artifacts(self) -> None:
        """Test that VQA artifacts in clothing attribute are cleaned."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
            attributes={
                "clothing": "VQA>person wearing<loc_71><loc_86><loc_920><loc_916>blue jacket"
            },
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=60)

        result = format_entity_match(match)

        assert "wearing blue jacket" in result
        assert "VQA>" not in result
        assert "<loc_" not in result

    def test_format_match_cleans_carrying_vqa_artifacts(self) -> None:
        """Test that VQA artifacts in carrying attribute are cleaned."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
            attributes={
                "carrying": "VQA>Is this person carrying anything<loc_1><loc_2><loc_3><loc_4>backpack"
            },
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=60)

        result = format_entity_match(match)

        assert "carrying backpack" in result
        assert "VQA>" not in result
        assert "<loc_" not in result

    def test_format_match_cleans_color_vqa_artifacts(self) -> None:
        """Test that VQA artifacts in color attribute are cleaned."""
        entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="driveway",
            timestamp=datetime.now(UTC),
            detection_id="det_car",
            attributes={"color": "<loc_10><loc_20>red<loc_30><loc_40>"},
        )
        match = EntityMatch(entity=entity, similarity=0.85, time_gap_seconds=300)

        result = format_entity_match(match)

        assert "red" in result
        assert "<loc_" not in result

    def test_format_match_cleans_vehicle_type_vqa_artifacts(self) -> None:
        """Test that VQA artifacts in vehicle_type attribute are cleaned."""
        entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="driveway",
            timestamp=datetime.now(UTC),
            detection_id="det_car",
            attributes={"vehicle_type": "VQA>What type of vehicle<loc_5><loc_10>SUV"},
        )
        match = EntityMatch(entity=entity, similarity=0.85, time_gap_seconds=300)

        result = format_entity_match(match)

        assert "SUV" in result
        assert "VQA>" not in result
        assert "<loc_" not in result

    def test_format_match_omits_empty_attribute_after_cleaning(self) -> None:
        """Test that attributes with only artifacts are omitted after cleaning."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
            attributes={
                "clothing": "blue jacket",  # Clean
                "carrying": "VQA>Is carrying<loc_1><loc_2>",  # Only artifacts
            },
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=60)

        result = format_entity_match(match)

        # Should have clothing but not carrying (since it's empty after cleaning)
        assert "wearing blue jacket" in result
        assert "carrying" not in result

    def test_format_match_handles_all_clean_attributes(self) -> None:
        """Test that already-clean attributes are preserved."""
        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_123",
            attributes={"clothing": "red shirt", "carrying": "shopping bag"},
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=60)

        result = format_entity_match(match)

        assert "wearing red shirt" in result
        assert "carrying shopping bag" in result


# =============================================================================
# Re-ID Prometheus Metrics Tests (NEM-4140)
# =============================================================================


class TestReIDServiceMetrics:
    """Tests for Re-ID service Prometheus metrics instrumentation (NEM-4140)."""

    @pytest.mark.asyncio
    async def test_find_matching_entities_records_attempt_metric(self) -> None:
        """Test that find_matching_entities records a Re-ID attempt metric."""
        from unittest.mock import patch

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        embedding = [0.1] * EMBEDDING_DIMENSION

        with patch("backend.services.reid_service.record_reid_attempt") as mock_record_attempt:
            await service.find_matching_entities(
                mock_redis, embedding, entity_type="person", camera_id="test_cam"
            )

            mock_record_attempt.assert_called_once_with("person", "test_cam")

    @pytest.mark.asyncio
    async def test_find_matching_entities_records_attempt_with_unknown_camera(
        self,
    ) -> None:
        """Test that find_matching_entities uses 'unknown' when no camera_id provided."""
        from unittest.mock import patch

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        embedding = [0.1] * EMBEDDING_DIMENSION

        with patch("backend.services.reid_service.record_reid_attempt") as mock_record_attempt:
            await service.find_matching_entities(mock_redis, embedding, entity_type="vehicle")

            mock_record_attempt.assert_called_once_with("vehicle", "unknown")

    @pytest.mark.asyncio
    async def test_find_matching_entities_records_match_duration_metric(self) -> None:
        """Test that find_matching_entities records match duration metric."""
        from unittest.mock import patch

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        service = ReIdentificationService()
        embedding = [0.1] * EMBEDDING_DIMENSION

        with patch("backend.services.reid_service.observe_reid_match_duration") as mock_observe:
            await service.find_matching_entities(
                mock_redis, embedding, entity_type="person", camera_id="cam1"
            )

            # Should have been called with entity_type and some duration
            mock_observe.assert_called_once()
            call_args = mock_observe.call_args
            assert call_args[0][0] == "person"  # entity_type
            assert isinstance(call_args[0][1], float)  # duration_seconds
            assert call_args[0][1] >= 0  # Duration should be non-negative

    @pytest.mark.asyncio
    async def test_find_matching_entities_records_match_metrics_on_success(self) -> None:
        """Test that find_matching_entities records match metrics when matches found."""
        from unittest.mock import patch

        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",
            timestamp=now - timedelta(minutes=5),
            detection_id="det_stored",
        )

        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        with patch("backend.services.reid_service.record_reid_match") as mock_record_match:
            matches = await service.find_matching_entities(
                mock_redis,
                query_embedding,
                entity_type="person",
                threshold=0.9,
                camera_id="back_door",
            )

            # Should have matches
            assert len(matches) >= 1

            # record_reid_match should be called for each match
            assert mock_record_match.call_count >= 1
            # First call should be for the match from front_door camera
            mock_record_match.assert_any_call("person", "front_door")

    @pytest.mark.asyncio
    async def test_find_matching_entities_records_cross_camera_handoff(self) -> None:
        """Test that find_matching_entities records cross-camera handoff metrics."""
        from unittest.mock import patch

        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",  # Different from query camera
            timestamp=now - timedelta(minutes=5),
            detection_id="det_stored",
        )

        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        with patch("backend.services.reid_service.record_cross_camera_handoff") as mock_handoff:
            matches = await service.find_matching_entities(
                mock_redis,
                query_embedding,
                entity_type="person",
                threshold=0.9,
                camera_id="back_door",  # Different camera - should trigger handoff
            )

            # Should have matches
            assert len(matches) >= 1

            # Cross-camera handoff should be recorded
            assert mock_handoff.call_count >= 1
            mock_handoff.assert_any_call("front_door", "back_door", "person")

    @pytest.mark.asyncio
    async def test_find_matching_entities_no_handoff_same_camera(self) -> None:
        """Test that no cross-camera handoff is recorded for same camera matches."""
        from unittest.mock import patch

        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",  # Same as query camera
            timestamp=now - timedelta(minutes=5),
            detection_id="det_stored",
        )

        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        with patch("backend.services.reid_service.record_cross_camera_handoff") as mock_handoff:
            await service.find_matching_entities(
                mock_redis,
                query_embedding,
                entity_type="person",
                threshold=0.9,
                camera_id="front_door",  # Same camera - no handoff
            )

            # No cross-camera handoff should be recorded for same camera
            mock_handoff.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_matching_entities_no_handoff_unknown_camera(self) -> None:
        """Test that no cross-camera handoff is recorded when camera_id is unknown."""
        from unittest.mock import patch

        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * EMBEDDING_DIMENSION,
            camera_id="front_door",
            timestamp=now - timedelta(minutes=5),
            detection_id="det_stored",
        )

        stored_data = {"persons": [stored_embedding.to_dict()], "vehicles": []}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        query_embedding = [0.1] * EMBEDDING_DIMENSION

        with patch("backend.services.reid_service.record_cross_camera_handoff") as mock_handoff:
            # No camera_id provided - should use "unknown"
            await service.find_matching_entities(
                mock_redis,
                query_embedding,
                entity_type="person",
                threshold=0.9,
            )

            # No cross-camera handoff should be recorded when camera is unknown
            mock_handoff.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_matching_vehicle_records_metrics(self) -> None:
        """Test that vehicle matching also records metrics correctly."""
        from unittest.mock import patch

        now = datetime.now(UTC)
        stored_embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * EMBEDDING_DIMENSION,
            camera_id="garage_cam",
            timestamp=now - timedelta(minutes=2),
            detection_id="det_vehicle",
        )

        stored_data = {"persons": [], "vehicles": [stored_embedding.to_dict()]}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(stored_data)

        service = ReIdentificationService()
        query_embedding = [0.5] * EMBEDDING_DIMENSION

        with (
            patch("backend.services.reid_service.record_reid_attempt") as mock_attempt,
            patch("backend.services.reid_service.record_reid_match") as mock_match,
            patch("backend.services.reid_service.observe_reid_match_duration") as mock_duration,
            patch("backend.services.reid_service.record_cross_camera_handoff") as mock_handoff,
        ):
            await service.find_matching_entities(
                mock_redis,
                query_embedding,
                entity_type="vehicle",
                threshold=0.9,
                camera_id="driveway_cam",
            )

            # Verify all metrics are called with correct entity_type
            mock_attempt.assert_called_once_with("vehicle", "driveway_cam")
            mock_match.assert_any_call("vehicle", "garage_cam")
            mock_duration.assert_called_once()
            assert mock_duration.call_args[0][0] == "vehicle"
            mock_handoff.assert_any_call("garage_cam", "driveway_cam", "vehicle")
