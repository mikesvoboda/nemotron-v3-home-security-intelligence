"""Unit tests for entity API schemas.

Tests the Pydantic schemas used by the entity re-identification API,
including validation, serialization, and conversion methods.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.api.schemas.entities import (
    EntityAppearance,
    EntityCreate,
    EntityDetail,
    EntityRead,
    EntitySummary,
    EntityTypeEnum,
    EntityUpdate,
)
from backend.models.entity import Entity


class TestEntityTypeEnum:
    """Tests for EntityTypeEnum."""

    def test_valid_entity_types(self) -> None:
        """Test all valid entity types."""
        assert EntityTypeEnum.PERSON == "person"
        assert EntityTypeEnum.VEHICLE == "vehicle"
        assert EntityTypeEnum.ANIMAL == "animal"
        assert EntityTypeEnum.PACKAGE == "package"
        assert EntityTypeEnum.OTHER == "other"


class TestEntityCreate:
    """Tests for EntityCreate schema."""

    def test_entity_create_minimal(self) -> None:
        """Test creating EntityCreate with minimal fields."""
        entity = EntityCreate(entity_type=EntityTypeEnum.PERSON)
        assert entity.entity_type == EntityTypeEnum.PERSON
        assert entity.entity_metadata is None
        assert entity.embedding_vector is None
        assert entity.primary_detection_id is None

    def test_entity_create_with_metadata(self) -> None:
        """Test creating EntityCreate with metadata."""
        entity = EntityCreate(
            entity_type=EntityTypeEnum.PERSON,
            entity_metadata={"clothing_color": "blue", "height": "tall"},
        )
        assert entity.entity_metadata == {"clothing_color": "blue", "height": "tall"}

    def test_entity_create_with_embedding(self) -> None:
        """Test creating EntityCreate with embedding vector."""
        from backend.api.schemas.entities import EmbeddingVectorData

        entity = EntityCreate(
            entity_type=EntityTypeEnum.PERSON,
            embedding_vector=EmbeddingVectorData(
                vector=[0.1, 0.2, 0.3], model="clip", dimension=768
            ),
        )
        assert entity.embedding_vector is not None
        assert entity.embedding_vector.model == "clip"
        assert entity.embedding_vector.dimension == 768


class TestEntityUpdate:
    """Tests for EntityUpdate schema."""

    def test_entity_update_all_none(self) -> None:
        """Test EntityUpdate with all fields None."""
        entity = EntityUpdate()
        assert entity.entity_type is None
        assert entity.embedding_vector is None
        assert entity.entity_metadata is None
        assert entity.primary_detection_id is None

    def test_entity_update_partial(self) -> None:
        """Test EntityUpdate with some fields set."""
        entity = EntityUpdate(
            entity_type=EntityTypeEnum.VEHICLE,
            entity_metadata={"make": "Toyota", "color": "silver"},
        )
        assert entity.entity_type == EntityTypeEnum.VEHICLE
        assert entity.entity_metadata == {"make": "Toyota", "color": "silver"}
        assert entity.embedding_vector is None


class TestEntityRead:
    """Tests for EntityRead schema."""

    def test_entity_read_from_model(self) -> None:
        """Test EntityRead.from_attributes with Entity model."""
        # Create a mock Entity
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            trust_status="unknown",
            first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            detection_count=5,
            entity_metadata={"clothing_color": "blue"},
        )

        # Convert to EntityRead using from_attributes
        entity_read = EntityRead.model_validate(entity)

        assert entity_read.id == entity.id
        assert entity_read.entity_type == entity.entity_type
        assert entity_read.trust_status.value == entity.trust_status
        assert entity_read.first_seen_at == entity.first_seen_at
        assert entity_read.last_seen_at == entity.last_seen_at
        assert entity_read.detection_count == 5
        assert entity_read.entity_metadata == {"clothing_color": "blue"}

    def test_entity_read_with_embedding(self) -> None:
        """Test EntityRead with embedding vector."""
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            trust_status="unknown",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            detection_count=1,
            embedding_vector={"vector": [0.1, 0.2], "model": "clip", "dimension": 2},
        )

        entity_read = EntityRead.model_validate(entity)

        assert entity_read.embedding_vector is not None
        assert entity_read.embedding_vector["model"] == "clip"


class TestEntitySummary:
    """Tests for EntitySummary schema."""

    def test_entity_summary_minimal(self) -> None:
        """Test creating EntitySummary with minimal fields."""
        summary = EntitySummary(
            id="entity_001",
            entity_type="person",
            first_seen=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            last_seen=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            appearance_count=5,
        )

        assert summary.id == "entity_001"
        assert summary.entity_type == "person"
        assert summary.appearance_count == 5
        assert summary.cameras_seen == []
        assert summary.thumbnail_url is None

    def test_entity_summary_with_cameras(self) -> None:
        """Test EntitySummary with cameras_seen."""
        summary = EntitySummary(
            id="entity_001",
            entity_type="person",
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            appearance_count=3,
            cameras_seen=["front_door", "backyard"],
            thumbnail_url="/api/detections/123/image",
        )

        assert len(summary.cameras_seen) == 2
        assert "front_door" in summary.cameras_seen
        assert "backyard" in summary.cameras_seen
        assert summary.thumbnail_url == "/api/detections/123/image"

    def test_entity_summary_appearance_count_validation(self) -> None:
        """Test that appearance_count must be >= 0."""
        with pytest.raises(ValidationError):
            EntitySummary(
                id="entity_001",
                entity_type="person",
                first_seen=datetime.now(UTC),
                last_seen=datetime.now(UTC),
                appearance_count=-1,
            )


class TestEntityDetail:
    """Tests for EntityDetail schema."""

    def test_entity_detail_inherits_summary(self) -> None:
        """Test that EntityDetail has all EntitySummary fields."""
        detail = EntityDetail(
            id="entity_001",
            entity_type="person",
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            appearance_count=2,
            cameras_seen=["front_door"],
            thumbnail_url="/api/detections/123/image",
            appearances=[],
        )

        assert detail.id == "entity_001"
        assert detail.entity_type == "person"
        assert detail.appearance_count == 2
        assert len(detail.appearances) == 0

    def test_entity_detail_with_appearances(self) -> None:
        """Test EntityDetail with appearance list."""
        appearances = [
            EntityAppearance(
                detection_id="det_001",
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            ),
            EntityAppearance(
                detection_id="det_002",
                camera_id="backyard",
                timestamp=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            ),
        ]

        detail = EntityDetail(
            id="entity_001",
            entity_type="person",
            first_seen=appearances[0].timestamp,
            last_seen=appearances[1].timestamp,
            appearance_count=2,
            appearances=appearances,
        )

        assert len(detail.appearances) == 2
        assert detail.appearances[0].camera_id == "front_door"
        assert detail.appearances[1].camera_id == "backyard"


class TestEntityAppearance:
    """Tests for EntityAppearance schema."""

    def test_entity_appearance_minimal(self) -> None:
        """Test creating EntityAppearance with minimal fields."""
        appearance = EntityAppearance(
            detection_id="det_001",
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        )

        assert appearance.detection_id == "det_001"
        assert appearance.camera_id == "front_door"
        assert appearance.camera_name is None
        assert appearance.thumbnail_url is None
        assert appearance.similarity_score is None
        assert appearance.attributes == {}

    def test_entity_appearance_with_attributes(self) -> None:
        """Test EntityAppearance with attributes."""
        appearance = EntityAppearance(
            detection_id="det_001",
            camera_id="front_door",
            camera_name="Front Door",
            timestamp=datetime.now(UTC),
            thumbnail_url="/api/detections/1/image",
            similarity_score=0.92,
            attributes={"clothing": "blue jacket", "carrying": "backpack"},
        )

        assert appearance.camera_name == "Front Door"
        assert appearance.similarity_score == 0.92
        assert appearance.attributes["clothing"] == "blue jacket"

    def test_entity_appearance_similarity_score_validation(self) -> None:
        """Test that similarity_score must be between 0 and 1."""
        # Valid score
        appearance = EntityAppearance(
            detection_id="det_001",
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            similarity_score=0.85,
        )
        assert appearance.similarity_score == 0.85

        # Invalid score (too high)
        with pytest.raises(ValidationError):
            EntityAppearance(
                detection_id="det_001",
                camera_id="front_door",
                timestamp=datetime.now(UTC),
                similarity_score=1.5,
            )

        # Invalid score (negative)
        with pytest.raises(ValidationError):
            EntityAppearance(
                detection_id="det_001",
                camera_id="front_door",
                timestamp=datetime.now(UTC),
                similarity_score=-0.1,
            )


class TestEntitySchemaConversions:
    """Tests for schema conversion methods."""

    def test_entity_model_to_read_schema(self) -> None:
        """Test converting Entity model to EntityRead schema."""
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            trust_status="trusted",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            detection_count=3,
            entity_metadata={"clothing_color": "blue"},
        )

        entity_read = EntityRead.model_validate(entity)

        assert entity_read.id == entity.id
        assert entity_read.entity_type == entity.entity_type
        assert entity_read.trust_status.value == "trusted"
        assert entity_read.detection_count == 3

    def test_entity_read_serialization(self) -> None:
        """Test EntityRead JSON serialization."""
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            trust_status="untrusted",
            first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            detection_count=1,
        )

        entity_read = EntityRead.model_validate(entity)
        json_data = entity_read.model_dump(mode="json")

        assert json_data["id"] == str(entity.id)
        assert json_data["entity_type"] == "person"
        assert json_data["trust_status"] == "untrusted"
        assert json_data["detection_count"] == 1

    def test_entity_create_to_model(self) -> None:
        """Test using EntityCreate to create Entity model."""
        entity_create = EntityCreate(
            entity_type=EntityTypeEnum.PERSON,
            entity_metadata={"clothing_color": "red"},
            primary_detection_id=123,
        )

        # Create Entity from EntityCreate data
        entity = Entity(
            id=uuid4(),
            entity_type=entity_create.entity_type.value,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            detection_count=1,
            entity_metadata=entity_create.entity_metadata,
            primary_detection_id=entity_create.primary_detection_id,
        )

        assert entity.entity_type == "person"
        assert entity.entity_metadata == {"clothing_color": "red"}
        assert entity.primary_detection_id == 123


class TestNullMetadataHandling:
    """Tests for handling null/None metadata."""

    def test_entity_read_with_null_metadata(self) -> None:
        """Test EntityRead with None entity_metadata."""
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            trust_status="unknown",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            detection_count=1,
            entity_metadata=None,
        )

        entity_read = EntityRead.model_validate(entity)
        assert entity_read.entity_metadata is None
        assert entity_read.trust_status.value == "unknown"

    def test_entity_create_with_null_metadata(self) -> None:
        """Test EntityCreate with None entity_metadata."""
        entity = EntityCreate(
            entity_type=EntityTypeEnum.PERSON,
            entity_metadata=None,
        )

        assert entity.entity_metadata is None

    def test_entity_update_preserves_none(self) -> None:
        """Test that EntityUpdate can have None values."""
        entity = EntityUpdate(
            entity_type=None,
            entity_metadata=None,
        )

        assert entity.entity_type is None
        assert entity.entity_metadata is None
