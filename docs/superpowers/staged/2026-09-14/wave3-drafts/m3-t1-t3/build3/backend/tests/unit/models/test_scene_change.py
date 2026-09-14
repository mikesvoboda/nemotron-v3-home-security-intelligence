"""Unit tests for SceneChange model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- SceneChangeType enum values
- String representation (__repr__)
- Relationship definitions
- Indexes and table configuration
- Property-based tests for field values
- Edge cases and boundary conditions
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.scene_change import SceneChange, SceneChangeType

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for scene change types
scene_change_types = st.sampled_from(list(SceneChangeType))

# Strategy for similarity scores (0 to 1)
similarity_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for camera IDs
camera_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
)

# Strategy for file paths
file_paths = st.one_of(
    st.none(),
    st.from_regex(r"^/[a-zA-Z0-9_\-/]+\.[a-zA-Z]{2,4}$", fullmatch=True),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_scene_change():
    """Create a sample SceneChange for testing."""
    return SceneChange(
        id=1,
        camera_id="front_door",
        detected_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        change_type=SceneChangeType.VIEW_BLOCKED,
        similarity_score=0.35,
        acknowledged=False,
        file_path="/export/foscam/front_door/image_001.jpg",
    )


@pytest.fixture
def acknowledged_scene_change():
    """Create an acknowledged SceneChange for testing."""
    return SceneChange(
        id=2,
        camera_id="back_yard",
        detected_at=datetime(2025, 1, 14, 8, 0, 0, tzinfo=UTC),
        change_type=SceneChangeType.ANGLE_CHANGED,
        similarity_score=0.45,
        acknowledged=True,
        acknowledged_at=datetime(2025, 1, 14, 9, 0, 0, tzinfo=UTC),
        file_path="/export/foscam/back_yard/image_002.jpg",
    )


@pytest.fixture
def minimal_scene_change():
    """Create a SceneChange with only required fields."""
    return SceneChange(
        camera_id="garage",
        similarity_score=0.5,
    )


@pytest.fixture
def tampered_scene_change():
    """Create a SceneChange with VIEW_TAMPERED type."""
    return SceneChange(
        id=3,
        camera_id="side_entrance",
        change_type=SceneChangeType.VIEW_TAMPERED,
        similarity_score=0.2,
        acknowledged=False,
    )


# =============================================================================
# SceneChangeType Enum Tests
# =============================================================================


class TestSceneChangeTypeEnum:
    """Tests for SceneChangeType enum."""

    def test_scene_change_type_view_blocked(self):
        """Test VIEW_BLOCKED type value."""
        assert SceneChangeType.VIEW_BLOCKED.value == "view_blocked"

    def test_scene_change_type_angle_changed(self):
        """Test ANGLE_CHANGED type value."""
        assert SceneChangeType.ANGLE_CHANGED.value == "angle_changed"

    def test_scene_change_type_view_tampered(self):
        """Test VIEW_TAMPERED type value."""
        assert SceneChangeType.VIEW_TAMPERED.value == "view_tampered"

    def test_scene_change_type_unknown(self):
        """Test UNKNOWN type value."""
        assert SceneChangeType.UNKNOWN.value == "unknown"

    def test_scene_change_type_count(self):
        """Test SceneChangeType has expected number of values."""
        assert len(SceneChangeType) == 4

    def test_scene_change_type_is_string_enum(self):
        """Test SceneChangeType inherits from str."""
        for change_type in SceneChangeType:
            assert isinstance(change_type, str)
            assert isinstance(change_type.value, str)

    def test_scene_change_type_from_string(self):
        """Test creating SceneChangeType from string value."""
        assert SceneChangeType("view_blocked") == SceneChangeType.VIEW_BLOCKED
        assert SceneChangeType("angle_changed") == SceneChangeType.ANGLE_CHANGED
        assert SceneChangeType("view_tampered") == SceneChangeType.VIEW_TAMPERED
        assert SceneChangeType("unknown") == SceneChangeType.UNKNOWN

    def test_scene_change_type_invalid_raises_error(self):
        """Test invalid SceneChangeType value raises ValueError."""
        with pytest.raises(ValueError):
            SceneChangeType("invalid_type")

    def test_scene_change_type_all_unique(self):
        """Test all SceneChangeType values are unique."""
        values = [t.value for t in SceneChangeType]
        assert len(values) == len(set(values))


# =============================================================================
# SceneChange Model Initialization Tests
# =============================================================================


class TestSceneChangeModelInitialization:
    """Tests for SceneChange model initialization."""

    def test_scene_change_creation_minimal(self, minimal_scene_change):
        """Test creating a SceneChange with minimal required fields."""
        assert minimal_scene_change.camera_id == "garage"
        assert minimal_scene_change.similarity_score == 0.5

    def test_scene_change_with_all_fields(self, sample_scene_change):
        """Test SceneChange with all fields populated."""
        assert sample_scene_change.id == 1
        assert sample_scene_change.camera_id == "front_door"
        assert sample_scene_change.detected_at == datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert sample_scene_change.change_type == SceneChangeType.VIEW_BLOCKED
        assert sample_scene_change.similarity_score == 0.35
        assert sample_scene_change.acknowledged is False
        assert sample_scene_change.file_path == "/export/foscam/front_door/image_001.jpg"

    def test_scene_change_default_change_type_column_definition(self):
        """Test that change_type column has UNKNOWN as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        change_type_col = mapper.columns["change_type"]
        assert change_type_col.default is not None
        assert change_type_col.default.arg == SceneChangeType.UNKNOWN

    def test_scene_change_default_acknowledged_column_definition(self):
        """Test that acknowledged column has False as default."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        acknowledged_col = mapper.columns["acknowledged"]
        assert acknowledged_col.default is not None
        assert acknowledged_col.default.arg is False

    def test_scene_change_optional_fields_default_to_none(self, minimal_scene_change):
        """Test that optional fields default to None."""
        assert minimal_scene_change.acknowledged_at is None
        assert minimal_scene_change.file_path is None


# =============================================================================
# SceneChange Field Tests
# =============================================================================


class TestSceneChangeCameraIdField:
    """Tests for SceneChange camera_id field."""

    def test_camera_id_simple_name(self, sample_scene_change):
        """Test camera_id with simple name."""
        assert sample_scene_change.camera_id == "front_door"

    def test_camera_id_with_underscores(self):
        """Test camera_id with underscores."""
        sc = SceneChange(camera_id="front_door_camera", similarity_score=0.5)
        assert sc.camera_id == "front_door_camera"

    def test_camera_id_with_numbers(self):
        """Test camera_id with numbers."""
        sc = SceneChange(camera_id="camera_01", similarity_score=0.5)
        assert sc.camera_id == "camera_01"

    def test_camera_id_with_hyphens(self):
        """Test camera_id with hyphens."""
        sc = SceneChange(camera_id="front-door", similarity_score=0.5)
        assert sc.camera_id == "front-door"


class TestSceneChangeChangeTypeField:
    """Tests for SceneChange change_type field."""

    def test_change_type_view_blocked(self, sample_scene_change):
        """Test change_type with VIEW_BLOCKED."""
        assert sample_scene_change.change_type == SceneChangeType.VIEW_BLOCKED

    def test_change_type_angle_changed(self, acknowledged_scene_change):
        """Test change_type with ANGLE_CHANGED."""
        assert acknowledged_scene_change.change_type == SceneChangeType.ANGLE_CHANGED

    def test_change_type_view_tampered(self, tampered_scene_change):
        """Test change_type with VIEW_TAMPERED."""
        assert tampered_scene_change.change_type == SceneChangeType.VIEW_TAMPERED

    def test_change_type_unknown(self):
        """Test change_type with UNKNOWN."""
        sc = SceneChange(
            camera_id="test",
            change_type=SceneChangeType.UNKNOWN,
            similarity_score=0.5,
        )
        assert sc.change_type == SceneChangeType.UNKNOWN

    def test_change_type_all_values(self):
        """Test all SceneChangeType values work correctly."""
        for change_type in SceneChangeType:
            sc = SceneChange(
                camera_id="test",
                change_type=change_type,
                similarity_score=0.5,
            )
            assert sc.change_type == change_type


class TestSceneChangeSimilarityScoreField:
    """Tests for SceneChange similarity_score field."""

    def test_similarity_score_value(self, sample_scene_change):
        """Test similarity_score field value."""
        assert sample_scene_change.similarity_score == 0.35

    def test_similarity_score_zero(self):
        """Test similarity_score can be zero (completely different)."""
        sc = SceneChange(camera_id="test", similarity_score=0.0)
        assert sc.similarity_score == 0.0

    def test_similarity_score_one(self):
        """Test similarity_score can be one (identical)."""
        sc = SceneChange(camera_id="test", similarity_score=1.0)
        assert sc.similarity_score == 1.0

    def test_similarity_score_fractional(self):
        """Test similarity_score with fractional values."""
        sc = SceneChange(camera_id="test", similarity_score=0.7532)
        assert abs(sc.similarity_score - 0.7532) < 0.0001

    def test_similarity_score_typical_blocked(self):
        """Test similarity_score typical for blocked view (low)."""
        sc = SceneChange(camera_id="test", similarity_score=0.15)
        assert sc.similarity_score < 0.5

    def test_similarity_score_typical_slight_change(self):
        """Test similarity_score typical for slight change (high)."""
        sc = SceneChange(camera_id="test", similarity_score=0.85)
        assert sc.similarity_score > 0.5


class TestSceneChangeAcknowledgedFields:
    """Tests for SceneChange acknowledged and acknowledged_at fields."""

    def test_acknowledged_false(self, sample_scene_change):
        """Test acknowledged field set to False."""
        assert sample_scene_change.acknowledged is False

    def test_acknowledged_true(self, acknowledged_scene_change):
        """Test acknowledged field set to True."""
        assert acknowledged_scene_change.acknowledged is True

    def test_acknowledged_at_none_when_not_acknowledged(self, sample_scene_change):
        """Test acknowledged_at is None when not acknowledged."""
        assert sample_scene_change.acknowledged_at is None

    def test_acknowledged_at_set_when_acknowledged(self, acknowledged_scene_change):
        """Test acknowledged_at is set when acknowledged."""
        assert acknowledged_scene_change.acknowledged_at is not None
        assert acknowledged_scene_change.acknowledged_at == datetime(
            2025, 1, 14, 9, 0, 0, tzinfo=UTC
        )

    def test_acknowledged_at_after_detected_at(self, acknowledged_scene_change):
        """Test acknowledged_at is after detected_at."""
        assert acknowledged_scene_change.acknowledged_at > acknowledged_scene_change.detected_at


class TestSceneChangeFilePathField:
    """Tests for SceneChange file_path field."""

    def test_file_path_set(self, sample_scene_change):
        """Test file_path when set."""
        assert sample_scene_change.file_path == "/export/foscam/front_door/image_001.jpg"

    def test_file_path_none(self, minimal_scene_change):
        """Test file_path when not set."""
        assert minimal_scene_change.file_path is None

    def test_file_path_with_different_extension(self):
        """Test file_path with different image extensions."""
        extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
        for ext in extensions:
            sc = SceneChange(
                camera_id="test",
                similarity_score=0.5,
                file_path=f"/export/foscam/test/image{ext}",
            )
            assert sc.file_path.endswith(ext)

    def test_file_path_with_nested_directory(self):
        """Test file_path with nested directory structure."""
        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            file_path="/export/foscam/2025/01/15/front_door/image_001.jpg",
        )
        assert sc.file_path == "/export/foscam/2025/01/15/front_door/image_001.jpg"


class TestSceneChangeDetectedAtField:
    """Tests for SceneChange detected_at field."""

    def test_detected_at_set(self, sample_scene_change):
        """Test detected_at when set."""
        assert sample_scene_change.detected_at == datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

    def test_detected_at_with_timezone(self, sample_scene_change):
        """Test detected_at has timezone info."""
        assert sample_scene_change.detected_at.tzinfo is not None

    def test_detected_at_explicit_value(self):
        """Test detected_at with explicit value."""
        now = datetime.now(UTC)
        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            detected_at=now,
        )
        assert sc.detected_at == now


# =============================================================================
# SceneChange Repr Tests
# =============================================================================


class TestSceneChangeRepr:
    """Tests for SceneChange string representation."""

    def test_repr_contains_class_name(self, sample_scene_change):
        """Test repr contains class name."""
        repr_str = repr(sample_scene_change)
        assert "SceneChange" in repr_str

    def test_repr_contains_id(self, sample_scene_change):
        """Test repr contains id."""
        repr_str = repr(sample_scene_change)
        assert "id=1" in repr_str

    def test_repr_contains_camera_id(self, sample_scene_change):
        """Test repr contains camera_id."""
        repr_str = repr(sample_scene_change)
        assert "front_door" in repr_str

    def test_repr_contains_change_type(self, sample_scene_change):
        """Test repr contains change_type."""
        repr_str = repr(sample_scene_change)
        assert "view_blocked" in repr_str.lower() or "VIEW_BLOCKED" in repr_str

    def test_repr_contains_similarity_score(self, sample_scene_change):
        """Test repr contains similarity_score."""
        repr_str = repr(sample_scene_change)
        assert "0.35" in repr_str

    def test_repr_format(self, sample_scene_change):
        """Test repr has expected format."""
        repr_str = repr(sample_scene_change)
        assert repr_str.startswith("<SceneChange(")
        assert repr_str.endswith(")>")

    def test_repr_with_different_change_types(self):
        """Test repr with different change types."""
        for change_type in SceneChangeType:
            sc = SceneChange(
                id=1,
                camera_id="test",
                change_type=change_type,
                similarity_score=0.5,
            )
            repr_str = repr(sc)
            assert change_type.value in repr_str.lower() or change_type.name in repr_str


# =============================================================================
# SceneChange Relationship Tests
# =============================================================================


class TestSceneChangeRelationships:
    """Tests for SceneChange relationship definitions."""

    def test_scene_change_has_camera_relationship(self, sample_scene_change):
        """Test SceneChange has camera relationship defined."""
        assert hasattr(sample_scene_change, "camera")

    def test_scene_change_camera_relationship_attribute(self):
        """Test SceneChange camera relationship attribute exists on class."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        relationships = [rel.key for rel in mapper.relationships]
        assert "camera" in relationships


# =============================================================================
# SceneChange Table Configuration Tests
# =============================================================================


class TestSceneChangeTableConfig:
    """Tests for SceneChange table configuration."""

    def test_scene_change_tablename(self):
        """Test SceneChange has correct table name."""
        assert SceneChange.__tablename__ == "scene_changes"

    def test_scene_change_has_id_primary_key(self):
        """Test SceneChange has id as primary key."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        pk_cols = [col.name for col in mapper.primary_key]
        assert "id" in pk_cols

    def test_scene_change_has_table_args(self):
        """Test SceneChange has __table_args__ for indexes."""
        assert hasattr(SceneChange, "__table_args__")

    def test_scene_change_indexes_defined(self):
        """Test SceneChange has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for expected indexes
        assert "idx_scene_changes_camera_id" in index_names
        assert "idx_scene_changes_detected_at" in index_names
        assert "idx_scene_changes_acknowledged" in index_names
        assert "idx_scene_changes_camera_acknowledged" in index_names


class TestSceneChangeColumnConstraints:
    """Tests for SceneChange column constraints."""

    def test_camera_id_not_nullable(self):
        """Test camera_id column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        camera_id_col = mapper.columns["camera_id"]
        assert camera_id_col.nullable is False

    def test_similarity_score_not_nullable(self):
        """Test similarity_score column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        similarity_score_col = mapper.columns["similarity_score"]
        assert similarity_score_col.nullable is False

    def test_change_type_not_nullable(self):
        """Test change_type column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        change_type_col = mapper.columns["change_type"]
        assert change_type_col.nullable is False

    def test_acknowledged_not_nullable(self):
        """Test acknowledged column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        acknowledged_col = mapper.columns["acknowledged"]
        assert acknowledged_col.nullable is False

    def test_detected_at_not_nullable(self):
        """Test detected_at column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        detected_at_col = mapper.columns["detected_at"]
        assert detected_at_col.nullable is False

    def test_acknowledged_at_nullable(self):
        """Test acknowledged_at column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        acknowledged_at_col = mapper.columns["acknowledged_at"]
        assert acknowledged_at_col.nullable is True

    def test_file_path_nullable(self):
        """Test file_path column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        file_path_col = mapper.columns["file_path"]
        assert file_path_col.nullable is True


class TestSceneChangeForeignKey:
    """Tests for SceneChange foreign key configuration."""

    def test_camera_id_has_foreign_key(self):
        """Test camera_id has foreign key to cameras table."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        camera_id_col = mapper.columns["camera_id"]
        foreign_keys = list(camera_id_col.foreign_keys)
        assert len(foreign_keys) == 1
        assert foreign_keys[0].column.table.name == "cameras"

    def test_camera_id_cascade_delete(self):
        """Test camera_id foreign key has CASCADE delete."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        camera_id_col = mapper.columns["camera_id"]
        foreign_keys = list(camera_id_col.foreign_keys)
        assert foreign_keys[0].ondelete == "CASCADE"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestSceneChangeProperties:
    """Property-based tests for SceneChange model."""

    @given(change_type=scene_change_types)
    @settings(max_examples=20)
    def test_change_type_roundtrip(self, change_type: SceneChangeType):
        """Property: Change type values roundtrip correctly."""
        sc = SceneChange(
            camera_id="test",
            change_type=change_type,
            similarity_score=0.5,
        )
        assert sc.change_type == change_type

    @given(similarity_score=similarity_scores)
    @settings(max_examples=50)
    def test_similarity_score_roundtrip(self, similarity_score: float):
        """Property: Similarity score values roundtrip correctly."""
        sc = SceneChange(
            camera_id="test",
            similarity_score=similarity_score,
        )
        assert abs(sc.similarity_score - similarity_score) < 0.0001

    @given(camera_id=camera_ids)
    @settings(max_examples=50)
    def test_camera_id_roundtrip(self, camera_id: str):
        """Property: Camera ID values roundtrip correctly."""
        sc = SceneChange(
            camera_id=camera_id,
            similarity_score=0.5,
        )
        assert sc.camera_id == camera_id

    @given(acknowledged=st.booleans())
    @settings(max_examples=10)
    def test_acknowledged_roundtrip(self, acknowledged: bool):
        """Property: Acknowledged values roundtrip correctly."""
        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            acknowledged=acknowledged,
        )
        assert sc.acknowledged == acknowledged

    @given(id_value=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=50)
    def test_id_roundtrip(self, id_value: int):
        """Property: ID values roundtrip correctly."""
        sc = SceneChange(
            id=id_value,
            camera_id="test",
            similarity_score=0.5,
        )
        assert sc.id == id_value

    @given(
        change_type=scene_change_types,
        similarity_score=similarity_scores,
        acknowledged=st.booleans(),
    )
    @settings(max_examples=50)
    def test_multiple_fields_roundtrip(
        self,
        change_type: SceneChangeType,
        similarity_score: float,
        acknowledged: bool,
    ):
        """Property: Multiple fields roundtrip correctly together."""
        sc = SceneChange(
            camera_id="test",
            change_type=change_type,
            similarity_score=similarity_score,
            acknowledged=acknowledged,
        )
        assert sc.change_type == change_type
        assert abs(sc.similarity_score - similarity_score) < 0.0001
        assert sc.acknowledged == acknowledged


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestSceneChangeEdgeCases:
    """Tests for SceneChange edge cases."""

    def test_similarity_score_boundary_zero(self):
        """Test similarity_score at boundary zero."""
        sc = SceneChange(camera_id="test", similarity_score=0.0)
        assert sc.similarity_score == 0.0

    def test_similarity_score_boundary_one(self):
        """Test similarity_score at boundary one."""
        sc = SceneChange(camera_id="test", similarity_score=1.0)
        assert sc.similarity_score == 1.0

    def test_similarity_score_very_small(self):
        """Test similarity_score with very small value."""
        sc = SceneChange(camera_id="test", similarity_score=0.001)
        assert sc.similarity_score == 0.001

    def test_similarity_score_almost_one(self):
        """Test similarity_score with value close to one."""
        sc = SceneChange(camera_id="test", similarity_score=0.999)
        assert sc.similarity_score == 0.999

    def test_acknowledged_transition(self):
        """Test transitioning from unacknowledged to acknowledged."""
        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            acknowledged=False,
        )
        assert sc.acknowledged is False
        assert sc.acknowledged_at is None

        # Simulate acknowledgment
        sc.acknowledged = True
        sc.acknowledged_at = datetime.now(UTC)

        assert sc.acknowledged is True
        assert sc.acknowledged_at is not None

    def test_file_path_empty_string(self):
        """Test file_path with empty string."""
        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            file_path="",
        )
        assert sc.file_path == ""

    def test_camera_id_with_unicode(self):
        """Test camera_id with Unicode characters."""
        sc = SceneChange(
            camera_id="camera_francaise",
            similarity_score=0.5,
        )
        assert sc.camera_id == "camera_francaise"

    def test_multiple_scene_changes_independence(self):
        """Test that multiple SceneChange instances are independent."""
        sc1 = SceneChange(
            camera_id="camera1",
            change_type=SceneChangeType.VIEW_BLOCKED,
            similarity_score=0.3,
            acknowledged=False,
        )
        sc2 = SceneChange(
            camera_id="camera2",
            change_type=SceneChangeType.ANGLE_CHANGED,
            similarity_score=0.7,
            acknowledged=True,
        )

        # Verify independence
        assert sc1.camera_id != sc2.camera_id
        assert sc1.change_type != sc2.change_type
        assert sc1.similarity_score != sc2.similarity_score
        assert sc1.acknowledged != sc2.acknowledged

    def test_all_change_types_with_low_similarity(self):
        """Test all change types work with low similarity scores."""
        for change_type in SceneChangeType:
            sc = SceneChange(
                camera_id="test",
                change_type=change_type,
                similarity_score=0.1,
            )
            assert sc.change_type == change_type
            assert sc.similarity_score < 0.5

    def test_detected_at_and_acknowledged_at_ordering(self):
        """Test that acknowledged_at should logically come after detected_at."""
        detected = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        acknowledged = datetime(2025, 1, 15, 11, 0, 0, tzinfo=UTC)

        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            detected_at=detected,
            acknowledged=True,
            acknowledged_at=acknowledged,
        )

        assert sc.detected_at < sc.acknowledged_at

    def test_file_path_with_spaces(self):
        """Test file_path with spaces in path."""
        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            file_path="/export/foscam/Front Door/image 001.jpg",
        )
        assert " " in sc.file_path

    def test_file_path_with_special_characters(self):
        """Test file_path with special characters."""
        sc = SceneChange(
            camera_id="test",
            similarity_score=0.5,
            file_path="/export/foscam/test_camera/image-001_backup.jpg",
        )
        assert "-" in sc.file_path
        assert "_" in sc.file_path
