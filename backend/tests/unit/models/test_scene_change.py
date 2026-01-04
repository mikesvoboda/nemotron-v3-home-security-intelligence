"""Unit tests for SceneChange model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- SceneChangeType enum values
- String representation (__repr__)
- Relationship definitions
- Timestamp handling
- Property-based tests for field values
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

# Strategy for valid scene change types
scene_change_types = st.sampled_from(list(SceneChangeType))

# Strategy for valid camera IDs (alphanumeric with underscores)
camera_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="_",
    ),
)

# Strategy for valid similarity scores (0.0 to 1.0)
similarity_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for file paths
file_paths = st.text(
    min_size=1,
    max_size=500,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="/_.-",
    ),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_scene_change():
    """Create a sample scene change for testing."""
    return SceneChange(
        id=1,
        camera_id="front_door",
        detected_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        change_type=SceneChangeType.VIEW_BLOCKED,
        similarity_score=0.35,
        acknowledged=False,
        file_path="/export/foscam/front_door/2025-01-15/image001.jpg",
    )


@pytest.fixture
def acknowledged_scene_change():
    """Create an acknowledged scene change for testing."""
    detected = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
    acknowledged = datetime(2025, 1, 15, 10, 5, 0, tzinfo=UTC)
    return SceneChange(
        id=2,
        camera_id="back_yard",
        detected_at=detected,
        change_type=SceneChangeType.ANGLE_CHANGED,
        similarity_score=0.45,
        acknowledged=True,
        acknowledged_at=acknowledged,
        file_path="/export/foscam/back_yard/2025-01-15/image002.jpg",
    )


@pytest.fixture
def minimal_scene_change():
    """Create a scene change with only required fields."""
    return SceneChange(
        camera_id="garage",
        similarity_score=0.5,
    )


# =============================================================================
# SceneChangeType Enum Tests
# =============================================================================


class TestSceneChangeTypeEnum:
    """Tests for SceneChangeType enum."""

    def test_scene_change_type_view_blocked(self):
        """Test VIEW_BLOCKED enum value."""
        assert SceneChangeType.VIEW_BLOCKED.value == "view_blocked"

    def test_scene_change_type_angle_changed(self):
        """Test ANGLE_CHANGED enum value."""
        assert SceneChangeType.ANGLE_CHANGED.value == "angle_changed"

    def test_scene_change_type_view_tampered(self):
        """Test VIEW_TAMPERED enum value."""
        assert SceneChangeType.VIEW_TAMPERED.value == "view_tampered"

    def test_scene_change_type_unknown(self):
        """Test UNKNOWN enum value."""
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
        values = [change_type.value for change_type in SceneChangeType]
        assert len(values) == len(set(values))


# =============================================================================
# SceneChange Model Initialization Tests
# =============================================================================


class TestSceneChangeModelInitialization:
    """Tests for SceneChange model initialization."""

    def test_scene_change_creation_minimal(self, minimal_scene_change):
        """Test creating a scene change with minimal required fields."""
        assert minimal_scene_change.camera_id == "garage"
        assert minimal_scene_change.similarity_score == 0.5

    def test_scene_change_with_all_fields(self, sample_scene_change):
        """Test scene change with all fields populated."""
        assert sample_scene_change.id == 1
        assert sample_scene_change.camera_id == "front_door"
        assert sample_scene_change.detected_at == datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert sample_scene_change.change_type == SceneChangeType.VIEW_BLOCKED
        assert sample_scene_change.similarity_score == 0.35
        assert sample_scene_change.acknowledged is False
        assert sample_scene_change.file_path == "/export/foscam/front_door/2025-01-15/image001.jpg"

    def test_scene_change_default_acknowledged_column_definition(self):
        """Test acknowledged column has False as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        acknowledged_col = mapper.columns["acknowledged"]
        assert acknowledged_col.default is not None
        assert acknowledged_col.default.arg is False

    def test_scene_change_default_change_type_column_definition(self):
        """Test change_type column has UNKNOWN as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        change_type_col = mapper.columns["change_type"]
        assert change_type_col.default is not None
        assert change_type_col.default.arg == SceneChangeType.UNKNOWN

    def test_scene_change_optional_fields_default_to_none(self, minimal_scene_change):
        """Test optional fields default to None."""
        assert minimal_scene_change.acknowledged_at is None
        assert minimal_scene_change.file_path is None


# =============================================================================
# SceneChange Field Tests
# =============================================================================


class TestSceneChangeCameraIdField:
    """Tests for SceneChange camera_id field."""

    def test_camera_id_simple(self, sample_scene_change):
        """Test camera_id with simple value."""
        assert sample_scene_change.camera_id == "front_door"

    def test_camera_id_with_underscore(self):
        """Test camera_id with underscores."""
        sc = SceneChange(camera_id="back_yard", similarity_score=0.5)
        assert sc.camera_id == "back_yard"

    def test_camera_id_with_numbers(self):
        """Test camera_id with numbers."""
        sc = SceneChange(camera_id="camera_01", similarity_score=0.5)
        assert sc.camera_id == "camera_01"

    def test_camera_id_uppercase(self):
        """Test camera_id with uppercase letters."""
        sc = SceneChange(camera_id="FrontDoor", similarity_score=0.5)
        assert sc.camera_id == "FrontDoor"


class TestSceneChangeSimilarityScoreField:
    """Tests for SceneChange similarity_score field."""

    def test_similarity_score_low(self):
        """Test low similarity score (more different)."""
        sc = SceneChange(camera_id="cam", similarity_score=0.1)
        assert sc.similarity_score == 0.1

    def test_similarity_score_high(self):
        """Test high similarity score (almost identical)."""
        sc = SceneChange(camera_id="cam", similarity_score=0.95)
        assert sc.similarity_score == 0.95

    def test_similarity_score_zero(self):
        """Test similarity score at minimum (0.0)."""
        sc = SceneChange(camera_id="cam", similarity_score=0.0)
        assert sc.similarity_score == 0.0

    def test_similarity_score_one(self):
        """Test similarity score at maximum (1.0)."""
        sc = SceneChange(camera_id="cam", similarity_score=1.0)
        assert sc.similarity_score == 1.0

    def test_similarity_score_fractional(self):
        """Test fractional similarity score."""
        sc = SceneChange(camera_id="cam", similarity_score=0.3456)
        assert abs(sc.similarity_score - 0.3456) < 0.0001


class TestSceneChangeChangeTypeField:
    """Tests for SceneChange change_type field."""

    def test_change_type_view_blocked(self, sample_scene_change):
        """Test change_type VIEW_BLOCKED."""
        assert sample_scene_change.change_type == SceneChangeType.VIEW_BLOCKED

    def test_change_type_angle_changed(self, acknowledged_scene_change):
        """Test change_type ANGLE_CHANGED."""
        assert acknowledged_scene_change.change_type == SceneChangeType.ANGLE_CHANGED

    def test_change_type_view_tampered(self):
        """Test change_type VIEW_TAMPERED."""
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.2,
            change_type=SceneChangeType.VIEW_TAMPERED,
        )
        assert sc.change_type == SceneChangeType.VIEW_TAMPERED

    def test_change_type_unknown(self):
        """Test change_type UNKNOWN."""
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.3,
            change_type=SceneChangeType.UNKNOWN,
        )
        assert sc.change_type == SceneChangeType.UNKNOWN

    def test_change_type_all_values(self):
        """Test all change_type enum values can be assigned."""
        for change_type in SceneChangeType:
            sc = SceneChange(
                camera_id="cam",
                similarity_score=0.5,
                change_type=change_type,
            )
            assert sc.change_type == change_type


class TestSceneChangeAcknowledgedField:
    """Tests for SceneChange acknowledged field."""

    def test_acknowledged_false(self, sample_scene_change):
        """Test acknowledged set to False."""
        assert sample_scene_change.acknowledged is False

    def test_acknowledged_true(self, acknowledged_scene_change):
        """Test acknowledged set to True."""
        assert acknowledged_scene_change.acknowledged is True

    def test_acknowledged_explicit_false(self):
        """Test explicit False assignment."""
        sc = SceneChange(camera_id="cam", similarity_score=0.5, acknowledged=False)
        assert sc.acknowledged is False

    def test_acknowledged_explicit_true(self):
        """Test explicit True assignment."""
        sc = SceneChange(camera_id="cam", similarity_score=0.5, acknowledged=True)
        assert sc.acknowledged is True


class TestSceneChangeAcknowledgedAtField:
    """Tests for SceneChange acknowledged_at field."""

    def test_acknowledged_at_none(self, sample_scene_change):
        """Test acknowledged_at is None when not acknowledged."""
        assert sample_scene_change.acknowledged_at is None

    def test_acknowledged_at_set(self, acknowledged_scene_change):
        """Test acknowledged_at is set when acknowledged."""
        expected = datetime(2025, 1, 15, 10, 5, 0, tzinfo=UTC)
        assert acknowledged_scene_change.acknowledged_at == expected

    def test_acknowledged_at_with_timezone(self, acknowledged_scene_change):
        """Test acknowledged_at has timezone info."""
        assert acknowledged_scene_change.acknowledged_at.tzinfo is not None

    def test_acknowledged_at_explicit(self):
        """Test explicit acknowledged_at assignment."""
        now = datetime.now(UTC)
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.5,
            acknowledged=True,
            acknowledged_at=now,
        )
        assert sc.acknowledged_at == now


class TestSceneChangeFilePathField:
    """Tests for SceneChange file_path field."""

    def test_file_path_set(self, sample_scene_change):
        """Test file_path when set."""
        expected = "/export/foscam/front_door/2025-01-15/image001.jpg"
        assert sample_scene_change.file_path == expected

    def test_file_path_none(self, minimal_scene_change):
        """Test file_path is None by default."""
        assert minimal_scene_change.file_path is None

    def test_file_path_with_spaces(self):
        """Test file_path with spaces."""
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.5,
            file_path="/export/foscam/Front Door/image.jpg",
        )
        assert sc.file_path == "/export/foscam/Front Door/image.jpg"

    def test_file_path_long(self):
        """Test long file_path."""
        long_path = "/export/foscam/" + "a" * 200 + "/image.jpg"
        sc = SceneChange(camera_id="cam", similarity_score=0.5, file_path=long_path)
        assert sc.file_path == long_path


class TestSceneChangeTimestampField:
    """Tests for SceneChange detected_at field."""

    def test_detected_at_with_timezone(self, sample_scene_change):
        """Test detected_at has timezone info."""
        assert sample_scene_change.detected_at.tzinfo is not None

    def test_detected_at_explicit(self, sample_scene_change):
        """Test explicit detected_at value."""
        expected = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert sample_scene_change.detected_at == expected

    def test_detected_at_has_attribute(self, minimal_scene_change):
        """Test scene change has detected_at attribute."""
        assert hasattr(minimal_scene_change, "detected_at")

    def test_detected_at_default_column_definition(self):
        """Test detected_at column has a default factory.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        detected_at_col = mapper.columns["detected_at"]
        assert detected_at_col.default is not None


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
        # Check for the enum value representation
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


# =============================================================================
# SceneChange Relationship Tests
# =============================================================================


class TestSceneChangeRelationships:
    """Tests for SceneChange relationship definitions."""

    def test_scene_change_has_camera_relationship(self, sample_scene_change):
        """Test SceneChange has camera relationship defined."""
        assert hasattr(sample_scene_change, "camera")


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


class TestSceneChangeForeignKeys:
    """Tests for SceneChange foreign key definitions."""

    def test_camera_id_has_foreign_key(self):
        """Test camera_id has foreign key to cameras table."""
        from sqlalchemy import inspect

        mapper = inspect(SceneChange)
        camera_id_col = mapper.columns["camera_id"]
        fks = list(camera_id_col.foreign_keys)
        assert len(fks) == 1
        assert "cameras.id" in str(fks[0].target_fullname)


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
            camera_id="cam",
            similarity_score=0.5,
            change_type=change_type,
        )
        assert sc.change_type == change_type

    @given(score=similarity_scores)
    @settings(max_examples=50)
    def test_similarity_score_roundtrip(self, score: float):
        """Property: Similarity score values roundtrip correctly."""
        sc = SceneChange(
            camera_id="cam",
            similarity_score=score,
        )
        assert abs(sc.similarity_score - score) < 1e-10

    @given(acknowledged=st.booleans())
    @settings(max_examples=10)
    def test_acknowledged_roundtrip(self, acknowledged: bool):
        """Property: Acknowledged values roundtrip correctly."""
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.5,
            acknowledged=acknowledged,
        )
        assert sc.acknowledged == acknowledged

    @given(camera_id=camera_ids)
    @settings(max_examples=50)
    def test_camera_id_roundtrip(self, camera_id: str):
        """Property: Camera ID values roundtrip correctly."""
        sc = SceneChange(
            camera_id=camera_id,
            similarity_score=0.5,
        )
        assert sc.camera_id == camera_id

    @given(id_value=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=50)
    def test_id_roundtrip(self, id_value: int):
        """Property: ID values roundtrip correctly."""
        sc = SceneChange(
            id=id_value,
            camera_id="cam",
            similarity_score=0.5,
        )
        assert sc.id == id_value

    @given(
        change_type=scene_change_types,
        score=similarity_scores,
        acknowledged=st.booleans(),
    )
    @settings(max_examples=50)
    def test_all_fields_roundtrip(
        self,
        change_type: SceneChangeType,
        score: float,
        acknowledged: bool,
    ):
        """Property: Multiple field combinations roundtrip correctly."""
        sc = SceneChange(
            camera_id="test_cam",
            similarity_score=score,
            change_type=change_type,
            acknowledged=acknowledged,
        )
        assert sc.change_type == change_type
        assert abs(sc.similarity_score - score) < 1e-10
        assert sc.acknowledged == acknowledged


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestSceneChangeEdgeCases:
    """Tests for edge cases in SceneChange model."""

    def test_similarity_score_boundary_low(self):
        """Test similarity score at low boundary (0.0)."""
        sc = SceneChange(camera_id="cam", similarity_score=0.0)
        assert sc.similarity_score == 0.0

    def test_similarity_score_boundary_high(self):
        """Test similarity score at high boundary (1.0)."""
        sc = SceneChange(camera_id="cam", similarity_score=1.0)
        assert sc.similarity_score == 1.0

    def test_acknowledged_without_acknowledged_at(self):
        """Test acknowledged=True without acknowledged_at timestamp."""
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.5,
            acknowledged=True,
            acknowledged_at=None,  # Explicitly None
        )
        assert sc.acknowledged is True
        assert sc.acknowledged_at is None

    def test_acknowledged_at_before_detected_at(self):
        """Test acknowledged_at can be before detected_at (edge case)."""
        earlier = datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC)
        later = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.5,
            detected_at=later,
            acknowledged_at=earlier,  # Before detected (unusual but allowed)
        )
        assert sc.acknowledged_at < sc.detected_at

    def test_file_path_empty_string(self):
        """Test file_path with empty string."""
        sc = SceneChange(camera_id="cam", similarity_score=0.5, file_path="")
        assert sc.file_path == ""

    def test_file_path_with_special_characters(self):
        """Test file_path with special characters."""
        sc = SceneChange(
            camera_id="cam",
            similarity_score=0.5,
            file_path="/export/foscam/Front Door-Cam (1)/image.jpg",
        )
        assert sc.file_path == "/export/foscam/Front Door-Cam (1)/image.jpg"

    def test_multiple_scene_changes_independence(self):
        """Test that multiple scene change instances are independent."""
        sc1 = SceneChange(
            camera_id="cam1",
            similarity_score=0.3,
            change_type=SceneChangeType.VIEW_BLOCKED,
        )
        sc2 = SceneChange(
            camera_id="cam2",
            similarity_score=0.7,
            change_type=SceneChangeType.ANGLE_CHANGED,
        )

        # Verify independence
        assert sc1.camera_id != sc2.camera_id
        assert sc1.similarity_score != sc2.similarity_score
        assert sc1.change_type != sc2.change_type

    def test_very_small_similarity_score(self):
        """Test very small similarity score (almost completely different)."""
        sc = SceneChange(camera_id="cam", similarity_score=0.0001)
        assert abs(sc.similarity_score - 0.0001) < 1e-10

    def test_similarity_score_near_one(self):
        """Test similarity score very close to 1.0 (almost identical)."""
        sc = SceneChange(camera_id="cam", similarity_score=0.9999)
        assert abs(sc.similarity_score - 0.9999) < 1e-10

    def test_camera_id_single_character(self):
        """Test camera_id with single character."""
        sc = SceneChange(camera_id="x", similarity_score=0.5)
        assert sc.camera_id == "x"

    def test_camera_id_numeric_only(self):
        """Test camera_id with numeric-only value."""
        sc = SceneChange(camera_id="12345", similarity_score=0.5)
        assert sc.camera_id == "12345"
