"""Unit tests for ActivityBaseline and ClassBaseline models.

Tests cover:
- Model initialization with all fields
- Default values for computed fields
- Field validation (hour 0-23, day_of_week 0-6)
- String representation (__repr__)
- Relationship definitions
- Property-based tests for field constraints
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import inspect

from backend.models.baseline import ActivityBaseline, ClassBaseline

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid hours (0-23)
valid_hours = st.integers(min_value=0, max_value=23)

# Strategy for invalid hours (outside 0-23)
invalid_hours = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=24),
)

# Strategy for valid day_of_week (0-6)
valid_days_of_week = st.integers(min_value=0, max_value=6)

# Strategy for invalid day_of_week (outside 0-6)
invalid_days_of_week = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=7),
)

# Strategy for valid camera IDs
camera_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="_"),
).filter(lambda x: len(x.strip()) > 0 and not x.startswith("_"))

# Strategy for valid detection classes
detection_classes = st.sampled_from(
    ["person", "vehicle", "car", "truck", "bicycle", "motorcycle", "cat", "dog", "bird", "animal"]
)

# Strategy for non-negative counts
non_negative_counts = st.floats(
    min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False
)

# Strategy for valid frequencies (0-1 range typically, but could be higher)
valid_frequencies = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for sample counts
sample_counts = st.integers(min_value=0, max_value=100000)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_activity_baseline():
    """Create a sample ActivityBaseline for testing."""
    return ActivityBaseline(
        id=1,
        camera_id="front_door",
        hour=14,
        day_of_week=2,
        avg_count=5.5,
        sample_count=100,
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def sample_class_baseline():
    """Create a sample ClassBaseline for testing."""
    return ClassBaseline(
        id=1,
        camera_id="front_door",
        detection_class="person",
        hour=14,
        frequency=0.75,
        sample_count=50,
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def minimal_activity_baseline():
    """Create an ActivityBaseline with only required fields."""
    return ActivityBaseline(
        camera_id="back_yard",
        hour=0,
        day_of_week=0,
    )


@pytest.fixture
def minimal_class_baseline():
    """Create a ClassBaseline with only required fields."""
    return ClassBaseline(
        camera_id="back_yard",
        detection_class="vehicle",
        hour=0,
    )


# =============================================================================
# ActivityBaseline Model Tests
# =============================================================================


class TestActivityBaselineInitialization:
    """Tests for ActivityBaseline model initialization."""

    def test_activity_baseline_creation_full(self, sample_activity_baseline):
        """Test creating an ActivityBaseline with all fields."""
        baseline = sample_activity_baseline

        assert baseline.id == 1
        assert baseline.camera_id == "front_door"
        assert baseline.hour == 14
        assert baseline.day_of_week == 2
        assert baseline.avg_count == 5.5
        assert baseline.sample_count == 100
        assert baseline.last_updated is not None

    def test_activity_baseline_creation_minimal(self, minimal_activity_baseline):
        """Test creating an ActivityBaseline with minimal required fields."""
        baseline = minimal_activity_baseline

        assert baseline.camera_id == "back_yard"
        assert baseline.hour == 0
        assert baseline.day_of_week == 0

    def test_activity_baseline_tablename(self):
        """Test that ActivityBaseline has correct table name."""
        assert ActivityBaseline.__tablename__ == "activity_baselines"


class TestActivityBaselineDefaults:
    """Tests for ActivityBaseline default values."""

    def test_avg_count_default_column_definition(self):
        """Test that avg_count column has 0.0 as default."""
        mapper = inspect(ActivityBaseline)
        avg_count_col = mapper.columns["avg_count"]
        assert avg_count_col.default is not None
        assert avg_count_col.default.arg == 0.0

    def test_sample_count_default_column_definition(self):
        """Test that sample_count column has 0 as default."""
        mapper = inspect(ActivityBaseline)
        sample_count_col = mapper.columns["sample_count"]
        assert sample_count_col.default is not None
        assert sample_count_col.default.arg == 0

    def test_last_updated_default_is_callable(self):
        """Test that last_updated has a callable default (current timestamp)."""
        mapper = inspect(ActivityBaseline)
        last_updated_col = mapper.columns["last_updated"]
        assert last_updated_col.default is not None
        # The default is a callable that returns current time
        assert callable(last_updated_col.default.arg)


class TestActivityBaselineAttributes:
    """Tests for ActivityBaseline model attributes."""

    def test_has_id_field(self, sample_activity_baseline):
        """Test ActivityBaseline has id field."""
        assert hasattr(sample_activity_baseline, "id")

    def test_has_camera_id_field(self, sample_activity_baseline):
        """Test ActivityBaseline has camera_id field."""
        assert hasattr(sample_activity_baseline, "camera_id")
        assert sample_activity_baseline.camera_id == "front_door"

    def test_has_hour_field(self, sample_activity_baseline):
        """Test ActivityBaseline has hour field."""
        assert hasattr(sample_activity_baseline, "hour")
        assert sample_activity_baseline.hour == 14

    def test_has_day_of_week_field(self, sample_activity_baseline):
        """Test ActivityBaseline has day_of_week field."""
        assert hasattr(sample_activity_baseline, "day_of_week")
        assert sample_activity_baseline.day_of_week == 2

    def test_has_avg_count_field(self, sample_activity_baseline):
        """Test ActivityBaseline has avg_count field."""
        assert hasattr(sample_activity_baseline, "avg_count")
        assert sample_activity_baseline.avg_count == 5.5

    def test_has_sample_count_field(self, sample_activity_baseline):
        """Test ActivityBaseline has sample_count field."""
        assert hasattr(sample_activity_baseline, "sample_count")
        assert sample_activity_baseline.sample_count == 100

    def test_has_last_updated_field(self, sample_activity_baseline):
        """Test ActivityBaseline has last_updated field."""
        assert hasattr(sample_activity_baseline, "last_updated")
        assert sample_activity_baseline.last_updated is not None


class TestActivityBaselineRepr:
    """Tests for ActivityBaseline string representation."""

    def test_repr_contains_class_name(self, sample_activity_baseline):
        """Test repr contains class name."""
        repr_str = repr(sample_activity_baseline)
        assert "ActivityBaseline" in repr_str

    def test_repr_contains_camera_id(self, sample_activity_baseline):
        """Test repr contains camera_id."""
        repr_str = repr(sample_activity_baseline)
        assert "front_door" in repr_str

    def test_repr_contains_hour(self, sample_activity_baseline):
        """Test repr contains hour."""
        repr_str = repr(sample_activity_baseline)
        assert "hour=14" in repr_str

    def test_repr_contains_day_of_week(self, sample_activity_baseline):
        """Test repr contains day_of_week."""
        repr_str = repr(sample_activity_baseline)
        assert "day_of_week=2" in repr_str

    def test_repr_contains_avg_count(self, sample_activity_baseline):
        """Test repr contains avg_count formatted to 2 decimal places."""
        repr_str = repr(sample_activity_baseline)
        assert "avg_count=5.50" in repr_str

    def test_repr_format(self, sample_activity_baseline):
        """Test repr has expected format."""
        repr_str = repr(sample_activity_baseline)
        assert repr_str.startswith("<ActivityBaseline(")
        assert repr_str.endswith(")>")


class TestActivityBaselineRelationships:
    """Tests for ActivityBaseline relationship definitions."""

    def test_has_camera_relationship(self, sample_activity_baseline):
        """Test ActivityBaseline has camera relationship defined."""
        assert hasattr(sample_activity_baseline, "camera")


class TestActivityBaselineConstraints:
    """Tests for ActivityBaseline table constraints and indexes."""

    def test_unique_constraint_defined(self):
        """Test unique constraint on camera_id, hour, day_of_week exists."""
        table_args = ActivityBaseline.__table_args__
        constraint_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "uq_activity_baseline_slot" in constraint_names

    def test_camera_index_defined(self):
        """Test index on camera_id exists."""
        table_args = ActivityBaseline.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "idx_activity_baseline_camera" in index_names

    def test_slot_index_defined(self):
        """Test composite index on camera_id, hour, day_of_week exists."""
        table_args = ActivityBaseline.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "idx_activity_baseline_slot" in index_names

    def test_foreign_key_cascade_delete(self):
        """Test that camera_id foreign key has cascade delete."""
        mapper = inspect(ActivityBaseline)
        camera_id_col = mapper.columns["camera_id"]
        fk = next(iter(camera_id_col.foreign_keys))
        assert fk.ondelete == "CASCADE"


# =============================================================================
# ClassBaseline Model Tests
# =============================================================================


class TestClassBaselineInitialization:
    """Tests for ClassBaseline model initialization."""

    def test_class_baseline_creation_full(self, sample_class_baseline):
        """Test creating a ClassBaseline with all fields."""
        baseline = sample_class_baseline

        assert baseline.id == 1
        assert baseline.camera_id == "front_door"
        assert baseline.detection_class == "person"
        assert baseline.hour == 14
        assert baseline.frequency == 0.75
        assert baseline.sample_count == 50
        assert baseline.last_updated is not None

    def test_class_baseline_creation_minimal(self, minimal_class_baseline):
        """Test creating a ClassBaseline with minimal required fields."""
        baseline = minimal_class_baseline

        assert baseline.camera_id == "back_yard"
        assert baseline.detection_class == "vehicle"
        assert baseline.hour == 0

    def test_class_baseline_tablename(self):
        """Test that ClassBaseline has correct table name."""
        assert ClassBaseline.__tablename__ == "class_baselines"


class TestClassBaselineDefaults:
    """Tests for ClassBaseline default values."""

    def test_frequency_default_column_definition(self):
        """Test that frequency column has 0.0 as default."""
        mapper = inspect(ClassBaseline)
        frequency_col = mapper.columns["frequency"]
        assert frequency_col.default is not None
        assert frequency_col.default.arg == 0.0

    def test_sample_count_default_column_definition(self):
        """Test that sample_count column has 0 as default."""
        mapper = inspect(ClassBaseline)
        sample_count_col = mapper.columns["sample_count"]
        assert sample_count_col.default is not None
        assert sample_count_col.default.arg == 0

    def test_last_updated_default_is_callable(self):
        """Test that last_updated has a callable default (current timestamp)."""
        mapper = inspect(ClassBaseline)
        last_updated_col = mapper.columns["last_updated"]
        assert last_updated_col.default is not None
        assert callable(last_updated_col.default.arg)


class TestClassBaselineAttributes:
    """Tests for ClassBaseline model attributes."""

    def test_has_id_field(self, sample_class_baseline):
        """Test ClassBaseline has id field."""
        assert hasattr(sample_class_baseline, "id")

    def test_has_camera_id_field(self, sample_class_baseline):
        """Test ClassBaseline has camera_id field."""
        assert hasattr(sample_class_baseline, "camera_id")
        assert sample_class_baseline.camera_id == "front_door"

    def test_has_detection_class_field(self, sample_class_baseline):
        """Test ClassBaseline has detection_class field."""
        assert hasattr(sample_class_baseline, "detection_class")
        assert sample_class_baseline.detection_class == "person"

    def test_has_hour_field(self, sample_class_baseline):
        """Test ClassBaseline has hour field."""
        assert hasattr(sample_class_baseline, "hour")
        assert sample_class_baseline.hour == 14

    def test_has_frequency_field(self, sample_class_baseline):
        """Test ClassBaseline has frequency field."""
        assert hasattr(sample_class_baseline, "frequency")
        assert sample_class_baseline.frequency == 0.75

    def test_has_sample_count_field(self, sample_class_baseline):
        """Test ClassBaseline has sample_count field."""
        assert hasattr(sample_class_baseline, "sample_count")
        assert sample_class_baseline.sample_count == 50

    def test_has_last_updated_field(self, sample_class_baseline):
        """Test ClassBaseline has last_updated field."""
        assert hasattr(sample_class_baseline, "last_updated")
        assert sample_class_baseline.last_updated is not None


class TestClassBaselineRepr:
    """Tests for ClassBaseline string representation."""

    def test_repr_contains_class_name(self, sample_class_baseline):
        """Test repr contains class name."""
        repr_str = repr(sample_class_baseline)
        assert "ClassBaseline" in repr_str

    def test_repr_contains_camera_id(self, sample_class_baseline):
        """Test repr contains camera_id."""
        repr_str = repr(sample_class_baseline)
        assert "front_door" in repr_str

    def test_repr_contains_detection_class(self, sample_class_baseline):
        """Test repr contains detection_class."""
        repr_str = repr(sample_class_baseline)
        assert "person" in repr_str

    def test_repr_contains_hour(self, sample_class_baseline):
        """Test repr contains hour."""
        repr_str = repr(sample_class_baseline)
        assert "hour=14" in repr_str

    def test_repr_contains_frequency(self, sample_class_baseline):
        """Test repr contains frequency formatted to 4 decimal places."""
        repr_str = repr(sample_class_baseline)
        assert "frequency=0.7500" in repr_str

    def test_repr_format(self, sample_class_baseline):
        """Test repr has expected format."""
        repr_str = repr(sample_class_baseline)
        assert repr_str.startswith("<ClassBaseline(")
        assert repr_str.endswith(")>")


class TestClassBaselineRelationships:
    """Tests for ClassBaseline relationship definitions."""

    def test_has_camera_relationship(self, sample_class_baseline):
        """Test ClassBaseline has camera relationship defined."""
        assert hasattr(sample_class_baseline, "camera")


class TestClassBaselineConstraints:
    """Tests for ClassBaseline table constraints and indexes."""

    def test_unique_constraint_defined(self):
        """Test unique constraint on camera_id, detection_class, hour exists."""
        table_args = ClassBaseline.__table_args__
        constraint_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "uq_class_baseline_slot" in constraint_names

    def test_camera_index_defined(self):
        """Test index on camera_id exists."""
        table_args = ClassBaseline.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "idx_class_baseline_camera" in index_names

    def test_class_index_defined(self):
        """Test composite index on camera_id, detection_class exists."""
        table_args = ClassBaseline.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "idx_class_baseline_class" in index_names

    def test_slot_index_defined(self):
        """Test composite index on camera_id, detection_class, hour exists."""
        table_args = ClassBaseline.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "idx_class_baseline_slot" in index_names

    def test_foreign_key_cascade_delete(self):
        """Test that camera_id foreign key has cascade delete."""
        mapper = inspect(ClassBaseline)
        camera_id_col = mapper.columns["camera_id"]
        fk = next(iter(camera_id_col.foreign_keys))
        assert fk.ondelete == "CASCADE"


# =============================================================================
# Property-based Tests - ActivityBaseline
# =============================================================================


class TestActivityBaselineProperties:
    """Property-based tests for ActivityBaseline model."""

    @given(
        camera_id=camera_ids,
        hour=valid_hours,
        day_of_week=valid_days_of_week,
        avg_count=non_negative_counts,
        sample_count=sample_counts,
    )
    @settings(max_examples=100)
    def test_activity_baseline_valid_inputs(
        self,
        camera_id: str,
        hour: int,
        day_of_week: int,
        avg_count: float,
        sample_count: int,
    ):
        """Property: Valid inputs always create a valid ActivityBaseline."""
        baseline = ActivityBaseline(
            camera_id=camera_id,
            hour=hour,
            day_of_week=day_of_week,
            avg_count=avg_count,
            sample_count=sample_count,
        )

        assert baseline.camera_id == camera_id
        assert baseline.hour == hour
        assert baseline.day_of_week == day_of_week
        assert baseline.avg_count == avg_count
        assert baseline.sample_count == sample_count

    @given(hour=valid_hours)
    @settings(max_examples=24)
    def test_hour_within_bounds(self, hour: int):
        """Property: Hour is always in [0, 23]."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=hour,
            day_of_week=0,
        )
        assert 0 <= baseline.hour <= 23

    @given(day_of_week=valid_days_of_week)
    @settings(max_examples=7)
    def test_day_of_week_within_bounds(self, day_of_week: int):
        """Property: day_of_week is always in [0, 6]."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=day_of_week,
        )
        assert 0 <= baseline.day_of_week <= 6

    @given(avg_count=non_negative_counts)
    @settings(max_examples=100)
    def test_avg_count_non_negative(self, avg_count: float):
        """Property: avg_count is always non-negative."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            avg_count=avg_count,
        )
        assert baseline.avg_count >= 0.0

    @given(sample_count=sample_counts)
    @settings(max_examples=100)
    def test_sample_count_non_negative(self, sample_count: int):
        """Property: sample_count is always non-negative."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            sample_count=sample_count,
        )
        assert baseline.sample_count >= 0

    @given(camera_id=camera_ids)
    @settings(max_examples=50)
    def test_camera_id_preserved(self, camera_id: str):
        """Property: camera_id is always preserved."""
        baseline = ActivityBaseline(
            camera_id=camera_id,
            hour=0,
            day_of_week=0,
        )
        assert baseline.camera_id == camera_id


class TestActivityBaselineReprProperties:
    """Property-based tests for ActivityBaseline __repr__."""

    @given(
        camera_id=camera_ids,
        hour=valid_hours,
        day_of_week=valid_days_of_week,
        avg_count=non_negative_counts,
    )
    @settings(max_examples=50)
    def test_repr_always_valid_string(
        self,
        camera_id: str,
        hour: int,
        day_of_week: int,
        avg_count: float,
    ):
        """Property: __repr__ always returns a valid string."""
        baseline = ActivityBaseline(
            camera_id=camera_id,
            hour=hour,
            day_of_week=day_of_week,
            avg_count=avg_count,
        )

        repr_str = repr(baseline)
        assert isinstance(repr_str, str)
        assert "ActivityBaseline" in repr_str
        assert repr_str.startswith("<")
        assert repr_str.endswith(">")

    @given(avg_count=non_negative_counts)
    @settings(max_examples=50)
    def test_repr_formats_avg_count_two_decimals(self, avg_count: float):
        """Property: avg_count in repr is always formatted to 2 decimal places."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            avg_count=avg_count,
        )

        repr_str = repr(baseline)
        # The avg_count should be formatted with .2f
        expected_formatted = f"{avg_count:.2f}"
        assert expected_formatted in repr_str


# =============================================================================
# Property-based Tests - ClassBaseline
# =============================================================================


class TestClassBaselineProperties:
    """Property-based tests for ClassBaseline model."""

    @given(
        camera_id=camera_ids,
        detection_class=detection_classes,
        hour=valid_hours,
        frequency=valid_frequencies,
        sample_count=sample_counts,
    )
    @settings(max_examples=100)
    def test_class_baseline_valid_inputs(
        self,
        camera_id: str,
        detection_class: str,
        hour: int,
        frequency: float,
        sample_count: int,
    ):
        """Property: Valid inputs always create a valid ClassBaseline."""
        baseline = ClassBaseline(
            camera_id=camera_id,
            detection_class=detection_class,
            hour=hour,
            frequency=frequency,
            sample_count=sample_count,
        )

        assert baseline.camera_id == camera_id
        assert baseline.detection_class == detection_class
        assert baseline.hour == hour
        assert baseline.frequency == frequency
        assert baseline.sample_count == sample_count

    @given(hour=valid_hours)
    @settings(max_examples=24)
    def test_hour_within_bounds(self, hour: int):
        """Property: Hour is always in [0, 23]."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=hour,
        )
        assert 0 <= baseline.hour <= 23

    @given(frequency=valid_frequencies)
    @settings(max_examples=100)
    def test_frequency_non_negative(self, frequency: float):
        """Property: frequency is always non-negative."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            frequency=frequency,
        )
        assert baseline.frequency >= 0.0

    @given(sample_count=sample_counts)
    @settings(max_examples=100)
    def test_sample_count_non_negative(self, sample_count: int):
        """Property: sample_count is always non-negative."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            sample_count=sample_count,
        )
        assert baseline.sample_count >= 0

    @given(camera_id=camera_ids)
    @settings(max_examples=50)
    def test_camera_id_preserved(self, camera_id: str):
        """Property: camera_id is always preserved."""
        baseline = ClassBaseline(
            camera_id=camera_id,
            detection_class="person",
            hour=0,
        )
        assert baseline.camera_id == camera_id

    @given(detection_class=detection_classes)
    @settings(max_examples=10)
    def test_detection_class_preserved(self, detection_class: str):
        """Property: detection_class is always preserved."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class=detection_class,
            hour=0,
        )
        assert baseline.detection_class == detection_class


class TestClassBaselineReprProperties:
    """Property-based tests for ClassBaseline __repr__."""

    @given(
        camera_id=camera_ids,
        detection_class=detection_classes,
        hour=valid_hours,
        frequency=valid_frequencies,
    )
    @settings(max_examples=50)
    def test_repr_always_valid_string(
        self,
        camera_id: str,
        detection_class: str,
        hour: int,
        frequency: float,
    ):
        """Property: __repr__ always returns a valid string."""
        baseline = ClassBaseline(
            camera_id=camera_id,
            detection_class=detection_class,
            hour=hour,
            frequency=frequency,
        )

        repr_str = repr(baseline)
        assert isinstance(repr_str, str)
        assert "ClassBaseline" in repr_str
        assert repr_str.startswith("<")
        assert repr_str.endswith(">")

    @given(frequency=valid_frequencies)
    @settings(max_examples=50)
    def test_repr_formats_frequency_four_decimals(self, frequency: float):
        """Property: frequency in repr is always formatted to 4 decimal places."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            frequency=frequency,
        )

        repr_str = repr(baseline)
        # The frequency should be formatted with .4f
        expected_formatted = f"{frequency:.4f}"
        assert expected_formatted in repr_str


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================


class TestActivityBaselineBoundaries:
    """Boundary tests for ActivityBaseline."""

    def test_hour_zero(self):
        """Test hour at minimum boundary (midnight)."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
        )
        assert baseline.hour == 0

    def test_hour_twenty_three(self):
        """Test hour at maximum boundary (11 PM)."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=23,
            day_of_week=0,
        )
        assert baseline.hour == 23

    def test_day_of_week_zero(self):
        """Test day_of_week at minimum boundary (Monday)."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
        )
        assert baseline.day_of_week == 0

    def test_day_of_week_six(self):
        """Test day_of_week at maximum boundary (Sunday)."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=6,
        )
        assert baseline.day_of_week == 6

    def test_sample_count_zero(self):
        """Test sample_count at minimum boundary."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            sample_count=0,
        )
        assert baseline.sample_count == 0

    def test_sample_count_large_value(self):
        """Test sample_count with a large value."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            sample_count=1000000,
        )
        assert baseline.sample_count == 1000000

    def test_avg_count_zero(self):
        """Test avg_count at minimum boundary."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            avg_count=0.0,
        )
        assert baseline.avg_count == 0.0

    def test_avg_count_large_value(self):
        """Test avg_count with a large value."""
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            avg_count=99999.99,
        )
        assert baseline.avg_count == 99999.99


class TestClassBaselineBoundaries:
    """Boundary tests for ClassBaseline."""

    def test_hour_zero(self):
        """Test hour at minimum boundary (midnight)."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
        )
        assert baseline.hour == 0

    def test_hour_twenty_three(self):
        """Test hour at maximum boundary (11 PM)."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=23,
        )
        assert baseline.hour == 23

    def test_sample_count_zero(self):
        """Test sample_count at minimum boundary."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            sample_count=0,
        )
        assert baseline.sample_count == 0

    def test_sample_count_large_value(self):
        """Test sample_count with a large value."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            sample_count=1000000,
        )
        assert baseline.sample_count == 1000000

    def test_frequency_zero(self):
        """Test frequency at minimum boundary."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            frequency=0.0,
        )
        assert baseline.frequency == 0.0

    def test_frequency_one(self):
        """Test frequency at maximum typical boundary."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            frequency=1.0,
        )
        assert baseline.frequency == 1.0

    def test_frequency_above_one(self):
        """Test frequency above 1.0 (allowed for aggregate frequencies)."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            frequency=5.0,
        )
        assert baseline.frequency == 5.0


class TestDetectionClassVariety:
    """Tests for various detection class values."""

    @pytest.mark.parametrize(
        "detection_class",
        [
            "person",
            "vehicle",
            "car",
            "truck",
            "bicycle",
            "motorcycle",
            "cat",
            "dog",
            "bird",
            "animal",
            "unknown",
            "package",
            "delivery_person",
        ],
    )
    def test_various_detection_classes(self, detection_class: str):
        """Test ClassBaseline with various detection class values."""
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class=detection_class,
            hour=12,
        )
        assert baseline.detection_class == detection_class


# =============================================================================
# Timestamp Tests
# =============================================================================


class TestActivityBaselineTimestamps:
    """Tests for ActivityBaseline timestamp handling."""

    def test_last_updated_accepts_utc_datetime(self):
        """Test that last_updated accepts UTC datetime."""
        now = datetime.now(UTC)
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            last_updated=now,
        )
        assert baseline.last_updated == now

    def test_last_updated_timezone_aware(self):
        """Test that last_updated can hold timezone-aware datetime."""
        now = datetime.now(UTC)
        baseline = ActivityBaseline(
            camera_id="test_cam",
            hour=0,
            day_of_week=0,
            last_updated=now,
        )
        assert baseline.last_updated.tzinfo is not None


class TestClassBaselineTimestamps:
    """Tests for ClassBaseline timestamp handling."""

    def test_last_updated_accepts_utc_datetime(self):
        """Test that last_updated accepts UTC datetime."""
        now = datetime.now(UTC)
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            last_updated=now,
        )
        assert baseline.last_updated == now

    def test_last_updated_timezone_aware(self):
        """Test that last_updated can hold timezone-aware datetime."""
        now = datetime.now(UTC)
        baseline = ClassBaseline(
            camera_id="test_cam",
            detection_class="person",
            hour=0,
            last_updated=now,
        )
        assert baseline.last_updated.tzinfo is not None


# =============================================================================
# Column Type Tests
# =============================================================================


class TestActivityBaselineColumnTypes:
    """Tests for ActivityBaseline column type definitions."""

    def test_id_is_integer_primary_key(self):
        """Test that id column is Integer primary key."""
        mapper = inspect(ActivityBaseline)
        id_col = mapper.columns["id"]
        assert id_col.primary_key
        assert id_col.autoincrement

    def test_camera_id_is_string(self):
        """Test that camera_id column is String."""
        mapper = inspect(ActivityBaseline)
        camera_id_col = mapper.columns["camera_id"]
        assert not camera_id_col.nullable

    def test_hour_is_integer_not_nullable(self):
        """Test that hour column is Integer and not nullable."""
        mapper = inspect(ActivityBaseline)
        hour_col = mapper.columns["hour"]
        assert not hour_col.nullable

    def test_day_of_week_is_integer_not_nullable(self):
        """Test that day_of_week column is Integer and not nullable."""
        mapper = inspect(ActivityBaseline)
        day_of_week_col = mapper.columns["day_of_week"]
        assert not day_of_week_col.nullable

    def test_avg_count_is_float_not_nullable(self):
        """Test that avg_count column is Float and not nullable."""
        mapper = inspect(ActivityBaseline)
        avg_count_col = mapper.columns["avg_count"]
        assert not avg_count_col.nullable

    def test_sample_count_is_integer_not_nullable(self):
        """Test that sample_count column is Integer and not nullable."""
        mapper = inspect(ActivityBaseline)
        sample_count_col = mapper.columns["sample_count"]
        assert not sample_count_col.nullable


class TestClassBaselineColumnTypes:
    """Tests for ClassBaseline column type definitions."""

    def test_id_is_integer_primary_key(self):
        """Test that id column is Integer primary key."""
        mapper = inspect(ClassBaseline)
        id_col = mapper.columns["id"]
        assert id_col.primary_key
        assert id_col.autoincrement

    def test_camera_id_is_string(self):
        """Test that camera_id column is String."""
        mapper = inspect(ClassBaseline)
        camera_id_col = mapper.columns["camera_id"]
        assert not camera_id_col.nullable

    def test_detection_class_is_string_not_nullable(self):
        """Test that detection_class column is String and not nullable."""
        mapper = inspect(ClassBaseline)
        detection_class_col = mapper.columns["detection_class"]
        assert not detection_class_col.nullable

    def test_hour_is_integer_not_nullable(self):
        """Test that hour column is Integer and not nullable."""
        mapper = inspect(ClassBaseline)
        hour_col = mapper.columns["hour"]
        assert not hour_col.nullable

    def test_frequency_is_float_not_nullable(self):
        """Test that frequency column is Float and not nullable."""
        mapper = inspect(ClassBaseline)
        frequency_col = mapper.columns["frequency"]
        assert not frequency_col.nullable

    def test_sample_count_is_integer_not_nullable(self):
        """Test that sample_count column is Integer and not nullable."""
        mapper = inspect(ClassBaseline)
        sample_count_col = mapper.columns["sample_count"]
        assert not sample_count_col.nullable
