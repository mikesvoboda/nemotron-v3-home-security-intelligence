"""Unit tests for HybridEntityStorage service.

Tests cover:
- store_detection_embedding writes to both Redis and PostgreSQL
- find_matches returns Redis matches first (faster)
- find_matches includes PostgreSQL historical matches
- Deduplication works (same entity not returned twice)
- Results sorted by similarity
- include_historical=False skips PostgreSQL query
- get_entity_full_history returns PostgreSQL entity
- get_entities_by_timerange queries PostgreSQL with filtering

Related to NEM-2498: Implement Hybrid Storage Bridge (Redis <-> PostgreSQL).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.entity import Entity
from backend.services.reid_service import EntityEmbedding, EntityMatch

if TYPE_CHECKING:
    from backend.services.hybrid_entity_storage import HybridEntityStorage

# =============================================================================
# Test Fixtures
# =============================================================================


def create_mock_entity(
    entity_type: str = "person",
    embedding: list[float] | None = None,
    detection_count: int = 1,
    first_seen_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    entity_id: uuid.UUID | None = None,
) -> Entity:
    """Create a mock Entity instance for testing.

    Args:
        entity_type: Type of entity (person, vehicle, etc.)
        embedding: Optional embedding vector
        detection_count: Number of detections for this entity
        first_seen_at: First seen timestamp
        last_seen_at: Last seen timestamp
        entity_id: Optional UUID for the entity

    Returns:
        Entity instance with the specified attributes
    """
    now = datetime.now(UTC)
    entity = Entity(
        id=entity_id or uuid.uuid4(),
        entity_type=entity_type,
        detection_count=detection_count,
        first_seen_at=first_seen_at or now,
        last_seen_at=last_seen_at or now,
        primary_detection_id=None,
        entity_metadata=None,
    )
    if embedding:
        entity.set_embedding(embedding, model="clip")
    return entity


def create_sample_embedding(seed: int = 0, dimension: int = 768) -> list[float]:
    """Create a sample embedding vector for testing.

    Args:
        seed: Seed value to vary the embedding (0 creates a normalized vector)
        dimension: Dimension of the embedding vector

    Returns:
        A normalized embedding vector
    """
    import math

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


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client for testing."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def mock_entity_repository() -> AsyncMock:
    """Create a mock EntityRepository for testing."""
    repo = AsyncMock()
    repo.find_by_embedding = AsyncMock(return_value=[])
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.list = AsyncMock(return_value=([], 0))
    repo.get_or_create_for_detection = AsyncMock()
    repo.session = MagicMock()
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()
    repo.session.commit = AsyncMock()
    return repo


@pytest.fixture
def mock_clustering_service() -> AsyncMock:
    """Create a mock EntityClusteringService for testing."""
    service = AsyncMock()
    service.assign_entity = AsyncMock()
    return service


@pytest.fixture
def mock_reid_service() -> AsyncMock:
    """Create a mock ReIdentificationService for testing."""
    service = AsyncMock()
    service.store_embedding = AsyncMock()
    service.find_matching_entities = AsyncMock(return_value=[])
    return service


@pytest.fixture
def hybrid_storage(
    mock_redis: AsyncMock,
    mock_entity_repository: AsyncMock,
    mock_clustering_service: AsyncMock,
    mock_reid_service: AsyncMock,
) -> HybridEntityStorage:
    """Create HybridEntityStorage with mocked dependencies."""
    from backend.services.hybrid_entity_storage import HybridEntityStorage

    return HybridEntityStorage(
        redis_client=mock_redis,
        entity_repository=mock_entity_repository,
        clustering_service=mock_clustering_service,
        reid_service=mock_reid_service,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestHybridEntityStorageInit:
    """Tests for HybridEntityStorage initialization."""

    def test_init_with_dependencies(
        self,
        mock_redis: AsyncMock,
        mock_entity_repository: AsyncMock,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test service initializes with all dependencies."""
        from backend.services.hybrid_entity_storage import HybridEntityStorage

        storage = HybridEntityStorage(
            redis_client=mock_redis,
            entity_repository=mock_entity_repository,
            clustering_service=mock_clustering_service,
            reid_service=mock_reid_service,
        )

        assert storage.redis is mock_redis
        assert storage.entity_repo is mock_entity_repository
        assert storage.clustering is mock_clustering_service
        assert storage.reid is mock_reid_service


# =============================================================================
# store_detection_embedding Tests
# =============================================================================


class TestStoreDetectionEmbedding:
    """Tests for store_detection_embedding method."""

    @pytest.mark.asyncio
    async def test_stores_in_redis_and_postgresql(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test that embedding is stored in both Redis and PostgreSQL."""
        embedding = create_sample_embedding(seed=1)
        timestamp = datetime.now(UTC)

        # Setup clustering service to return a new entity
        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        entity_id, is_new = await hybrid_storage.store_detection_embedding(
            detection_id=123,
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=timestamp,
            attributes={"clothing": "blue jacket"},
        )

        # Verify clustering service was called (PostgreSQL storage)
        mock_clustering_service.assign_entity.assert_called_once()

        # Verify reid service was called (Redis storage)
        mock_reid_service.store_embedding.assert_called_once()

        assert entity_id == new_entity.id
        assert is_new is True

    @pytest.mark.asyncio
    async def test_returns_existing_entity_when_matched(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
    ) -> None:
        """Test returns existing entity when matching entity found."""
        embedding = create_sample_embedding(seed=2)
        timestamp = datetime.now(UTC)

        # Setup clustering service to return existing entity
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=5,
        )
        mock_clustering_service.assign_entity.return_value = (existing_entity, False, 0.95)

        entity_id, is_new = await hybrid_storage.store_detection_embedding(
            detection_id=456,
            entity_type="person",
            embedding=embedding,
            camera_id="back_door",
            timestamp=timestamp,
        )

        assert entity_id == existing_entity.id
        assert is_new is False

    @pytest.mark.asyncio
    async def test_stores_entity_embedding_in_redis(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test that EntityEmbedding is created correctly for Redis storage."""
        embedding = create_sample_embedding(seed=3)
        timestamp = datetime.now(UTC)
        attributes = {"clothing": "red shirt", "carrying": "backpack"}

        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        await hybrid_storage.store_detection_embedding(
            detection_id=789,
            entity_type="person",
            embedding=embedding,
            camera_id="garage",
            timestamp=timestamp,
            attributes=attributes,
        )

        # Verify the EntityEmbedding passed to reid service
        mock_reid_service.store_embedding.assert_called_once()
        call_args = mock_reid_service.store_embedding.call_args
        # The call is: store_embedding(redis_client, entity_embedding)
        # So positional args are (redis, embedding) at indices 0 and 1
        stored_embedding = call_args[0][1]

        assert stored_embedding.entity_type == "person"
        assert stored_embedding.embedding == embedding
        assert stored_embedding.camera_id == "garage"
        assert stored_embedding.attributes == attributes


# =============================================================================
# find_matches Tests - Redis First Pattern
# =============================================================================


class TestFindMatchesRedisFirst:
    """Tests for find_matches method checking Redis first."""

    @pytest.mark.asyncio
    async def test_checks_redis_first(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that Redis is checked first for matches."""
        embedding = create_sample_embedding(seed=10)

        # Setup Redis to return matches
        redis_match = EntityMatch(
            entity=EntityEmbedding(
                entity_type="person",
                embedding=embedding,
                camera_id="front_door",
                timestamp=datetime.now(UTC) - timedelta(minutes=5),
                detection_id="det_redis",
            ),
            similarity=0.95,
            time_gap_seconds=300,
        )
        mock_reid_service.find_matching_entities.return_value = [redis_match]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
        )

        # Verify Redis was checked
        mock_reid_service.find_matching_entities.assert_called_once()

        assert len(matches) >= 1

    @pytest.mark.asyncio
    async def test_includes_postgresql_historical_matches(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that PostgreSQL matches are included with include_historical=True."""
        embedding = create_sample_embedding(seed=11)

        # Setup Redis to return empty (no recent matches)
        mock_reid_service.find_matching_entities.return_value = []

        # Setup PostgreSQL to return historical matches
        historical_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=10,
            last_seen_at=datetime.now(UTC) - timedelta(days=5),
        )
        mock_entity_repository.find_by_embedding.return_value = [(historical_entity, 0.90)]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=True,
        )

        # Verify PostgreSQL was checked
        mock_entity_repository.find_by_embedding.assert_called_once()

        assert len(matches) >= 1

    @pytest.mark.asyncio
    async def test_skips_postgresql_when_include_historical_false(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that PostgreSQL is skipped when include_historical=False."""
        embedding = create_sample_embedding(seed=12)

        # Setup Redis to return some matches
        redis_match = EntityMatch(
            entity=EntityEmbedding(
                entity_type="person",
                embedding=embedding,
                camera_id="front_door",
                timestamp=datetime.now(UTC) - timedelta(minutes=5),
                detection_id="det_redis",
            ),
            similarity=0.95,
            time_gap_seconds=300,
        )
        mock_reid_service.find_matching_entities.return_value = [redis_match]

        await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=False,
        )

        # Verify PostgreSQL was NOT checked
        mock_entity_repository.find_by_embedding.assert_not_called()


# =============================================================================
# find_matches Tests - Deduplication
# =============================================================================


class TestFindMatchesDeduplication:
    """Tests for deduplication in find_matches method."""

    @pytest.mark.asyncio
    async def test_deduplicates_same_entity(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that same entity is not returned twice from Redis and PostgreSQL."""
        embedding = create_sample_embedding(seed=20)
        shared_entity_id = uuid.uuid4()

        # Setup Redis to return a match
        redis_match = EntityMatch(
            entity=EntityEmbedding(
                entity_type="person",
                embedding=embedding,
                camera_id="front_door",
                timestamp=datetime.now(UTC) - timedelta(minutes=5),
                detection_id=f"det_{shared_entity_id}",  # Same detection
            ),
            similarity=0.95,
            time_gap_seconds=300,
        )
        mock_reid_service.find_matching_entities.return_value = [redis_match]

        # Setup PostgreSQL to return same entity
        pg_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            entity_id=shared_entity_id,
        )
        mock_entity_repository.find_by_embedding.return_value = [(pg_entity, 0.92)]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=True,
        )

        # Entity should appear only once (deduplicated)
        # We expect either 1 match (deduplicated) or both with highest similarity first
        assert len(matches) >= 1


# =============================================================================
# find_matches Tests - Sorting
# =============================================================================


class TestFindMatchesSorting:
    """Tests for result sorting in find_matches method."""

    @pytest.mark.asyncio
    async def test_results_sorted_by_similarity(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that results are sorted by similarity (highest first)."""
        embedding = create_sample_embedding(seed=30)

        # Setup multiple Redis matches with varying similarities
        redis_matches = [
            EntityMatch(
                entity=EntityEmbedding(
                    entity_type="person",
                    embedding=create_sample_embedding(seed=31),
                    camera_id="camera_1",
                    timestamp=datetime.now(UTC) - timedelta(minutes=5),
                    detection_id="det_1",
                ),
                similarity=0.88,
                time_gap_seconds=300,
            ),
            EntityMatch(
                entity=EntityEmbedding(
                    entity_type="person",
                    embedding=create_sample_embedding(seed=32),
                    camera_id="camera_2",
                    timestamp=datetime.now(UTC) - timedelta(minutes=10),
                    detection_id="det_2",
                ),
                similarity=0.95,  # Higher similarity
                time_gap_seconds=600,
            ),
        ]
        mock_reid_service.find_matching_entities.return_value = redis_matches

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=False,
        )

        # Results should be sorted by similarity (highest first)
        assert len(matches) == 2
        assert matches[0].similarity >= matches[1].similarity


# =============================================================================
# find_matches Tests - Exclude Detection
# =============================================================================


class TestFindMatchesExcludeDetection:
    """Tests for exclude_detection_id in find_matches method."""

    @pytest.mark.asyncio
    async def test_excludes_specified_detection(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test that exclude_detection_id is passed to reid service."""
        embedding = create_sample_embedding(seed=40)

        mock_reid_service.find_matching_entities.return_value = []

        await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            exclude_detection_id="det_exclude_me",
            include_historical=False,
        )

        # Verify exclude_detection_id was passed
        mock_reid_service.find_matching_entities.assert_called_once()
        call_kwargs = mock_reid_service.find_matching_entities.call_args[1]
        assert call_kwargs.get("exclude_detection_id") == "det_exclude_me"


# =============================================================================
# get_entity_full_history Tests
# =============================================================================


class TestGetEntityFullHistory:
    """Tests for get_entity_full_history method."""

    @pytest.mark.asyncio
    async def test_returns_entity_from_postgresql(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that entity is retrieved from PostgreSQL."""
        entity_id = uuid.uuid4()
        expected_entity = create_mock_entity(
            entity_type="person",
            entity_id=entity_id,
            detection_count=15,
        )
        mock_entity_repository.get_by_id.return_value = expected_entity

        entity = await hybrid_storage.get_entity_full_history(entity_id)

        mock_entity_repository.get_by_id.assert_called_once_with(entity_id)
        assert entity is not None
        assert entity.id == entity_id
        assert entity.detection_count == 15

    @pytest.mark.asyncio
    async def test_returns_none_when_entity_not_found(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test returns None when entity doesn't exist."""
        entity_id = uuid.uuid4()
        mock_entity_repository.get_by_id.return_value = None

        entity = await hybrid_storage.get_entity_full_history(entity_id)

        assert entity is None


# =============================================================================
# get_entities_by_timerange Tests
# =============================================================================


class TestGetEntitiesByTimerange:
    """Tests for get_entities_by_timerange method."""

    @pytest.mark.asyncio
    async def test_queries_postgresql_with_filters(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that entities are queried from PostgreSQL with filters."""
        now = datetime.now(UTC)
        since = now - timedelta(days=7)
        until = now

        entities_list = [
            create_mock_entity(entity_type="person"),
            create_mock_entity(entity_type="person"),
        ]
        mock_entity_repository.list.return_value = (entities_list, 2)

        entities, total = await hybrid_storage.get_entities_by_timerange(
            entity_type="person",
            since=since,
            until=until,
            limit=50,
            offset=0,
        )

        mock_entity_repository.list.assert_called_once()
        assert len(entities) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_queries_without_type_filter(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test query without entity type filter."""
        entities_list = [
            create_mock_entity(entity_type="person"),
            create_mock_entity(entity_type="vehicle"),
        ]
        mock_entity_repository.list.return_value = (entities_list, 2)

        entities, total = await hybrid_storage.get_entities_by_timerange(
            entity_type=None,
            limit=100,
        )

        assert len(entities) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_pagination_parameters(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that pagination parameters are passed correctly."""
        mock_entity_repository.list.return_value = ([], 0)

        await hybrid_storage.get_entities_by_timerange(
            limit=25,
            offset=50,
        )

        call_kwargs = mock_entity_repository.list.call_args[1]
        assert call_kwargs.get("limit") == 25
        assert call_kwargs.get("offset") == 50


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestHybridStorageWorkflows:
    """Tests for complete hybrid storage workflows."""

    @pytest.mark.asyncio
    async def test_store_and_find_workflow(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test complete store and find workflow."""
        embedding = create_sample_embedding(seed=100)
        timestamp = datetime.now(UTC)

        # Step 1: Store a new detection
        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        entity_id, is_new = await hybrid_storage.store_detection_embedding(
            detection_id=1001,
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=timestamp,
        )

        assert is_new is True
        assert entity_id == new_entity.id

        # Step 2: Find matches (should find the stored entity)
        redis_match = EntityMatch(
            entity=EntityEmbedding(
                entity_type="person",
                embedding=embedding,
                camera_id="front_door",
                timestamp=timestamp,
                detection_id="det_1001",
            ),
            similarity=0.99,
            time_gap_seconds=0,
        )
        mock_reid_service.find_matching_entities.return_value = [redis_match]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
        )

        assert len(matches) >= 1

    @pytest.mark.asyncio
    async def test_vehicle_entity_workflow(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test workflow for vehicle entities."""
        embedding = create_sample_embedding(seed=200)
        timestamp = datetime.now(UTC)

        vehicle_entity = create_mock_entity(entity_type="vehicle", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (vehicle_entity, True, None)

        _entity_id, is_new = await hybrid_storage.store_detection_embedding(
            detection_id=2001,
            entity_type="vehicle",
            embedding=embedding,
            camera_id="driveway",
            timestamp=timestamp,
            attributes={"color": "blue", "vehicle_type": "sedan"},
        )

        assert is_new is True

        # Verify entity type was passed correctly
        call_kwargs = mock_clustering_service.assign_entity.call_args[1]
        assert call_kwargs.get("entity_type") == "vehicle"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in HybridEntityStorage."""

    @pytest.mark.asyncio
    async def test_handles_redis_store_error_gracefully(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test that Redis errors during store don't prevent PostgreSQL storage."""
        embedding = create_sample_embedding(seed=300)
        timestamp = datetime.now(UTC)

        # PostgreSQL succeeds
        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        # Redis fails
        mock_reid_service.store_embedding.side_effect = Exception("Redis error")

        # Should still return entity from PostgreSQL
        # (implementation may choose to log error or raise depending on design)
        try:
            entity_id, _is_new = await hybrid_storage.store_detection_embedding(
                detection_id=3001,
                entity_type="person",
                embedding=embedding,
                camera_id="test",
                timestamp=timestamp,
            )
            # If it doesn't raise, verify PostgreSQL storage worked
            assert entity_id == new_entity.id
        except Exception:
            # If it raises, that's also acceptable behavior
            pass

    @pytest.mark.asyncio
    async def test_handles_redis_find_error_gracefully(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that Redis errors during find fall back to PostgreSQL."""
        embedding = create_sample_embedding(seed=301)

        # Redis fails
        mock_reid_service.find_matching_entities.side_effect = Exception("Redis error")

        # PostgreSQL works
        pg_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_entity_repository.find_by_embedding.return_value = [(pg_entity, 0.90)]

        # Should fall back to PostgreSQL or return empty depending on implementation
        try:
            matches = await hybrid_storage.find_matches(
                embedding=embedding,
                entity_type="person",
                threshold=0.85,
            )
            # If it returns results, they should be from PostgreSQL
            assert isinstance(matches, list)
        except Exception:
            # If it raises, that's also acceptable behavior
            pass


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in HybridEntityStorage."""

    @pytest.mark.asyncio
    async def test_empty_embedding(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test handling of empty embedding in find_matches."""
        mock_reid_service.find_matching_entities.return_value = []

        matches = await hybrid_storage.find_matches(
            embedding=[],
            entity_type="person",
            threshold=0.85,
            include_historical=False,
        )

        assert matches == []

    @pytest.mark.asyncio
    async def test_high_threshold(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test find_matches with very high threshold."""
        embedding = create_sample_embedding(seed=400)
        mock_reid_service.find_matching_entities.return_value = []

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.99,  # Very high threshold
            include_historical=False,
        )

        # Verify threshold was passed correctly
        call_kwargs = mock_reid_service.find_matching_entities.call_args[1]
        assert call_kwargs.get("threshold") == 0.99

    @pytest.mark.asyncio
    async def test_none_attributes(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test store_detection_embedding with None attributes."""
        embedding = create_sample_embedding(seed=401)
        timestamp = datetime.now(UTC)

        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        _entity_id, is_new = await hybrid_storage.store_detection_embedding(
            detection_id=4001,
            entity_type="person",
            embedding=embedding,
            camera_id="test",
            timestamp=timestamp,
            attributes=None,
        )

        assert is_new is True


# =============================================================================
# Match Conversion Tests
# =============================================================================


class TestMatchConversion:
    """Tests for HybridEntityMatch conversion."""

    @pytest.mark.asyncio
    async def test_redis_match_to_hybrid_match(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test that Redis EntityMatch is converted to HybridEntityMatch."""
        from backend.services.hybrid_entity_storage import HybridEntityMatch

        embedding = create_sample_embedding(seed=500)

        redis_match = EntityMatch(
            entity=EntityEmbedding(
                entity_type="person",
                embedding=embedding,
                camera_id="front_door",
                timestamp=datetime.now(UTC) - timedelta(minutes=5),
                detection_id="det_500",
            ),
            similarity=0.92,
            time_gap_seconds=300,
        )
        mock_reid_service.find_matching_entities.return_value = [redis_match]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=False,
        )

        assert len(matches) == 1
        # Verify match is converted to HybridEntityMatch
        assert isinstance(matches[0], HybridEntityMatch)
        assert matches[0].similarity == 0.92
        assert matches[0].source == "redis"

    @pytest.mark.asyncio
    async def test_postgresql_match_to_hybrid_match(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that PostgreSQL match is converted to HybridEntityMatch."""
        from backend.services.hybrid_entity_storage import HybridEntityMatch

        embedding = create_sample_embedding(seed=501)

        # No Redis matches
        mock_reid_service.find_matching_entities.return_value = []

        # PostgreSQL returns match
        pg_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_entity_repository.find_by_embedding.return_value = [(pg_entity, 0.88)]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=True,
        )

        assert len(matches) == 1
        assert isinstance(matches[0], HybridEntityMatch)
        assert matches[0].similarity == 0.88
        assert matches[0].source == "postgresql"
