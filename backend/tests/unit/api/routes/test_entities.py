"""Unit tests for entities API routes.

Tests the entity re-identification tracking endpoints using real
database operations via EntityRepository.

Includes tests for:
- Historical entity queries (PostgreSQL via EntityRepository)
- Date range filtering (since, until)
- Entity statistics endpoint
- Entity detections endpoint
- Pagination and filtering
- UUID validation
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

# Import the entire module to ensure coverage tracks it
import backend.api.routes.entities  # noqa: F401
from backend.api.routes.entities import (
    _entity_to_summary,
    _get_thumbnail_url,
    get_entity,
    get_entity_history,
    list_entities,
)
from backend.api.schemas.entities import EntityTypeFilter
from backend.core.database import get_session
from backend.models import Detection, Entity
from backend.repositories.entity_repository import EntityRepository
from backend.services.reid_service import EntityEmbedding


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
async def db_session(isolated_db):
    """Provide a database session for entity tests."""
    async with get_session() as session:
        yield session


@pytest.fixture
async def entity_repo(db_session):
    """Provide an EntityRepository instance."""
    return EntityRepository(db_session)


@pytest.fixture
async def sample_person_entity(db_session) -> Entity:
    """Create a sample person entity in the database."""
    entity = Entity(
        id=uuid4(),
        entity_type="person",
        first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        last_seen_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
        detection_count=3,
        primary_detection_id=None,  # Will be set after detections are created
        entity_metadata={"camera_id": "front_door", "clothing": "blue jacket"},
        embedding_vector={
            "vector": [0.1] * 768,
            "model": "clip",
            "dimension": 768,
        },
    )
    db_session.add(entity)
    await db_session.commit()
    await db_session.refresh(entity)
    return entity


@pytest.fixture
async def sample_vehicle_entity(db_session) -> Entity:
    """Create a sample vehicle entity in the database."""
    entity = Entity(
        id=uuid4(),
        entity_type="vehicle",
        first_seen_at=datetime(2025, 12, 23, 11, 0, 0, tzinfo=UTC),
        last_seen_at=datetime(2025, 12, 23, 13, 0, 0, tzinfo=UTC),
        detection_count=2,
        primary_detection_id=None,
        entity_metadata={"camera_id": "driveway", "color": "silver"},
        embedding_vector={
            "vector": [0.2] * 768,
            "model": "clip",
            "dimension": 768,
        },
    )
    db_session.add(entity)
    await db_session.commit()
    await db_session.refresh(entity)
    return entity


@pytest.fixture
async def sample_detections(db_session, sample_person_entity) -> list[Detection]:
    """Create sample detections linked to person entity."""
    from backend.models import Camera

    # Create a camera first
    camera = Camera(
        id="front_door",
        name="Front Door",
        folder_path="/export/foscam/front_door",
        last_heartbeat=datetime.now(UTC),
    )
    db_session.add(camera)
    await db_session.commit()

    detections = [
        Detection(
            id=123,
            camera_id="front_door",
            image_path="/path/to/image1.jpg",
            detected_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=50,
            bbox_height=100,
            entity_id=sample_person_entity.id,
        ),
        Detection(
            id=124,
            camera_id="front_door",
            image_path="/path/to/image2.jpg",
            detected_at=datetime(2025, 12, 23, 11, 0, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.92,
            bbox_x=105,
            bbox_y=105,
            bbox_width=52,
            bbox_height=102,
            entity_id=sample_person_entity.id,
        ),
        Detection(
            id=125,
            camera_id="front_door",
            image_path="/path/to/image3.jpg",
            detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.88,
            bbox_x=110,
            bbox_y=110,
            bbox_width=48,
            bbox_height=98,
            entity_id=sample_person_entity.id,
        ),
    ]
    for det in detections:
        db_session.add(det)
    await db_session.commit()

    for det in detections:
        await db_session.refresh(det)

    # Now update entity's primary_detection_id after detections exist
    sample_person_entity.primary_detection_id = 123
    db_session.add(sample_person_entity)
    await db_session.commit()
    await db_session.refresh(sample_person_entity)

    return detections


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestThumbnailUrl:
    """Tests for _get_thumbnail_url helper function."""

    def test_integer_detection_id(self) -> None:
        """Test thumbnail URL generation for integer detection IDs."""
        url = _get_thumbnail_url("123")
        assert url == "/api/detections/123/image"

    def test_non_integer_detection_id(self) -> None:
        """Test thumbnail URL generation for non-integer detection IDs."""
        url = _get_thumbnail_url("det_abc123")
        assert url == "/api/detections/det_abc123/image"


class TestEntityToSummary:
    """Tests for _entity_to_summary helper function."""

    def test_single_embedding(self) -> None:
        """Test summary creation from a single embedding."""
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={"clothing": "blue jacket"},
        )

        summary = _entity_to_summary("det_001", [embedding])

        assert summary.id == "det_001"
        assert summary.entity_type == "person"
        assert summary.first_seen == embedding.timestamp
        assert summary.last_seen == embedding.timestamp
        assert summary.appearance_count == 1
        assert summary.cameras_seen == ["front_door"]
        assert summary.thumbnail_url == "/api/detections/det_001/image"

    def test_multiple_embeddings(self) -> None:
        """Test summary creation from multiple embeddings."""
        embeddings = [
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="backyard",
                timestamp=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
        ]

        summary = _entity_to_summary("det_001", embeddings)

        assert summary.appearance_count == 3
        assert len(summary.cameras_seen) == 2
        assert "front_door" in summary.cameras_seen
        assert "backyard" in summary.cameras_seen
        assert summary.first_seen == embeddings[0].timestamp
        assert summary.last_seen == embeddings[2].timestamp

    def test_empty_embeddings_raises_error(self) -> None:
        """Test that empty embeddings list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot create summary from empty"):
            _entity_to_summary("det_001", [])


class TestListEntities:
    """Tests for GET /api/entities endpoint using real database operations."""

    @pytest.mark.asyncio
    async def test_list_entities_empty(self, entity_repo) -> None:
        """Test listing entities when none exist in database."""
        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=entity_repo,
        )

        assert result.items == []
        assert result.pagination.total == 0
        assert result.pagination.has_more is False

    @pytest.mark.asyncio
    async def test_list_entities_with_data(
        self, entity_repo, sample_person_entity, sample_vehicle_entity
    ) -> None:
        """Test listing entities when data exists in database."""
        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 2
        assert len(result.items) == 2
        # Verify entity data
        entity_ids = {item.id for item in result.items}
        assert str(sample_person_entity.id) in entity_ids
        assert str(sample_vehicle_entity.id) in entity_ids

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_person_type(
        self, entity_repo, sample_person_entity, sample_vehicle_entity
    ) -> None:
        """Test filtering entities by person type."""
        result = await list_entities(
            entity_type=EntityTypeFilter.person,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 1
        assert len(result.items) == 1
        assert result.items[0].entity_type == "person"
        assert result.items[0].id == str(sample_person_entity.id)

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_vehicle_type(
        self, entity_repo, sample_person_entity, sample_vehicle_entity
    ) -> None:
        """Test filtering entities by vehicle type."""
        result = await list_entities(
            entity_type=EntityTypeFilter.vehicle,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 1
        assert len(result.items) == 1
        assert result.items[0].entity_type == "vehicle"
        assert result.items[0].id == str(sample_vehicle_entity.id)

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_camera(
        self, entity_repo, sample_person_entity, sample_vehicle_entity
    ) -> None:
        """Test filtering entities by camera ID."""
        result = await list_entities(
            entity_type=None,
            camera_id="front_door",
            since=None,
            limit=50,
            offset=0,
            entity_repo=entity_repo,
        )

        # Only person entity has front_door in metadata
        assert result.pagination.total == 1
        assert result.items[0].id == str(sample_person_entity.id)

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_since(self, entity_repo, sample_person_entity) -> None:
        """Test filtering entities by timestamp."""
        # Query with since after person's last_seen (should return nothing)
        since = datetime(2025, 12, 23, 13, 0, 0, tzinfo=UTC)
        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=since,
            limit=50,
            offset=0,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 0

        # Query with since before person's last_seen (should return entity)
        since = datetime(2025, 12, 23, 11, 0, 0, tzinfo=UTC)
        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=since,
            limit=50,
            offset=0,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 1
        assert result.items[0].id == str(sample_person_entity.id)

    @pytest.mark.asyncio
    async def test_list_entities_pagination(
        self, db_session, entity_repo
    ) -> None:
        """Test pagination of entity list."""
        # Create 5 entities
        entities = []
        for i in range(5):
            entity = Entity(
                id=uuid4(),
                entity_type="person",
                first_seen_at=datetime.now(UTC) - timedelta(hours=i),
                last_seen_at=datetime.now(UTC) - timedelta(hours=i),
                detection_count=1,
            )
            db_session.add(entity)
            entities.append(entity)
        await db_session.commit()

        # Test first page
        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=2,
            offset=0,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 5
        assert len(result.items) == 2
        assert result.pagination.limit == 2
        assert result.pagination.offset == 0
        assert result.pagination.has_more is True

        # Test second page
        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=2,
            offset=2,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 5
        assert len(result.items) == 2
        assert result.pagination.offset == 2
        assert result.pagination.has_more is True

        # Test last page
        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=2,
            offset=4,
            entity_repo=entity_repo,
        )

        assert result.pagination.total == 5
        assert len(result.items) == 1
        assert result.pagination.offset == 4
        assert result.pagination.has_more is False


class TestGetEntity:
    """Tests for GET /api/entities/{entity_id} endpoint using real database."""

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, entity_repo) -> None:
        """Test getting non-existent entity returns 404."""
        nonexistent_id = uuid4()

        with pytest.raises(Exception) as exc_info:
            await get_entity(nonexistent_id, entity_repo=entity_repo)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_entity_success(
        self, entity_repo, sample_person_entity, sample_detections
    ) -> None:
        """Test getting entity successfully with detections."""
        result = await get_entity(sample_person_entity.id, entity_repo=entity_repo)

        assert result.id == str(sample_person_entity.id)
        assert result.entity_type == "person"
        assert result.appearance_count == 3
        assert len(result.appearances) == 3
        # Verify detection IDs
        detection_ids = {app.detection_id for app in result.appearances}
        assert "123" in detection_ids
        assert "124" in detection_ids
        assert "125" in detection_ids

    @pytest.mark.asyncio
    async def test_get_entity_with_no_detections(self, entity_repo, sample_vehicle_entity) -> None:
        """Test getting entity that has no linked detections."""
        result = await get_entity(sample_vehicle_entity.id, entity_repo=entity_repo)

        assert result.id == str(sample_vehicle_entity.id)
        assert result.entity_type == "vehicle"
        assert result.appearance_count == 2  # From entity.detection_count
        assert len(result.appearances) == 0  # No actual detections linked


class TestGetEntityHistory:
    """Tests for GET /api/entities/{entity_id}/history endpoint using real database."""

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, entity_repo) -> None:
        """Test getting history for non-existent entity returns 404."""
        nonexistent_id = uuid4()

        with pytest.raises(Exception) as exc_info:
            await get_entity_history(nonexistent_id, entity_repo=entity_repo)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_history_success(
        self, entity_repo, sample_person_entity, sample_detections
    ) -> None:
        """Test getting entity history successfully."""
        result = await get_entity_history(sample_person_entity.id, entity_repo=entity_repo)

        assert result.entity_id == str(sample_person_entity.id)
        assert result.entity_type == "person"
        assert result.count == 3
        assert len(result.appearances) == 3

        # Verify chronological order (detections should be sorted by timestamp)
        timestamps = [app.timestamp for app in result.appearances]
        assert timestamps == sorted(timestamps)

        # Verify camera IDs are correct
        camera_ids = [app.camera_id for app in result.appearances]
        assert all(cid == "front_door" for cid in camera_ids)

    @pytest.mark.asyncio
    async def test_get_history_empty(self, entity_repo, sample_vehicle_entity) -> None:
        """Test getting history for entity with no detections."""
        result = await get_entity_history(sample_vehicle_entity.id, entity_repo=entity_repo)

        assert result.entity_id == str(sample_vehicle_entity.id)
        assert result.entity_type == "vehicle"
        assert result.count == 0
        assert len(result.appearances) == 0


# NOTE: Tests for _get_redis_client and matches endpoint use mocks since they
# specifically test Redis integration, not database operations.
