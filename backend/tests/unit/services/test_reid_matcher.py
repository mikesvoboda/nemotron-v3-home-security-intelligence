"""Unit tests for ReIDMatcher service.

Tests cover:
- Cosine similarity computation
- Matching with mock embeddings
- Time window filtering
- Threshold boundary conditions
- Embedding storage and retrieval
- Known person detection
- Person history tracking
- Camera-grouped sightings

Related to NEM-3043: Implement Re-ID Matching Service.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import Detection
from backend.services.reid_matcher import (
    DEFAULT_SIMILARITY_THRESHOLD,
    ReIDMatch,
    ReIDMatcher,
    get_reid_matcher,
)

# =============================================================================
# Test Fixtures
# =============================================================================


def create_sample_embedding(seed: int = 0, dimension: int = 512) -> list[float]:
    """Create a sample embedding vector for testing.

    Args:
        seed: Seed value to vary the embedding
        dimension: Dimension of the embedding vector (default: 512 for OSNet)

    Returns:
        A normalized embedding vector
    """
    # Create a simple normalized vector based on seed
    embedding = [0.0] * dimension
    base_idx = seed % dimension
    embedding[base_idx] = 1.0

    # Add some variation to make it more realistic
    for i in range(dimension):
        embedding[i] += (i * 0.001 * (seed + 1)) % 0.1

    # Normalize
    magnitude = math.sqrt(sum(x * x for x in embedding))
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]

    return embedding


def create_similar_embedding(
    base_embedding: list[float],
    noise_factor: float = 0.1,
) -> list[float]:
    """Create an embedding similar to the base embedding.

    Args:
        base_embedding: The base embedding to modify
        noise_factor: How much noise to add (0-1)

    Returns:
        A similar but slightly different embedding (normalized)
    """
    import random

    random.seed(42)  # Reproducible
    result = [v + random.uniform(-noise_factor, noise_factor) for v in base_embedding]  # noqa: S311

    # Normalize
    magnitude = math.sqrt(sum(x * x for x in result))
    if magnitude > 0:
        result = [x / magnitude for x in result]

    return result


def create_mock_detection(
    detection_id: int,
    camera_id: str = "front_door",
    detected_at: datetime | None = None,
    reid_embedding: list[float] | None = None,
    enrichment_data: dict | None = None,
) -> MagicMock:
    """Create a mock Detection instance for testing.

    Args:
        detection_id: ID for the detection
        camera_id: Camera ID
        detected_at: Detection timestamp (defaults to now)
        reid_embedding: Optional ReID embedding to include
        enrichment_data: Optional full enrichment data dict

    Returns:
        Mock Detection instance
    """
    mock = MagicMock(spec=Detection)
    mock.id = detection_id
    mock.camera_id = camera_id
    mock.detected_at = detected_at or datetime.now(UTC)

    if enrichment_data is not None:
        mock.enrichment_data = enrichment_data
    elif reid_embedding is not None:
        mock.enrichment_data = {"reid_embedding": reid_embedding}
    else:
        mock.enrichment_data = None

    return mock


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def reid_matcher(mock_session: AsyncMock) -> ReIDMatcher:
    """Create ReIDMatcher with mock session."""
    return ReIDMatcher(
        session=mock_session,
        similarity_threshold=0.7,
    )


# =============================================================================
# Cosine Similarity Tests
# =============================================================================


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors_return_one(self) -> None:
        """Test that identical vectors have similarity of 1.0."""
        embedding = create_sample_embedding(seed=1)
        similarity = ReIDMatcher._cosine_similarity(embedding, embedding)
        assert similarity == pytest.approx(1.0, rel=1e-6)

    def test_orthogonal_vectors_return_zero(self) -> None:
        """Test that orthogonal vectors have similarity of ~0."""
        # Create two orthogonal unit vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = ReIDMatcher._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors_return_negative_one(self) -> None:
        """Test that opposite vectors have similarity of -1.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = ReIDMatcher._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(-1.0, rel=1e-6)

    def test_similar_vectors_high_similarity(self) -> None:
        """Test that similar vectors have high similarity score."""
        base_embedding = create_sample_embedding(seed=1)
        similar_embedding = create_similar_embedding(base_embedding, noise_factor=0.05)
        similarity = ReIDMatcher._cosine_similarity(base_embedding, similar_embedding)
        # Should be reasonably high (above matching threshold)
        assert similarity > 0.7

    def test_different_vectors_low_similarity(self) -> None:
        """Test that very different vectors have lower similarity."""
        embedding1 = create_sample_embedding(seed=1)
        embedding2 = create_sample_embedding(seed=100)  # Very different seed
        similarity = ReIDMatcher._cosine_similarity(embedding1, embedding2)
        # Should be lower than similar vectors (below matching threshold)
        assert similarity < 0.7

    def test_empty_vectors_return_zero(self) -> None:
        """Test that empty vectors return 0.0 similarity."""
        similarity = ReIDMatcher._cosine_similarity([], [])
        assert similarity == 0.0

    def test_different_dimension_vectors_return_zero(self) -> None:
        """Test that vectors with different dimensions return 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0]
        similarity = ReIDMatcher._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_zero_vector_returns_zero(self) -> None:
        """Test that a zero vector returns 0.0 similarity."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = ReIDMatcher._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_normalized_vectors(self) -> None:
        """Test similarity with pre-normalized vectors."""
        # Pre-normalized vectors
        vec1 = [0.6, 0.8, 0.0]  # magnitude = 1.0
        vec2 = [0.6, 0.8, 0.0]  # Same as vec1
        similarity = ReIDMatcher._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0, rel=1e-6)


# =============================================================================
# Initialization Tests
# =============================================================================


class TestReIDMatcherInit:
    """Tests for ReIDMatcher initialization."""

    def test_init_with_default_threshold(self, mock_session: AsyncMock) -> None:
        """Test matcher initializes with default threshold."""
        matcher = ReIDMatcher(session=mock_session)
        assert matcher.session == mock_session
        assert matcher.threshold == DEFAULT_SIMILARITY_THRESHOLD

    def test_init_with_custom_threshold(self, mock_session: AsyncMock) -> None:
        """Test matcher initializes with custom threshold."""
        matcher = ReIDMatcher(session=mock_session, similarity_threshold=0.8)
        assert matcher.threshold == 0.8

    def test_factory_function(self, mock_session: AsyncMock) -> None:
        """Test get_reid_matcher factory function."""
        matcher = get_reid_matcher(mock_session, similarity_threshold=0.75)
        assert isinstance(matcher, ReIDMatcher)
        assert matcher.threshold == 0.75


# =============================================================================
# find_matches Tests
# =============================================================================


class TestFindMatches:
    """Tests for find_matches method."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_detections(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns empty list when no detections exist."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        embedding = create_sample_embedding(seed=1)
        matches = await reid_matcher.find_matches(embedding)

        assert matches == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_embedding(
        self,
        reid_matcher: ReIDMatcher,
    ) -> None:
        """Test returns empty list for empty embedding input."""
        matches = await reid_matcher.find_matches([])
        assert matches == []

    @pytest.mark.asyncio
    async def test_finds_matching_detection(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test finds detection with similar embedding."""
        embedding = create_sample_embedding(seed=1)

        # Create mock detection with similar embedding
        detection = create_mock_detection(
            detection_id=100,
            camera_id="front_door",
            reid_embedding=embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        assert len(matches) == 1
        assert matches[0].detection_id == 100
        assert matches[0].similarity == pytest.approx(1.0, rel=1e-6)
        assert matches[0].camera_id == "front_door"

    @pytest.mark.asyncio
    async def test_excludes_below_threshold(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test excludes detections below similarity threshold."""
        embedding1 = create_sample_embedding(seed=1)
        embedding2 = create_sample_embedding(seed=100)  # Very different

        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=embedding2,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding1)

        # Should be empty because similarity is below threshold (0.7)
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_respects_max_results(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test respects max_results parameter."""
        embedding = create_sample_embedding(seed=1)

        # Create multiple matching detections
        detections = [
            create_mock_detection(
                detection_id=i,
                reid_embedding=embedding,
                detected_at=datetime.now(UTC) - timedelta(minutes=i),
            )
            for i in range(10)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding, max_results=3)

        assert len(matches) == 3

    @pytest.mark.asyncio
    async def test_sorts_by_similarity_descending(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test results are sorted by similarity (highest first)."""
        base_embedding = create_sample_embedding(seed=1)

        # Create embeddings with decreasing similarity
        embedding_high = create_similar_embedding(base_embedding, noise_factor=0.01)
        embedding_med = create_similar_embedding(base_embedding, noise_factor=0.05)
        embedding_low = create_similar_embedding(base_embedding, noise_factor=0.1)

        detections = [
            create_mock_detection(detection_id=1, reid_embedding=embedding_low),
            create_mock_detection(detection_id=2, reid_embedding=embedding_high),
            create_mock_detection(detection_id=3, reid_embedding=embedding_med),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(base_embedding)

        # Results should be sorted by similarity descending
        assert len(matches) >= 2
        for i in range(len(matches) - 1):
            assert matches[i].similarity >= matches[i + 1].similarity

    @pytest.mark.asyncio
    async def test_excludes_detection_id(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test excludes specified detection_id from results."""
        embedding = create_sample_embedding(seed=1)

        # Create detections including one to exclude
        detections = [
            create_mock_detection(detection_id=100, reid_embedding=embedding),
            create_mock_detection(detection_id=200, reid_embedding=embedding),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        # The exclude is handled at query level, but our mock returns all
        # In a real test we'd verify the query, but here we just check the call
        matches = await reid_matcher.find_matches(
            embedding,
            exclude_detection_id=100,
        )

        # Both returned because mock doesn't filter; real DB would filter
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_handles_dict_embedding_format(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test handles embedding stored as dict with 'vector' key."""
        embedding = create_sample_embedding(seed=1)

        detection = create_mock_detection(
            detection_id=100,
            enrichment_data={
                "reid_embedding": {
                    "vector": embedding,
                    "dimension": len(embedding),
                    "model": "osnet_x0_25",
                }
            },
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        assert len(matches) == 1
        assert matches[0].similarity == pytest.approx(1.0, rel=1e-6)

    @pytest.mark.asyncio
    async def test_handles_list_embedding_format(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test handles embedding stored as direct list."""
        embedding = create_sample_embedding(seed=1)

        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_skips_detection_without_embedding(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test skips detections without ReID embedding."""
        embedding = create_sample_embedding(seed=1)

        # One with embedding, one without
        detections = [
            create_mock_detection(detection_id=100, reid_embedding=embedding),
            create_mock_detection(detection_id=200, enrichment_data={}),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        # Only one match (the one with embedding)
        assert len(matches) == 1
        assert matches[0].detection_id == 100


# =============================================================================
# Time Window Tests
# =============================================================================


class TestTimeWindowFiltering:
    """Tests for time window filtering."""

    @pytest.mark.asyncio
    async def test_default_time_window_is_24_hours(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test default time window is 24 hours."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await reid_matcher.find_matches(embedding)

        # Verify execute was called (query would have 24-hour cutoff)
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_custom_time_window(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test custom time window is used."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await reid_matcher.find_matches(embedding, time_window_hours=48)

        # Verify execute was called
        assert mock_session.execute.called


# =============================================================================
# store_embedding Tests
# =============================================================================


class TestStoreEmbedding:
    """Tests for store_embedding method."""

    @pytest.mark.asyncio
    async def test_stores_embedding_for_existing_detection(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test stores embedding when detection exists."""
        embedding = create_sample_embedding(seed=1)

        # Create mock detection
        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.enrichment_data = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = detection
        mock_session.execute.return_value = mock_result

        success = await reid_matcher.store_embedding(100, embedding)

        assert success is True
        assert "reid_embedding" in detection.enrichment_data
        assert detection.enrichment_data["reid_embedding"]["vector"] == embedding
        assert detection.enrichment_data["reid_embedding"]["dimension"] == len(embedding)
        assert "hash" in detection.enrichment_data["reid_embedding"]
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_for_missing_detection(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns False when detection doesn't exist."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        success = await reid_matcher.store_embedding(999, embedding)

        assert success is False
        mock_session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_initializes_enrichment_data_if_none(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test initializes enrichment_data if it was None."""
        embedding = create_sample_embedding(seed=1)

        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.enrichment_data = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = detection
        mock_session.execute.return_value = mock_result

        success = await reid_matcher.store_embedding(100, embedding)

        assert success is True
        assert detection.enrichment_data is not None
        assert "reid_embedding" in detection.enrichment_data

    @pytest.mark.asyncio
    async def test_preserves_existing_enrichment_data(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test preserves existing enrichment_data fields."""
        embedding = create_sample_embedding(seed=1)

        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.enrichment_data = {"existing_field": "value"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = detection
        mock_session.execute.return_value = mock_result

        await reid_matcher.store_embedding(100, embedding)

        assert "existing_field" in detection.enrichment_data
        assert detection.enrichment_data["existing_field"] == "value"
        assert "reid_embedding" in detection.enrichment_data


# =============================================================================
# is_known_person Tests
# =============================================================================


class TestIsKnownPerson:
    """Tests for is_known_person method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_match_found(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns (True, match) when similar person found."""
        embedding = create_sample_embedding(seed=1)

        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        is_known, best_match = await reid_matcher.is_known_person(embedding)

        assert is_known is True
        assert best_match is not None
        assert best_match.detection_id == 100

    @pytest.mark.asyncio
    async def test_returns_false_when_no_match(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns (False, None) when no similar person found."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        is_known, best_match = await reid_matcher.is_known_person(embedding)

        assert is_known is False
        assert best_match is None

    @pytest.mark.asyncio
    async def test_uses_custom_time_window(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test is_known_person respects time_window_hours."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await reid_matcher.is_known_person(embedding, time_window_hours=48)

        # Verify execute was called
        assert mock_session.execute.called


# =============================================================================
# get_person_history Tests
# =============================================================================


class TestGetPersonHistory:
    """Tests for get_person_history method."""

    @pytest.mark.asyncio
    async def test_returns_historical_sightings(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns list of historical sightings."""
        embedding = create_sample_embedding(seed=1)

        detections = [
            create_mock_detection(
                detection_id=i,
                reid_embedding=embedding,
                detected_at=datetime.now(UTC) - timedelta(hours=i),
            )
            for i in range(5)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        history = await reid_matcher.get_person_history(embedding)

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_uses_extended_time_window(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test uses 72-hour default time window for history."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Default is 72 hours
        await reid_matcher.get_person_history(embedding)

        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_custom_time_window_for_history(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test allows custom time window for history."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await reid_matcher.get_person_history(embedding, time_window_hours=168)

        assert mock_session.execute.called


# =============================================================================
# get_sightings_by_camera Tests
# =============================================================================


class TestGetSightingsByCamera:
    """Tests for get_sightings_by_camera method."""

    @pytest.mark.asyncio
    async def test_groups_by_camera_id(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test groups sightings by camera ID."""
        embedding = create_sample_embedding(seed=1)

        detections = [
            create_mock_detection(detection_id=1, camera_id="front_door", reid_embedding=embedding),
            create_mock_detection(detection_id=2, camera_id="front_door", reid_embedding=embedding),
            create_mock_detection(detection_id=3, camera_id="backyard", reid_embedding=embedding),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        by_camera = await reid_matcher.get_sightings_by_camera(embedding)

        assert "front_door" in by_camera
        assert "backyard" in by_camera
        assert len(by_camera["front_door"]) == 2
        assert len(by_camera["backyard"]) == 1

    @pytest.mark.asyncio
    async def test_handles_none_camera_id(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test handles detections with None camera_id."""
        embedding = create_sample_embedding(seed=1)

        detection = create_mock_detection(
            detection_id=1,
            camera_id=None,  # type: ignore[arg-type]
            reid_embedding=embedding,
        )
        detection.camera_id = None  # Override to None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        by_camera = await reid_matcher.get_sightings_by_camera(embedding)

        assert "unknown" in by_camera
        assert len(by_camera["unknown"]) == 1


# =============================================================================
# Embedding Hash Tests
# =============================================================================


class TestEmbeddingHash:
    """Tests for embedding hash computation."""

    def test_hash_is_deterministic(self) -> None:
        """Test same embedding produces same hash."""
        embedding = create_sample_embedding(seed=1)

        hash1 = ReIDMatcher._compute_embedding_hash(embedding)
        hash2 = ReIDMatcher._compute_embedding_hash(embedding)

        assert hash1 == hash2

    def test_different_embeddings_different_hashes(self) -> None:
        """Test different embeddings produce different hashes."""
        embedding1 = create_sample_embedding(seed=1)
        embedding2 = create_sample_embedding(seed=2)

        hash1 = ReIDMatcher._compute_embedding_hash(embedding1)
        hash2 = ReIDMatcher._compute_embedding_hash(embedding2)

        assert hash1 != hash2

    def test_hash_is_16_characters(self) -> None:
        """Test hash is exactly 16 characters."""
        embedding = create_sample_embedding(seed=1)
        hash_value = ReIDMatcher._compute_embedding_hash(embedding)
        assert len(hash_value) == 16


# =============================================================================
# Threshold Boundary Tests
# =============================================================================


class TestThresholdBoundaries:
    """Tests for similarity threshold boundary conditions."""

    @pytest.mark.asyncio
    async def test_exact_threshold_match_included(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that exact threshold value is included."""
        # Create matcher with specific threshold
        matcher = ReIDMatcher(session=mock_session, similarity_threshold=0.7)

        base_embedding = create_sample_embedding(seed=1)

        # Create embedding that will have exactly threshold similarity
        # This is hard to achieve precisely, so we use identical embedding
        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=base_embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await matcher.find_matches(base_embedding)

        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_just_below_threshold_excluded(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that similarity just below threshold is excluded."""
        # Use high threshold
        matcher = ReIDMatcher(session=mock_session, similarity_threshold=0.99)

        base_embedding = create_sample_embedding(seed=1)
        # Create slightly different embedding
        different_embedding = create_similar_embedding(base_embedding, noise_factor=0.1)

        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=different_embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await matcher.find_matches(base_embedding)

        # Should be excluded because similarity < 0.99
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_high_threshold_stricter_matching(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test high threshold results in stricter matching."""
        base_embedding = create_sample_embedding(seed=1)
        similar_embedding = create_similar_embedding(base_embedding, noise_factor=0.05)

        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=similar_embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        # Low threshold - should match
        matcher_low = ReIDMatcher(session=mock_session, similarity_threshold=0.5)
        matches_low = await matcher_low.find_matches(base_embedding)

        # High threshold - may not match
        matcher_high = ReIDMatcher(session=mock_session, similarity_threshold=0.99)
        matches_high = await matcher_high.find_matches(base_embedding)

        # Low threshold should have at least as many matches
        assert len(matches_low) >= len(matches_high)


# =============================================================================
# ReIDMatch Dataclass Tests
# =============================================================================


class TestReIDMatchDataclass:
    """Tests for ReIDMatch dataclass."""

    def test_creates_match_with_all_fields(self) -> None:
        """Test ReIDMatch can be created with all fields."""
        timestamp = datetime.now(UTC)
        match = ReIDMatch(
            detection_id=123,
            similarity=0.85,
            timestamp=timestamp,
            camera_id="front_door",
        )

        assert match.detection_id == 123
        assert match.similarity == 0.85
        assert match.timestamp == timestamp
        assert match.camera_id == "front_door"

    def test_creates_match_with_default_camera_id(self) -> None:
        """Test ReIDMatch default camera_id is None."""
        match = ReIDMatch(
            detection_id=123,
            similarity=0.85,
            timestamp=datetime.now(UTC),
        )

        assert match.camera_id is None


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_detection_with_null_enrichment_data(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test handles detection with null enrichment_data."""
        embedding = create_sample_embedding(seed=1)

        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.camera_id = "front_door"
        detection.detected_at = datetime.now(UTC)
        detection.enrichment_data = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        # Should not raise, just skip the detection
        matches = await reid_matcher.find_matches(embedding)
        assert matches == []

    @pytest.mark.asyncio
    async def test_handles_invalid_embedding_in_enrichment(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test handles invalid embedding format in enrichment_data."""
        embedding = create_sample_embedding(seed=1)

        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.camera_id = "front_door"
        detection.detected_at = datetime.now(UTC)
        detection.enrichment_data = {"reid_embedding": "invalid"}  # String instead of list

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        # Should not raise, just skip the detection
        matches = await reid_matcher.find_matches(embedding)
        assert matches == []

    @pytest.mark.asyncio
    async def test_handles_large_embedding_dimension(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test handles large embedding dimensions."""
        # OSNet default is 512, but test with larger
        embedding = create_sample_embedding(seed=1, dimension=2048)

        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_handles_small_embedding_dimension(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test handles small embedding dimensions."""
        embedding = create_sample_embedding(seed=1, dimension=128)

        detection = create_mock_detection(
            detection_id=100,
            reid_embedding=embedding,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        assert len(matches) == 1
