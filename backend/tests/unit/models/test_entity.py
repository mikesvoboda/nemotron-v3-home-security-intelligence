"""Unit tests for Entity model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Helper methods (update_seen, set_embedding, get_embedding_vector, etc.)
- Factory method from_detection
- Property-based tests for field values

Related Linear issue: NEM-2210
"""

import uuid
from datetime import UTC, datetime, timedelta

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
entity_types = st.sampled_from([e.value for e in EntityType])

# Strategy for valid embedding vectors (common dimensions: 128, 256, 512, 768)
embedding_vectors = st.lists(
    st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    min_size=128,
    max_size=768,
)

# Strategy for valid detection counts
detection_counts = st.integers(min_value=0, max_value=10000)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_entity():
    """Create a sample entity for testing."""
    return Entity(
        id=uuid.uuid4(),
        entity_type=EntityType.PERSON.value,
        detection_count=5,
    )


@pytest.fixture
def entity_with_embedding():
    """Create an entity with embedding vector for testing."""
    entity = Entity(
        id=uuid.uuid4(),
        entity_type=EntityType.PERSON.value,
        detection_count=3,
    )
    entity.set_embedding(
        vector=[0.1, 0.2, 0.3] * 43,  # 129 floats
        model="clip",
    )
    return entity


@pytest.fixture
def minimal_entity():
    """Create an entity with only required fields."""
    return Entity()


# =============================================================================
# Entity Model Initialization Tests
# =============================================================================


class TestEntityModelInitialization:
    """Tests for Entity model initialization."""

    def test_entity_creation_minimal(self, minimal_entity):
        """Test creating an entity with minimal fields.

        Note: SQLAlchemy column defaults (like UUID, datetime) are applied at
        database flush time, not at instantiation time. For unit tests without
        a database, we verify the defaults are defined on the column.
        """
        # Default values are applied at flush time, so id may be None
        # We verify the column has a default defined
        from sqlalchemy import inspect

        mapper = inspect(Entity)
        id_col = mapper.columns["id"]
        assert id_col.default is not None  # Has a default function

    def test_entity_creation_with_fields(self, sample_entity):
        """Test creating an entity with all fields populated."""
        assert sample_entity.id is not None
        assert sample_entity.entity_type == EntityType.PERSON.value
        assert sample_entity.detection_count == 5

    def test_entity_uuid_generation(self):
        """Test that UUID default is properly defined on the column.

        Note: SQLAlchemy column defaults are applied at database flush time.
        For unit tests, we verify the default is configured on the column.
        """
        from sqlalchemy import inspect

        mapper = inspect(Entity)
        id_col = mapper.columns["id"]

        # Verify the column has a default function set
        assert id_col.default is not None
        # The default callable should be uuid4 (verify by name)
        assert id_col.default.arg.__name__ == "uuid4"

    def test_entity_default_timestamps(self):
        """Test that timestamp defaults are properly defined on columns.

        Note: SQLAlchemy column defaults are applied at database flush time.
        For unit tests, we verify the defaults are configured on the columns.
        """
        from sqlalchemy import inspect

        mapper = inspect(Entity)
        first_seen_col = mapper.columns["first_seen_at"]
        last_seen_col = mapper.columns["last_seen_at"]

        # Verify the columns have default functions set
        assert first_seen_col.default is not None
        assert last_seen_col.default is not None

        # Verify the defaults are callable (lambda functions)
        assert callable(first_seen_col.default.arg)
        assert callable(last_seen_col.default.arg)

    def test_entity_optional_fields_default_to_none(self, minimal_entity):
        """Test that optional fields default to None."""
        assert minimal_entity.embedding_vector is None
        assert minimal_entity.entity_metadata is None
        assert minimal_entity.primary_detection_id is None


# =============================================================================
# Entity Type Tests
# =============================================================================


class TestEntityType:
    """Tests for entity type handling."""

    def test_entity_type_person(self):
        """Test entity with person type."""
        entity = Entity(entity_type=EntityType.PERSON.value)
        assert entity.entity_type == "person"

    def test_entity_type_vehicle(self):
        """Test entity with vehicle type."""
        entity = Entity(entity_type=EntityType.VEHICLE.value)
        assert entity.entity_type == "vehicle"

    def test_entity_type_animal(self):
        """Test entity with animal type."""
        entity = Entity(entity_type=EntityType.ANIMAL.value)
        assert entity.entity_type == "animal"

    def test_entity_type_package(self):
        """Test entity with package type."""
        entity = Entity(entity_type=EntityType.PACKAGE.value)
        assert entity.entity_type == "package"

    def test_entity_type_other(self):
        """Test entity with other type."""
        entity = Entity(entity_type=EntityType.OTHER.value)
        assert entity.entity_type == "other"

    def test_entity_type_enum_str_conversion(self):
        """Test EntityType enum string conversion."""
        assert str(EntityType.PERSON) == "person"
        assert str(EntityType.VEHICLE) == "vehicle"
        assert str(EntityType.ANIMAL) == "animal"


# =============================================================================
# Embedding Vector Tests
# =============================================================================


class TestEntityEmbedding:
    """Tests for entity embedding operations."""

    def test_set_embedding(self):
        """Test setting embedding vector."""
        entity = Entity()
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        entity.set_embedding(vector, model="clip")

        assert entity.embedding_vector is not None
        assert entity.embedding_vector["vector"] == vector
        assert entity.embedding_vector["model"] == "clip"
        assert entity.embedding_vector["dimension"] == 5

    def test_set_embedding_with_explicit_dimension(self):
        """Test setting embedding with explicit dimension."""
        entity = Entity()
        vector = [0.1, 0.2, 0.3]
        entity.set_embedding(vector, model="reid", dimension=512)

        assert entity.embedding_vector["dimension"] == 512

    def test_get_embedding_vector(self, entity_with_embedding):
        """Test getting embedding vector."""
        vector = entity_with_embedding.get_embedding_vector()
        assert vector is not None
        assert isinstance(vector, list)
        assert len(vector) == 129  # 0.1, 0.2, 0.3 repeated 43 times

    def test_get_embedding_vector_none(self, minimal_entity):
        """Test getting embedding vector when not set."""
        assert minimal_entity.get_embedding_vector() is None

    def test_get_embedding_model(self, entity_with_embedding):
        """Test getting embedding model."""
        model = entity_with_embedding.get_embedding_model()
        assert model == "clip"

    def test_get_embedding_model_none(self, minimal_entity):
        """Test getting embedding model when not set."""
        assert minimal_entity.get_embedding_model() is None

    def test_set_embedding_different_models(self):
        """Test setting embeddings from different models."""
        entity = Entity()

        # CLIP model
        entity.set_embedding([0.1] * 512, model="clip")
        assert entity.get_embedding_model() == "clip"

        # ReID model
        entity.set_embedding([0.2] * 256, model="torchreid")
        assert entity.get_embedding_model() == "torchreid"


# =============================================================================
# Update Methods Tests
# =============================================================================


class TestEntityUpdateMethods:
    """Tests for entity update helper methods."""

    def test_update_seen_increments_count(self):
        """Test that update_seen increments detection count."""
        entity = Entity(detection_count=0)
        entity.update_seen()
        assert entity.detection_count == 1

        entity.update_seen()
        assert entity.detection_count == 2

    def test_update_seen_updates_timestamp(self):
        """Test that update_seen updates last_seen_at."""
        entity = Entity()
        original_time = entity.last_seen_at

        # Update with specific timestamp
        new_time = datetime.now(UTC) + timedelta(hours=1)
        entity.update_seen(timestamp=new_time)

        assert entity.last_seen_at == new_time

    def test_update_seen_default_timestamp(self):
        """Test that update_seen uses current time by default."""
        entity = Entity()
        before = datetime.now(UTC)
        entity.update_seen()
        after = datetime.now(UTC)

        assert before <= entity.last_seen_at <= after

    def test_update_seen_handles_none_count(self):
        """Test update_seen handles None detection_count gracefully."""
        entity = Entity()
        entity.detection_count = None  # type: ignore[assignment]
        entity.update_seen()
        assert entity.detection_count == 1


# =============================================================================
# Factory Method Tests
# =============================================================================


class TestEntityFactoryMethod:
    """Tests for Entity.from_detection factory method."""

    def test_from_detection_basic(self):
        """Test creating entity from detection."""
        entity = Entity.from_detection(
            entity_type=EntityType.PERSON,
            detection_id=123,
        )

        assert entity.entity_type == "person"
        assert entity.primary_detection_id == 123
        assert entity.detection_count == 1

    def test_from_detection_with_embedding(self):
        """Test creating entity from detection with embedding."""
        embedding = [0.1] * 512
        entity = Entity.from_detection(
            entity_type=EntityType.VEHICLE,
            detection_id=456,
            embedding=embedding,
            model="clip",
        )

        assert entity.entity_type == "vehicle"
        assert entity.get_embedding_vector() == embedding
        assert entity.get_embedding_model() == "clip"

    def test_from_detection_with_metadata(self):
        """Test creating entity from detection with metadata."""
        metadata = {"clothing_color": "red", "height_estimate": 175}
        entity = Entity.from_detection(
            entity_type=EntityType.PERSON,
            entity_metadata=metadata,
        )

        assert entity.entity_metadata == metadata

    def test_from_detection_string_entity_type(self):
        """Test creating entity with string entity type."""
        entity = Entity.from_detection(entity_type="vehicle")

        assert entity.entity_type == "vehicle"

    def test_from_detection_enum_entity_type(self):
        """Test creating entity with enum entity type."""
        entity = Entity.from_detection(entity_type=EntityType.ANIMAL)

        assert entity.entity_type == "animal"


# =============================================================================
# Entity Repr Tests
# =============================================================================


class TestEntityRepr:
    """Tests for Entity string representation."""

    def test_entity_repr_contains_class_name(self, sample_entity):
        """Test repr contains class name."""
        repr_str = repr(sample_entity)
        assert "Entity" in repr_str

    def test_entity_repr_contains_id(self, sample_entity):
        """Test repr contains entity id."""
        repr_str = repr(sample_entity)
        assert "id=" in repr_str

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
    """Tests for Entity table arguments (indexes, constraints)."""

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

    def test_entity_has_first_seen_at_index(self):
        """Test Entity has first_seen_at index defined."""
        indexes = Entity.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_entities_first_seen_at" in index_names

    def test_entity_has_last_seen_at_index(self):
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


# =============================================================================
# Entity Constraints Tests
# =============================================================================


class TestEntityConstraints:
    """Tests for Entity check constraints."""

    def test_entity_has_entity_type_constraint(self):
        """Test Entity has entity_type CHECK constraint defined."""
        from sqlalchemy import CheckConstraint

        constraints = [arg for arg in Entity.__table_args__ if isinstance(arg, CheckConstraint)]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_entities_entity_type" in constraint_names

    def test_entity_has_detection_count_constraint(self):
        """Test Entity has detection_count CHECK constraint defined."""
        from sqlalchemy import CheckConstraint

        constraints = [arg for arg in Entity.__table_args__ if isinstance(arg, CheckConstraint)]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_entities_detection_count" in constraint_names


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
        result = entity.get_embedding_vector()

        assert result is not None
        assert len(result) == len(vector)
        # Allow for floating point precision
        for orig, stored in zip(vector, result, strict=True):
            assert abs(orig - stored) < 1e-10

    @given(
        first_seen=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(UTC),
        ),
        last_seen=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(UTC),
        ),
    )
    @settings(max_examples=20)
    def test_timestamp_roundtrip(self, first_seen: datetime, last_seen: datetime):
        """Property: Timestamps roundtrip correctly."""
        entity = Entity(
            first_seen_at=first_seen,
            last_seen_at=last_seen,
        )
        assert entity.first_seen_at == first_seen
        assert entity.last_seen_at == last_seen


# =============================================================================
# Entity Relationship Tests
# =============================================================================


class TestEntityRelationships:
    """Tests for Entity relationship definitions."""

    def test_entity_has_primary_detection_relationship(self, sample_entity):
        """Test entity has primary_detection relationship defined."""
        assert hasattr(sample_entity, "primary_detection")
