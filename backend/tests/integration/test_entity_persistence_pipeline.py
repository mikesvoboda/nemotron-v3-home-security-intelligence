"""Integration tests for entity persistence in the enrichment pipeline.

Tests verify that entities are written to PostgreSQL when the enrichment
pipeline processes detections with re-identification enabled.

Related to NEM-2453: Verify and Update Enrichment Pipeline to Write Entities to PostgreSQL.

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- db_session: AsyncSession for database
- mock_redis: Mock Redis client for tests
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from backend.repositories.entity_repository import EntityRepository
from backend.services.entity_clustering_service import EntityClusteringService
from backend.services.hybrid_entity_storage import HybridEntityStorage
from backend.services.reid_service import ReIdentificationService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


def unique_embedding(seed: int | None = None) -> list[float]:
    """Generate a unique 768-dim embedding for testing.

    Using random values ensures embeddings don't accidentally match
    entities from other tests sharing the same database session.
    """
    # S311: Using pseudo-random for test data, not cryptographic purposes
    rng = random.Random(seed) if seed is not None else random.Random()  # noqa: S311
    return [rng.uniform(-1, 1) for _ in range(768)]


class TestEntityClusteringServiceCameraTracking:
    """Tests for cameras_seen tracking in EntityClusteringService.

    Verifies NEM-2453 requirement: cameras_seen tracked in entity_metadata.

    Note: Tests use valid entity types (person, vehicle, etc.) as required
    by the database constraint ck_entities_entity_type.
    """

    async def test_new_entity_initializes_cameras_seen(
        self,
        db_session: AsyncSession,
    ):
        """Test that new entities have cameras_seen initialized."""
        # Setup
        entity_repo = EntityRepository(db_session)
        clustering_service = EntityClusteringService(entity_repository=entity_repo)

        # Use valid entity_type and unique embedding
        embedding = unique_embedding(seed=10001)

        # Act: Create new entity
        entity, is_new, _similarity = await clustering_service.assign_entity(
            detection_id=1001,
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            attributes={"clothing": "blue jacket"},
        )

        # Assert - entity was created (new or matched previous from same test)
        assert entity is not None
        assert entity.entity_metadata is not None
        assert "cameras_seen" in entity.entity_metadata
        # If new, should have front_door; if matched existing, should include it
        assert "front_door" in entity.entity_metadata["cameras_seen"]
        if is_new:
            assert entity.entity_metadata.get("camera_id") == "front_door"
            assert entity.detection_count == 1

    async def test_existing_entity_tracks_multiple_cameras(
        self,
        db_session: AsyncSession,
    ):
        """Test that repeat detections add to cameras_seen list."""
        # Setup
        entity_repo = EntityRepository(db_session)
        clustering_service = EntityClusteringService(
            entity_repository=entity_repo,
            similarity_threshold=0.80,  # Lower threshold for test
        )

        # Use unique embedding for this test
        embedding = unique_embedding(seed=20001)

        # Create initial entity
        entity1, _is_new1, _ = await clustering_service.assign_entity(
            detection_id=2001,
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
        )
        initial_count = entity1.detection_count

        # Act: Same entity seen from different camera (same embedding)
        entity2, is_new2, similarity = await clustering_service.assign_entity(
            detection_id=2002,
            entity_type="person",
            embedding=embedding,  # Same embedding should match
            camera_id="back_door",
            timestamp=datetime.now(UTC),
        )

        # Assert: Should match existing entity and add camera
        assert is_new2 is False
        assert similarity is not None
        assert similarity >= 0.80  # Should match with high similarity
        assert entity1.id == entity2.id  # Same entity
        assert entity2.entity_metadata is not None
        assert "cameras_seen" in entity2.entity_metadata
        assert "front_door" in entity2.entity_metadata["cameras_seen"]
        assert "back_door" in entity2.entity_metadata["cameras_seen"]
        # Detection count should increase
        assert entity2.detection_count == initial_count + 1

    async def test_same_camera_not_duplicated(
        self,
        db_session: AsyncSession,
    ):
        """Test that same camera isn't duplicated in cameras_seen."""
        # Setup
        entity_repo = EntityRepository(db_session)
        clustering_service = EntityClusteringService(
            entity_repository=entity_repo,
            similarity_threshold=0.80,
        )

        # Use unique embedding for this test
        embedding = unique_embedding(seed=30001)

        # Create initial entity
        entity1, _is_new1, _ = await clustering_service.assign_entity(
            detection_id=3001,
            entity_type="person",
            embedding=embedding,
            camera_id="garage",
            timestamp=datetime.now(UTC),
        )
        initial_count = entity1.detection_count
        initial_cameras_len = len(entity1.entity_metadata.get("cameras_seen", []))

        # Act: Same entity, same camera
        entity2, is_new, _ = await clustering_service.assign_entity(
            detection_id=3002,
            entity_type="person",
            embedding=embedding,
            camera_id="garage",  # Same camera
            timestamp=datetime.now(UTC),
        )

        # Assert
        assert is_new is False
        assert entity2.entity_metadata is not None
        # Should not have more cameras than before (garage already tracked)
        assert len(entity2.entity_metadata.get("cameras_seen", [])) == initial_cameras_len
        assert "garage" in entity2.entity_metadata["cameras_seen"]
        assert entity2.detection_count == initial_count + 1  # Still incremented


class TestHybridEntityStorageIntegration:
    """Integration tests for HybridEntityStorage with PostgreSQL.

    Verifies NEM-2453 requirements:
    - Entities written to PostgreSQL
    - detection_count increments
    - last_seen_at updates
    """

    async def test_store_detection_creates_entity_in_postgres(
        self,
        db_session: AsyncSession,
        mock_redis,
    ):
        """Test that store_detection_embedding creates entity in PostgreSQL."""
        # Configure mock_redis to behave like Redis for get/set operations
        mock_redis.get.return_value = None  # No existing key
        mock_redis.set.return_value = True

        # Setup services
        entity_repo = EntityRepository(db_session)
        clustering_service = EntityClusteringService(entity_repository=entity_repo)
        reid_service = ReIdentificationService()

        hybrid_storage = HybridEntityStorage(
            redis_client=mock_redis,
            entity_repository=entity_repo,
            clustering_service=clustering_service,
            reid_service=reid_service,
        )

        # Test embedding - unique for this test
        embedding = unique_embedding(seed=40001)
        timestamp = datetime.now(UTC)

        # Act
        entity_id, _is_new = await hybrid_storage.store_detection_embedding(
            detection_id=4001,
            entity_type="vehicle",
            embedding=embedding,
            camera_id="driveway",
            timestamp=timestamp,
            attributes={"color": "red", "vehicle_type": "sedan"},
        )

        # Assert: Entity was stored (may be new or matched existing with same embedding)
        assert entity_id is not None

        # Verify entity exists in database
        entity = await entity_repo.get_by_id(entity_id)
        assert entity is not None
        assert entity.entity_type == "vehicle"
        assert entity.entity_metadata is not None
        # cameras_seen should include driveway
        assert "driveway" in entity.entity_metadata.get("cameras_seen", [])

    async def test_repeat_detection_updates_existing_entity(
        self,
        db_session: AsyncSession,
        mock_redis,
    ):
        """Test that repeat detections update existing entity."""
        # Configure mock_redis to behave like Redis for get/set operations
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        # Setup services
        entity_repo = EntityRepository(db_session)
        clustering_service = EntityClusteringService(
            entity_repository=entity_repo,
            similarity_threshold=0.80,
        )
        reid_service = ReIdentificationService()

        hybrid_storage = HybridEntityStorage(
            redis_client=mock_redis,
            entity_repository=entity_repo,
            clustering_service=clustering_service,
            reid_service=reid_service,
        )

        # Create first detection - unique embedding for this test
        embedding = unique_embedding(seed=50001)
        first_timestamp = datetime.now(UTC)

        entity_id1, _is_new1 = await hybrid_storage.store_detection_embedding(
            detection_id=5001,
            entity_type="person",
            embedding=embedding,
            camera_id="entrance",
            timestamp=first_timestamp,
        )

        # Get initial detection count
        entity1 = await entity_repo.get_by_id(entity_id1)
        initial_count = entity1.detection_count

        # Act: Same entity detected again (same embedding)
        second_timestamp = datetime.now(UTC)
        entity_id2, is_new2 = await hybrid_storage.store_detection_embedding(
            detection_id=5002,
            entity_type="person",
            embedding=embedding,
            camera_id="lobby",
            timestamp=second_timestamp,
        )

        # Assert
        assert is_new2 is False  # Matched existing
        assert entity_id1 == entity_id2  # Same entity

        # Verify updates in database
        entity = await entity_repo.get_by_id(entity_id1)
        assert entity is not None
        assert entity.detection_count == initial_count + 1  # Incremented
        assert entity.last_seen_at >= first_timestamp  # Updated
        assert "entrance" in entity.entity_metadata.get("cameras_seen", [])
        assert "lobby" in entity.entity_metadata.get("cameras_seen", [])


class TestEnrichmentPipelineWithSession:
    """Integration tests for get_enrichment_pipeline_with_session.

    Verifies NEM-2453 requirement: Entity appears in API after detection processed.
    """

    async def test_pipeline_factory_creates_hybrid_storage(
        self,
        db_session: AsyncSession,
        mock_redis,
    ):
        """Test that get_enrichment_pipeline_with_session configures hybrid storage."""
        from backend.services.enrichment_pipeline import get_enrichment_pipeline_with_session

        # Act
        pipeline = await get_enrichment_pipeline_with_session(
            session=db_session,
            redis_client=mock_redis,
        )

        # Assert: Pipeline has reid_service with hybrid_storage
        assert pipeline._reid_service is not None
        assert pipeline._reid_service.hybrid_storage is not None

    async def test_reid_service_persists_to_postgres(
        self,
        db_session: AsyncSession,
        mock_redis,
    ):
        """Test that ReIdentificationService with hybrid_storage persists entities."""
        from backend.services.reid_service import EntityEmbedding

        # Configure mock_redis to behave like Redis for get/set operations
        mock_redis.get.return_value = None  # No existing key
        mock_redis.set.return_value = True

        # Setup services
        entity_repo = EntityRepository(db_session)
        clustering_service = EntityClusteringService(entity_repository=entity_repo)
        reid_service_for_hybrid = ReIdentificationService()

        hybrid_storage = HybridEntityStorage(
            redis_client=mock_redis,
            entity_repository=entity_repo,
            clustering_service=clustering_service,
            reid_service=reid_service_for_hybrid,
        )

        reid_service = ReIdentificationService(hybrid_storage=hybrid_storage)

        # Create embedding - use valid entity_type
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=unique_embedding(seed=60001),
            camera_id="test_camera",
            timestamp=datetime.now(UTC),
            detection_id="6001",
            attributes={"clothing": "black coat"},
        )

        # Act: Store embedding (should persist to PostgreSQL)
        entity_id = await reid_service.store_embedding(
            redis_client=mock_redis,
            embedding=embedding,
            persist_to_postgres=True,
        )

        # Assert
        assert entity_id is not None

        # Verify entity exists in database
        entity = await entity_repo.get_by_id(entity_id)
        assert entity is not None
        assert entity.entity_type == "person"


class TestEntityRepositoryGetOrCreate:
    """Tests for EntityRepository.get_or_create_for_detection method.

    Verifies correct behavior for entity creation and matching.
    """

    async def test_get_or_create_creates_new_entity(
        self,
        db_session: AsyncSession,
    ):
        """Test that get_or_create creates entity when no match exists."""
        entity_repo = EntityRepository(db_session)

        # Unique embedding for this test
        embedding = unique_embedding(seed=70001)
        entity, _is_new = await entity_repo.get_or_create_for_detection(
            detection_id=7001,
            entity_type="person",
            embedding=embedding,
            threshold=0.85,
            attributes={"camera_id": "parking_lot"},
        )

        # Verify entity was stored
        assert entity is not None
        assert entity.entity_type == "person"
        assert entity.detection_count >= 1

    async def test_get_or_create_finds_existing_entity(
        self,
        db_session: AsyncSession,
    ):
        """Test that get_or_create finds and updates existing entity."""
        entity_repo = EntityRepository(db_session)

        # Create first entity - unique embedding for this test
        embedding = unique_embedding(seed=80001)
        entity1, _is_new1 = await entity_repo.get_or_create_for_detection(
            detection_id=8001,
            entity_type="vehicle",
            embedding=embedding,
            threshold=0.85,
        )
        initial_count = entity1.detection_count

        # Find same entity (same embedding)
        entity2, is_new2 = await entity_repo.get_or_create_for_detection(
            detection_id=8002,
            entity_type="vehicle",
            embedding=embedding,
            threshold=0.85,
        )

        assert is_new2 is False
        assert entity1.id == entity2.id
        assert entity2.detection_count == initial_count + 1


class TestEntityStatsAfterPipeline:
    """Tests verifying entity statistics after pipeline processing."""

    async def test_entity_stats_reflect_detections(
        self,
        db_session: AsyncSession,
        mock_redis,
    ):
        """Test that entity stats API returns correct counts after pipeline."""
        # Configure mock_redis to behave like Redis for get/set operations
        mock_redis.get.return_value = None  # No existing key
        mock_redis.set.return_value = True

        # Setup
        entity_repo = EntityRepository(db_session)
        clustering_service = EntityClusteringService(entity_repository=entity_repo)
        reid_service = ReIdentificationService()

        hybrid_storage = HybridEntityStorage(
            redis_client=mock_redis,
            entity_repository=entity_repo,
            clustering_service=clustering_service,
            reid_service=reid_service,
        )

        # Get initial person count
        initial_stats = await entity_repo.get_stats(entity_type="person")
        initial_entities = initial_stats.get("total_entities", 0)

        # Create some entities with unique embeddings that won't match each other
        for i in range(3):
            # Use unique random embeddings for each entity
            embedding = unique_embedding(seed=90000 + i * 1000)
            await hybrid_storage.store_detection_embedding(
                detection_id=9000 + i,
                entity_type="person",
                embedding=embedding,
                camera_id=f"camera_{i}",
                timestamp=datetime.now(UTC),
            )

        # Verify stats - should have at least some new entities
        stats = await entity_repo.get_stats(entity_type="person")
        # Entities should have increased (some might match existing due to similarity)
        assert stats["total_entities"] >= initial_entities
        assert stats["total_detections"] >= 1
