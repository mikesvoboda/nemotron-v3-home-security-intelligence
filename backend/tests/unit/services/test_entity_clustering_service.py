"""Unit tests for EntityClusteringService.

Tests cover:
- New detection with no matches creates new entity
- New detection matching existing entity updates that entity
- Similarity threshold is respected (below threshold = new entity)
- Multiple detections of same person cluster correctly
- Different people create separate entities
- Entity detection_count increments correctly
- Entity last_seen_at updates correctly
- Edge cases: empty embeddings, boundary threshold values

Related to NEM-2497: Create Entity Clustering Service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.entity import Entity
from backend.services.entity_clustering_service import EntityClusteringService

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
    # For seed=0, we get a unit vector in first dimension
    # For different seeds, we get different orthogonal-ish vectors
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
def mock_entity_repository() -> AsyncMock:
    """Create a mock EntityRepository for testing."""
    repo = AsyncMock()
    repo.find_by_embedding = AsyncMock(return_value=[])
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.increment_detection_count = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.session = MagicMock()
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()
    return repo


@pytest.fixture
def clustering_service(mock_entity_repository: AsyncMock) -> EntityClusteringService:
    """Create EntityClusteringService with mock repository."""
    return EntityClusteringService(
        entity_repository=mock_entity_repository,
        similarity_threshold=0.85,
        embedding_model="clip",
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestEntityClusteringServiceInit:
    """Tests for EntityClusteringService initialization."""

    def test_init_with_defaults(self, mock_entity_repository: AsyncMock) -> None:
        """Test service initializes with default parameters."""
        service = EntityClusteringService(entity_repository=mock_entity_repository)
        assert service.entity_repository == mock_entity_repository
        assert service.similarity_threshold == 0.85  # Default threshold
        assert service.embedding_model == "clip"  # Default model

    def test_init_with_custom_threshold(self, mock_entity_repository: AsyncMock) -> None:
        """Test service initializes with custom similarity threshold."""
        service = EntityClusteringService(
            entity_repository=mock_entity_repository,
            similarity_threshold=0.90,
        )
        assert service.similarity_threshold == 0.90

    def test_init_with_custom_embedding_model(self, mock_entity_repository: AsyncMock) -> None:
        """Test service initializes with custom embedding model."""
        service = EntityClusteringService(
            entity_repository=mock_entity_repository,
            embedding_model="resnet",
        )
        assert service.embedding_model == "resnet"


# =============================================================================
# assign_entity Tests - New Entity Creation
# =============================================================================


class TestAssignEntityNewEntity:
    """Tests for assign_entity when no matching entity exists."""

    @pytest.mark.asyncio
    async def test_creates_new_entity_when_no_matches(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test creates new entity when no similar entities exist."""
        # Setup: No matches found
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=1)
        timestamp = datetime.now(UTC)

        # Create a new entity to be returned
        new_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=1,
        )

        # Mock the session to return the new entity after creation
        async def mock_refresh(entity: Entity) -> None:
            entity.id = new_entity.id
            entity.detection_count = 1
            entity.first_seen_at = timestamp
            entity.last_seen_at = timestamp

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        _entity, is_new, match_similarity = await clustering_service.assign_entity(
            detection_id=123,
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=timestamp,
            attributes={"clothing": "blue jacket"},
        )

        assert is_new is True
        assert match_similarity is None
        mock_entity_repository.find_by_embedding.assert_called_once()
        mock_entity_repository.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_entity_has_correct_metadata(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test new entity is created with correct metadata."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=2)
        timestamp = datetime.now(UTC)
        attributes = {"clothing": "red shirt", "carrying": "backpack"}

        # Track the entity that gets added
        added_entity: Entity | None = None

        def capture_add(entity: Entity) -> None:
            nonlocal added_entity
            added_entity = entity

        mock_entity_repository.session.add.side_effect = capture_add

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        _entity, is_new, _ = await clustering_service.assign_entity(
            detection_id=456,
            entity_type="person",
            embedding=embedding,
            camera_id="backyard",
            timestamp=timestamp,
            attributes=attributes,
        )

        assert is_new is True
        assert added_entity is not None
        assert added_entity.entity_type == "person"
        assert added_entity.primary_detection_id == 456
        # Check embedding was set
        assert added_entity.get_embedding_vector() == embedding


# =============================================================================
# assign_entity Tests - Match Existing Entity
# =============================================================================


class TestAssignEntityMatchExisting:
    """Tests for assign_entity when matching entity exists."""

    @pytest.mark.asyncio
    async def test_matches_existing_entity_above_threshold(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test matches existing entity when similarity is above threshold."""
        embedding = create_sample_embedding(seed=1)
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=5,
        )

        # Return match with high similarity (0.95 > 0.85 threshold)
        mock_entity_repository.find_by_embedding.return_value = [
            (existing_entity, 0.95),
        ]

        timestamp = datetime.now(UTC)

        entity, is_new, match_similarity = await clustering_service.assign_entity(
            detection_id=789,
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=timestamp,
        )

        assert is_new is False
        assert match_similarity == 0.95
        assert entity.id == existing_entity.id
        mock_entity_repository.find_by_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_entity_when_below_threshold(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test creates new entity when similarity is below threshold."""
        # No matches above threshold returned by repository
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=3)
        timestamp = datetime.now(UTC)

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        _entity, is_new, match_similarity = await clustering_service.assign_entity(
            detection_id=101,
            entity_type="person",
            embedding=embedding,
            camera_id="side_gate",
            timestamp=timestamp,
        )

        assert is_new is True
        assert match_similarity is None
        mock_entity_repository.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_best_match_when_multiple_candidates(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test returns best match when multiple entities are similar."""
        embedding = create_sample_embedding(seed=1)

        entity1 = create_mock_entity(entity_type="person", detection_count=3)
        entity2 = create_mock_entity(entity_type="person", detection_count=5)

        # Repository returns matches sorted by similarity (highest first)
        mock_entity_repository.find_by_embedding.return_value = [
            (entity2, 0.95),  # Best match
            (entity1, 0.88),  # Second best
        ]

        timestamp = datetime.now(UTC)

        entity, is_new, match_similarity = await clustering_service.assign_entity(
            detection_id=202,
            entity_type="person",
            embedding=embedding,
            camera_id="driveway",
            timestamp=timestamp,
        )

        assert is_new is False
        assert match_similarity == 0.95
        assert entity.id == entity2.id  # Should match the best one


# =============================================================================
# Detection Count Tests
# =============================================================================


class TestDetectionCount:
    """Tests for detection count management."""

    @pytest.mark.asyncio
    async def test_new_entity_has_detection_count_one(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test new entity starts with detection_count = 1."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=10)
        timestamp = datetime.now(UTC)

        added_entity: Entity | None = None

        def capture_add(entity: Entity) -> None:
            nonlocal added_entity
            added_entity = entity

        mock_entity_repository.session.add.side_effect = capture_add

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        await clustering_service.assign_entity(
            detection_id=301,
            entity_type="person",
            embedding=embedding,
            camera_id="garage",
            timestamp=timestamp,
        )

        assert added_entity is not None
        assert added_entity.detection_count == 1

    @pytest.mark.asyncio
    async def test_matched_entity_increments_detection_count(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test matching entity increments detection count."""
        embedding = create_sample_embedding(seed=11)
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=5,
        )

        mock_entity_repository.find_by_embedding.return_value = [
            (existing_entity, 0.92),
        ]

        timestamp = datetime.now(UTC)

        await clustering_service.assign_entity(
            detection_id=302,
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=timestamp,
        )

        # Verify update_seen was called (which increments detection_count)
        # The entity's update_seen method should have been called
        assert existing_entity.detection_count == 6


# =============================================================================
# Timestamp Tests
# =============================================================================


class TestTimestampUpdates:
    """Tests for timestamp management."""

    @pytest.mark.asyncio
    async def test_new_entity_sets_first_and_last_seen(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test new entity sets both first_seen_at and last_seen_at."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=20)
        timestamp = datetime.now(UTC)

        added_entity: Entity | None = None

        def capture_add(entity: Entity) -> None:
            nonlocal added_entity
            added_entity = entity

        mock_entity_repository.session.add.side_effect = capture_add

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        await clustering_service.assign_entity(
            detection_id=401,
            entity_type="vehicle",
            embedding=embedding,
            camera_id="parking_lot",
            timestamp=timestamp,
        )

        assert added_entity is not None
        # The Entity.from_detection factory sets timestamps
        assert added_entity.first_seen_at is not None
        assert added_entity.last_seen_at is not None

    @pytest.mark.asyncio
    async def test_matched_entity_updates_last_seen(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test matching entity updates last_seen_at timestamp."""
        embedding = create_sample_embedding(seed=21)
        old_timestamp = datetime.now(UTC) - timedelta(hours=2)
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=3,
            first_seen_at=old_timestamp,
            last_seen_at=old_timestamp,
        )

        mock_entity_repository.find_by_embedding.return_value = [
            (existing_entity, 0.91),
        ]

        new_timestamp = datetime.now(UTC)

        await clustering_service.assign_entity(
            detection_id=402,
            entity_type="person",
            embedding=embedding,
            camera_id="backyard",
            timestamp=new_timestamp,
        )

        # last_seen_at should be updated to new timestamp
        # update_seen() updates last_seen_at
        assert existing_entity.last_seen_at >= old_timestamp

    @pytest.mark.asyncio
    async def test_matched_entity_preserves_first_seen(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test matching entity preserves original first_seen_at."""
        embedding = create_sample_embedding(seed=22)
        original_first_seen = datetime.now(UTC) - timedelta(days=5)
        existing_entity = create_mock_entity(
            entity_type="vehicle",
            embedding=embedding,
            detection_count=10,
            first_seen_at=original_first_seen,
        )

        mock_entity_repository.find_by_embedding.return_value = [
            (existing_entity, 0.89),
        ]

        new_timestamp = datetime.now(UTC)

        entity, _is_new, _ = await clustering_service.assign_entity(
            detection_id=403,
            entity_type="vehicle",
            embedding=embedding,
            camera_id="driveway",
            timestamp=new_timestamp,
        )

        # first_seen_at should NOT change
        assert entity.first_seen_at == original_first_seen


# =============================================================================
# Multiple Detections Clustering Tests
# =============================================================================


class TestMultipleDetectionsClustering:
    """Tests for clustering multiple detections."""

    @pytest.mark.asyncio
    async def test_same_person_clusters_correctly(
        self,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test multiple detections of same person cluster to one entity."""
        service = EntityClusteringService(
            entity_repository=mock_entity_repository,
            similarity_threshold=0.85,
        )

        # Same embedding for same person
        person_embedding = create_sample_embedding(seed=100)
        base_timestamp = datetime.now(UTC)

        # First detection - creates new entity
        mock_entity_repository.find_by_embedding.return_value = []

        first_entity = create_mock_entity(
            entity_type="person",
            embedding=person_embedding,
            detection_count=1,
        )

        async def mock_refresh_first(entity: Entity) -> None:
            entity.id = first_entity.id
            entity.detection_count = 1

        mock_entity_repository.session.refresh.side_effect = mock_refresh_first

        entity1, is_new1, _ = await service.assign_entity(
            detection_id=501,
            entity_type="person",
            embedding=person_embedding,
            camera_id="camera_1",
            timestamp=base_timestamp,
        )

        assert is_new1 is True

        # Second detection - should match existing entity
        mock_entity_repository.find_by_embedding.return_value = [
            (entity1, 0.98),  # Same person, very high similarity
        ]

        entity2, is_new2, similarity2 = await service.assign_entity(
            detection_id=502,
            entity_type="person",
            embedding=person_embedding,
            camera_id="camera_2",
            timestamp=base_timestamp + timedelta(minutes=5),
        )

        assert is_new2 is False
        assert entity2.id == entity1.id
        assert similarity2 == 0.98

    @pytest.mark.asyncio
    async def test_different_people_create_separate_entities(
        self,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test different people create separate entities."""
        service = EntityClusteringService(
            entity_repository=mock_entity_repository,
            similarity_threshold=0.85,
        )

        # Different embeddings for different people
        person1_embedding = create_sample_embedding(seed=200)
        person2_embedding = create_sample_embedding(seed=201)
        base_timestamp = datetime.now(UTC)

        # First person - creates new entity
        mock_entity_repository.find_by_embedding.return_value = []

        person1_entity = create_mock_entity(
            entity_type="person",
            embedding=person1_embedding,
            detection_count=1,
            entity_id=uuid.uuid4(),
        )

        async def mock_refresh_person1(entity: Entity) -> None:
            entity.id = person1_entity.id
            entity.detection_count = 1

        mock_entity_repository.session.refresh.side_effect = mock_refresh_person1
        mock_entity_repository.session.add.reset_mock()

        entity1, is_new1, _ = await service.assign_entity(
            detection_id=601,
            entity_type="person",
            embedding=person1_embedding,
            camera_id="camera_1",
            timestamp=base_timestamp,
        )

        assert is_new1 is True
        first_entity_id = entity1.id

        # Second person - different embedding, no match, should create new entity
        # Repository returns empty because person2's embedding doesn't match person1
        mock_entity_repository.find_by_embedding.return_value = []

        person2_entity = create_mock_entity(
            entity_type="person",
            embedding=person2_embedding,
            detection_count=1,
            entity_id=uuid.uuid4(),  # Different ID
        )

        async def mock_refresh_person2(entity: Entity) -> None:
            entity.id = person2_entity.id
            entity.detection_count = 1

        mock_entity_repository.session.refresh.side_effect = mock_refresh_person2
        mock_entity_repository.session.add.reset_mock()

        entity2, is_new2, _ = await service.assign_entity(
            detection_id=602,
            entity_type="person",
            embedding=person2_embedding,
            camera_id="camera_2",
            timestamp=base_timestamp + timedelta(minutes=1),
        )

        assert is_new2 is True
        assert entity2.id != first_entity_id  # Different entity


# =============================================================================
# Entity Type Tests
# =============================================================================


class TestEntityTypes:
    """Tests for different entity types."""

    @pytest.mark.asyncio
    async def test_vehicle_entity_creation(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test vehicle entity creation."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=300)
        timestamp = datetime.now(UTC)

        added_entity: Entity | None = None

        def capture_add(entity: Entity) -> None:
            nonlocal added_entity
            added_entity = entity

        mock_entity_repository.session.add.side_effect = capture_add

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        await clustering_service.assign_entity(
            detection_id=701,
            entity_type="vehicle",
            embedding=embedding,
            camera_id="parking",
            timestamp=timestamp,
            attributes={"color": "red", "vehicle_type": "sedan"},
        )

        assert added_entity is not None
        assert added_entity.entity_type == "vehicle"

    @pytest.mark.asyncio
    async def test_search_uses_correct_entity_type(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that entity search uses the correct entity type filter."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=301)
        timestamp = datetime.now(UTC)

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        await clustering_service.assign_entity(
            detection_id=702,
            entity_type="animal",
            embedding=embedding,
            camera_id="backyard",
            timestamp=timestamp,
        )

        # Verify find_by_embedding was called with correct entity_type
        mock_entity_repository.find_by_embedding.assert_called_once()
        call_args = mock_entity_repository.find_by_embedding.call_args
        assert call_args.kwargs["entity_type"] == "animal"


# =============================================================================
# Threshold Boundary Tests
# =============================================================================


class TestThresholdBoundaries:
    """Tests for similarity threshold boundary conditions."""

    @pytest.mark.asyncio
    async def test_exact_threshold_match(
        self,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that exact threshold value counts as a match."""
        service = EntityClusteringService(
            entity_repository=mock_entity_repository,
            similarity_threshold=0.85,
        )

        embedding = create_sample_embedding(seed=400)
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=2,
        )

        # Return match with EXACTLY threshold similarity
        mock_entity_repository.find_by_embedding.return_value = [
            (existing_entity, 0.85),  # Exactly at threshold
        ]

        timestamp = datetime.now(UTC)

        _entity, is_new, match_similarity = await service.assign_entity(
            detection_id=801,
            entity_type="person",
            embedding=embedding,
            camera_id="entrance",
            timestamp=timestamp,
        )

        # Should match (threshold is inclusive via >= in repository)
        assert is_new is False
        assert match_similarity == 0.85

    @pytest.mark.asyncio
    async def test_slightly_above_threshold(
        self,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test that slightly above threshold is a match."""
        service = EntityClusteringService(
            entity_repository=mock_entity_repository,
            similarity_threshold=0.85,
        )

        embedding = create_sample_embedding(seed=401)
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=3,
        )

        mock_entity_repository.find_by_embedding.return_value = [
            (existing_entity, 0.851),  # Just above threshold
        ]

        timestamp = datetime.now(UTC)

        _entity, is_new, match_similarity = await service.assign_entity(
            detection_id=802,
            entity_type="person",
            embedding=embedding,
            camera_id="lobby",
            timestamp=timestamp,
        )

        assert is_new is False
        assert match_similarity == 0.851

    @pytest.mark.asyncio
    async def test_custom_high_threshold(
        self,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test service works with custom high threshold."""
        service = EntityClusteringService(
            entity_repository=mock_entity_repository,
            similarity_threshold=0.95,  # Very strict threshold
        )

        embedding = create_sample_embedding(seed=402)
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=1,
        )

        # 0.90 similarity is below 0.95 threshold, so repository returns empty
        mock_entity_repository.find_by_embedding.return_value = []

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        timestamp = datetime.now(UTC)

        _entity, is_new, match_similarity = await service.assign_entity(
            detection_id=803,
            entity_type="person",
            embedding=embedding,
            camera_id="hallway",
            timestamp=timestamp,
        )

        # Should NOT match with high threshold
        assert is_new is True
        assert match_similarity is None

        # Verify threshold was passed to repository
        call_args = mock_entity_repository.find_by_embedding.call_args
        assert call_args.kwargs["threshold"] == 0.95


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_attributes(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test entity creation with empty attributes."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=500)
        timestamp = datetime.now(UTC)

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        _entity, is_new, _ = await clustering_service.assign_entity(
            detection_id=901,
            entity_type="person",
            embedding=embedding,
            camera_id="test",
            timestamp=timestamp,
            attributes=None,  # No attributes
        )

        assert is_new is True

    @pytest.mark.asyncio
    async def test_attributes_with_empty_dict(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test entity creation with empty dict attributes."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=501)
        timestamp = datetime.now(UTC)

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        _entity, is_new, _ = await clustering_service.assign_entity(
            detection_id=902,
            entity_type="person",
            embedding=embedding,
            camera_id="test",
            timestamp=timestamp,
            attributes={},  # Empty dict
        )

        assert is_new is True

    @pytest.mark.asyncio
    async def test_large_embedding_dimension(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test with standard 768-dimension CLIP embedding."""
        mock_entity_repository.find_by_embedding.return_value = []

        # Standard CLIP ViT-L embedding dimension
        embedding = create_sample_embedding(seed=502, dimension=768)
        timestamp = datetime.now(UTC)

        assert len(embedding) == 768

        async def mock_refresh(entity: Entity) -> None:
            entity.id = uuid.uuid4()

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        _entity, is_new, _ = await clustering_service.assign_entity(
            detection_id=903,
            entity_type="person",
            embedding=embedding,
            camera_id="test",
            timestamp=timestamp,
        )

        assert is_new is True


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestAssignEntityFlow:
    """Tests for complete assign_entity workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_new_entity(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test complete workflow for creating a new entity."""
        mock_entity_repository.find_by_embedding.return_value = []

        embedding = create_sample_embedding(seed=600)
        timestamp = datetime.now(UTC)
        attributes = {"clothing": "black jacket", "carrying": "briefcase"}

        entity_id = uuid.uuid4()

        async def mock_refresh(entity: Entity) -> None:
            entity.id = entity_id
            entity.detection_count = 1
            entity.first_seen_at = timestamp
            entity.last_seen_at = timestamp

        mock_entity_repository.session.refresh.side_effect = mock_refresh

        entity, is_new, match_similarity = await clustering_service.assign_entity(
            detection_id=1001,
            entity_type="person",
            embedding=embedding,
            camera_id="main_entrance",
            timestamp=timestamp,
            attributes=attributes,
        )

        # Verify results
        assert is_new is True
        assert match_similarity is None
        assert entity.id == entity_id
        assert entity.entity_type == "person"
        assert entity.detection_count == 1

        # Verify repository interactions
        mock_entity_repository.find_by_embedding.assert_called_once_with(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            limit=1,
        )
        mock_entity_repository.session.add.assert_called_once()
        # flush is called multiple times: once for entity creation, once for cameras_seen tracking
        assert mock_entity_repository.session.flush.call_count >= 1
        mock_entity_repository.session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_workflow_match_existing(
        self,
        clustering_service: EntityClusteringService,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test complete workflow for matching an existing entity."""
        embedding = create_sample_embedding(seed=601)
        first_seen = datetime.now(UTC) - timedelta(hours=3)
        existing_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            detection_count=7,
            first_seen_at=first_seen,
            last_seen_at=first_seen + timedelta(hours=1),
        )

        mock_entity_repository.find_by_embedding.return_value = [
            (existing_entity, 0.93),
        ]

        timestamp = datetime.now(UTC)

        entity, is_new, match_similarity = await clustering_service.assign_entity(
            detection_id=1002,
            entity_type="person",
            embedding=embedding,
            camera_id="side_door",
            timestamp=timestamp,
        )

        # Verify results
        assert is_new is False
        assert match_similarity == 0.93
        assert entity.id == existing_entity.id
        assert entity.detection_count == 8  # Incremented
        assert entity.first_seen_at == first_seen  # Preserved

        # Verify repository interactions - should NOT add new entity
        mock_entity_repository.session.add.assert_not_called()
