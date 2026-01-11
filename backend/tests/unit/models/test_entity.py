"""Unit tests for Entity model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- EntityType enum
- Embedding vector operations
- Factory methods
- Table arguments and indexes
"""

import uuid
from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.entity import Entity
from backend.models.enums import EntityType

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid entity types
entity_types = st.sampled_from(["person", "vehicle", "animal", "package", "other"])

# Strategy for valid embedding vectors (list of floats)
embedding_vectors = st.lists(
    st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=128,
    max_size=512,
)

# Strategy for valid detection counts (non-negative integers)
detection_counts = st.integers(min_value=0, max_value=100000)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_entity():
    """Create a sample entity for testing."""
    return Entity(
        entity_type="person",
        detection_count=5,
    )


@pytest.fixture
def entity_with_embedding():
    """Create an entity with an embedding vector."""
    entity = Entity(
        entity_type="vehicle",
        detection_count=3,
    )
    entity.set_embedding([0.1, 0.2, 0.3, 0.4, 0.5], model="clip", dimension=5)
    return entity


@pytest.fixture
def entity_with_metadata():
    """Create an entity with metadata."""
    return Entity(
        entity_type="person",
        detection_count=1,
        entity_metadata={
            "clothing_color": "blue",
            "carrying": "backpack",
            "hair_color": "brown",
        },
    )


# =============================================================================
# EntityType Enum Tests
# =============================================================================


class TestEntityTypeEnum:
    """Tests for EntityType enumeration."""

    def test_entity_type_person(self):
        """Test EntityType.PERSON value."""
        assert EntityType.PERSON.value == "person"

    def test_entity_type_vehicle(self):
        """Test EntityType.VEHICLE value."""
        assert EntityType.VEHICLE.value == "vehicle"

    def test_entity_type_animal(self):
        """Test EntityType.ANIMAL value."""
        assert EntityType.ANIMAL.value == "animal"

    def test_entity_type_package(self):
        """Test EntityType.PACKAGE value."""
        assert EntityType.PACKAGE.value == "package"

    def test_entity_type_other(self):
        """Test EntityType.OTHER value."""
        assert EntityType.OTHER.value == "other"

    def test_entity_type_str(self):
        """Test EntityType string conversion."""
        assert str(EntityType.PERSON) == "person"
        assert str(EntityType.VEHICLE) == "vehicle"

    def test_entity_type_is_str_enum(self):
        """Test that EntityType inherits from str."""
        assert isinstance(EntityType.PERSON, str)


# =============================================================================
# Entity Model Initialization Tests
# =============================================================================


class TestEntityModelInitialization:
    """Tests for Entity model initialization."""

    def test_entity_creation_minimal(self):
        """Test creating an entity with minimal fields.

        Note: SQLAlchemy defaults are applied at database flush time,
        not at object construction. So entity_type and detection_count
        will be None until flushed, unless explicitly set.
        """
        entity = Entity()
        # Defaults are not applied until flush, so they are None
        assert entity.entity_type is None
        assert entity.detection_count is None

        # Can create with explicit values
        entity_with_values = Entity(entity_type="person", detection_count=0)
        assert entity_with_values.entity_type == "person"
        assert entity_with_values.detection_count == 0

    def test_entity_with_type(self, sample_entity):
        """Test entity with explicit type."""
        assert sample_entity.entity_type == "person"
        assert sample_entity.detection_count == 5

    def test_entity_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        entity = Entity()
        assert entity.embedding_vector is None
        assert entity.entity_metadata is None
        assert entity.primary_detection_id is None

    def test_entity_uuid_generation(self):
        """Test that entity generates UUID on creation."""
        entity = Entity()
        # When setting a default, SQLAlchemy sets it on flush, but we can
        # manually test the default is callable
        from sqlalchemy import inspect

        mapper = inspect(Entity)
        id_col = mapper.columns["id"]
        assert id_col.default is not None

    def test_entity_with_all_types(self):
        """Test entity creation with all valid types."""
        for entity_type in ["person", "vehicle", "animal", "package", "other"]:
            entity = Entity(entity_type=entity_type)
            assert entity.entity_type == entity_type

    def test_entity_with_enum_type(self):
        """Test entity creation using EntityType enum."""
        entity = Entity(entity_type=EntityType.VEHICLE.value)
        assert entity.entity_type == "vehicle"


# =============================================================================
# Entity Embedding Tests
# =============================================================================


class TestEntityEmbedding:
    """Tests for Entity embedding operations."""

    def test_set_embedding(self):
        """Test setting an embedding vector."""
        entity = Entity()
        vector = [0.1, 0.2, 0.3, 0.4]
        entity.set_embedding(vector, model="clip")

        assert entity.embedding_vector is not None
        assert entity.embedding_vector["vector"] == vector
        assert entity.embedding_vector["model"] == "clip"
        assert entity.embedding_vector["dimension"] == 4

    def test_set_embedding_custom_dimension(self):
        """Test setting embedding with custom dimension."""
        entity = Entity()
        vector = [0.1, 0.2, 0.3]
        entity.set_embedding(vector, model="reid", dimension=512)

        assert entity.embedding_vector["dimension"] == 512

    def test_get_embedding_vector(self, entity_with_embedding):
        """Test retrieving the embedding vector."""
        vector = entity_with_embedding.get_embedding_vector()
        assert vector == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_get_embedding_vector_none(self):
        """Test getting embedding vector when not set."""
        entity = Entity()
        assert entity.get_embedding_vector() is None

    def test_get_embedding_model(self, entity_with_embedding):
        """Test retrieving the embedding model name."""
        model = entity_with_embedding.get_embedding_model()
        assert model == "clip"

    def test_get_embedding_model_none(self):
        """Test getting embedding model when not set."""
        entity = Entity()
        assert entity.get_embedding_model() is None


# =============================================================================
# Entity Metadata Tests
# =============================================================================


class TestEntityMetadata:
    """Tests for Entity metadata field."""

    def test_entity_metadata_dict(self, entity_with_metadata):
        """Test entity with metadata dictionary."""
        assert entity_with_metadata.entity_metadata["clothing_color"] == "blue"
        assert entity_with_metadata.entity_metadata["carrying"] == "backpack"

    def test_entity_metadata_empty(self):
        """Test entity with empty metadata."""
        entity = Entity(entity_metadata={})
        assert entity.entity_metadata == {}

    def test_entity_metadata_nested(self):
        """Test entity with nested metadata."""
        entity = Entity(
            entity_metadata={
                "vehicle": {
                    "make": "Toyota",
                    "model": "Camry",
                    "year": 2023,
                },
                "color": "silver",
            }
        )
        assert entity.entity_metadata["vehicle"]["make"] == "Toyota"


# =============================================================================
# Entity Update Methods Tests
# =============================================================================


class TestEntityUpdateMethods:
    """Tests for Entity update methods."""

    def test_update_seen_increments_count(self):
        """Test that update_seen increments detection count."""
        entity = Entity(detection_count=5)
        entity.update_seen()
        assert entity.detection_count == 6

    def test_update_seen_updates_timestamp(self):
        """Test that update_seen updates last_seen_at."""
        from datetime import timedelta

        entity = Entity(detection_count=0)
        old_time = datetime.now(UTC) - timedelta(seconds=1)
        entity.last_seen_at = old_time
        entity.update_seen()
        assert entity.last_seen_at >= old_time

    def test_update_seen_custom_timestamp(self):
        """Test update_seen with custom timestamp."""
        entity = Entity(detection_count=0)
        custom_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        entity.update_seen(timestamp=custom_time)
        assert entity.last_seen_at == custom_time


# =============================================================================
# Entity Factory Method Tests
# =============================================================================


class TestEntityFactoryMethods:
    """Tests for Entity factory methods."""

    def test_from_detection_basic(self):
        """Test creating entity from detection with minimal args."""
        entity = Entity.from_detection(entity_type="person")
        assert entity.entity_type == "person"
        assert entity.detection_count == 1

    def test_from_detection_with_enum(self):
        """Test creating entity using EntityType enum."""
        entity = Entity.from_detection(entity_type=EntityType.VEHICLE)
        assert entity.entity_type == "vehicle"

    def test_from_detection_with_detection_id(self):
        """Test creating entity with primary detection ID."""
        entity = Entity.from_detection(
            entity_type="person",
            detection_id=123,
        )
        assert entity.primary_detection_id == 123

    def test_from_detection_with_embedding(self):
        """Test creating entity with embedding vector."""
        vector = [0.1, 0.2, 0.3]
        entity = Entity.from_detection(
            entity_type="person",
            embedding=vector,
            model="clip",
        )
        assert entity.get_embedding_vector() == vector
        assert entity.get_embedding_model() == "clip"

    def test_from_detection_with_metadata(self):
        """Test creating entity with metadata."""
        metadata = {"clothing": "red shirt"}
        entity = Entity.from_detection(
            entity_type="person",
            entity_metadata=metadata,
        )
        assert entity.entity_metadata == metadata


# =============================================================================
# Entity Repr Tests
# =============================================================================


class TestEntityRepr:
    """Tests for Entity string representation."""

    def test_entity_repr_contains_class_name(self, sample_entity):
        """Test repr contains class name."""
        repr_str = repr(sample_entity)
        assert "Entity" in repr_str

    def test_entity_repr_contains_entity_type(self, sample_entity):
        """Test repr contains entity_type."""
        repr_str = repr(sample_entity)
        assert "person" in repr_str

    def test_entity_repr_contains_detection_count(self, sample_entity):
        """Test repr contains detection_count."""
        repr_str = repr(sample_entity)
        assert "detection_count=5" in repr_str

    def test_entity_repr_format(self, sample_entity):
        """Test repr has expected format."""
        repr_str = repr(sample_entity)
        assert repr_str.startswith("<Entity(")
        assert repr_str.endswith(")>")


# =============================================================================
# Entity Table Args Tests
# =============================================================================


class TestEntityTableArgs:
    """Tests for Entity table arguments (indexes and constraints)."""

    def test_entity_has_table_args(self):
        """Test Entity model has __table_args__."""
        assert hasattr(Entity, "__table_args__")

    def test_entity_tablename(self):
        """Test Entity has correct table name."""
        assert Entity.__tablename__ == "entities"

    def test_entity_has_entity_type_index(self):
        """Test Entity has entity_type index defined."""
        indexes = Entity.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_entities_entity_type" in index_names

    def test_entity_has_first_seen_index(self):
        """Test Entity has first_seen_at index defined."""
        indexes = Entity.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_entities_first_seen_at" in index_names

    def test_entity_has_last_seen_index(self):
        """Test Entity has last_seen_at index defined."""
        indexes = Entity.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_entities_last_seen_at" in index_names

    def test_entity_has_type_last_seen_composite_index(self):
        """Test Entity has entity_type + last_seen_at composite index."""
        indexes = Entity.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_entities_type_last_seen" in index_names

    def test_entity_has_metadata_gin_index(self):
        """Test Entity has GIN index on entity_metadata."""
        indexes = Entity.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "ix_entities_entity_metadata_gin" in index_names

    def test_entity_metadata_gin_index_uses_gin(self):
        """Test entity_metadata GIN index uses gin postgresql_using."""
        from sqlalchemy import Index

        indexes = Entity.__table_args__
        gin_index = None
        for idx in indexes:
            if isinstance(idx, Index) and idx.name == "ix_entities_entity_metadata_gin":
                gin_index = idx
                break
        assert gin_index is not None
        assert gin_index.kwargs.get("postgresql_using") == "gin"

    def test_entity_has_entity_type_check_constraint(self):
        """Test Entity has CHECK constraint for entity_type."""
        from sqlalchemy import CheckConstraint

        constraints = Entity.__table_args__
        check_names = [c.name for c in constraints if isinstance(c, CheckConstraint) and c.name]
        assert "ck_entities_entity_type" in check_names

    def test_entity_has_detection_count_check_constraint(self):
        """Test Entity has CHECK constraint for detection_count."""
        from sqlalchemy import CheckConstraint

        constraints = Entity.__table_args__
        check_names = [c.name for c in constraints if isinstance(c, CheckConstraint) and c.name]
        assert "ck_entities_detection_count" in check_names


# =============================================================================
# Entity Relationship Tests
# =============================================================================


class TestEntityRelationships:
    """Tests for Entity relationship definitions."""

    def test_entity_has_primary_detection_relationship(self):
        """Test entity has primary_detection relationship defined."""
        entity = Entity()
        assert hasattr(entity, "primary_detection")


# =============================================================================
# Property-based Tests
# =============================================================================


class TestEntityProperties:
    """Property-based tests for Entity model."""

    @given(entity_type=entity_types)
    @settings(max_examples=20)
    def test_entity_type_roundtrip(self, entity_type: str):
        """Property: Entity type values roundtrip correctly."""
        entity = Entity(entity_type=entity_type)
        assert entity.entity_type == entity_type

    @given(count=detection_counts)
    @settings(max_examples=50)
    def test_detection_count_roundtrip(self, count: int):
        """Property: Detection count values roundtrip correctly."""
        entity = Entity(detection_count=count)
        assert entity.detection_count == count

    @given(vector=embedding_vectors)
    @settings(max_examples=20)
    def test_embedding_vector_roundtrip(self, vector: list[float]):
        """Property: Embedding vectors roundtrip correctly."""
        entity = Entity()
        entity.set_embedding(vector, model="test")
        retrieved = entity.get_embedding_vector()
        assert len(retrieved) == len(vector)
        for i, (expected, actual) in enumerate(zip(vector, retrieved, strict=True)):
            assert abs(expected - actual) < 1e-10, f"Mismatch at index {i}"

    @given(
        entity_type=entity_types,
        count=st.integers(min_value=0, max_value=1000),
    )
    @settings(max_examples=30)
    def test_combined_fields_roundtrip(self, entity_type: str, count: int):
        """Property: Combined fields roundtrip correctly."""
        entity = Entity(entity_type=entity_type, detection_count=count)
        assert entity.entity_type == entity_type
        assert entity.detection_count == count


# =============================================================================
# Entity UUID Tests
# =============================================================================


class TestEntityUUID:
    """Tests for Entity UUID primary key."""

    def test_entity_accepts_uuid(self):
        """Test entity accepts UUID for id."""
        test_uuid = uuid.uuid4()
        entity = Entity(id=test_uuid)
        assert entity.id == test_uuid

    def test_entity_id_is_uuid_type(self):
        """Test entity id column is UUID type."""
        from sqlalchemy import inspect
        from sqlalchemy.dialects.postgresql import UUID

        mapper = inspect(Entity)
        id_col = mapper.columns["id"]
        assert isinstance(id_col.type, UUID)
