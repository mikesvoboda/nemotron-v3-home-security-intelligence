"""Unit tests for UserCalibration model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Threshold ordering constraints
- Decay factor constraints
- Feedback count constraints
- Table indexes and constraints
- Property-based tests for field values

Related Linear issue: NEM-2352
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import CheckConstraint, inspect

from backend.models.user_calibration import UserCalibration

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid threshold values (0-100)
threshold_values = st.integers(min_value=0, max_value=100)

# Strategy for valid decay factor values (0.0-1.0)
decay_factors = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for valid feedback counts (non-negative)
feedback_counts = st.integers(min_value=0, max_value=10000)

# Strategy for valid user IDs
user_ids = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_calibration():
    """Create a sample UserCalibration for testing."""
    return UserCalibration(
        id=1,
        user_id="default",
        low_threshold=30,
        medium_threshold=60,
        high_threshold=85,
        decay_factor=0.1,
        false_positive_count=5,
        missed_detection_count=3,
    )


@pytest.fixture
def minimal_calibration():
    """Create a UserCalibration with minimal fields."""
    return UserCalibration(
        user_id="test_user",
    )


@pytest.fixture
def calibration_with_timestamps():
    """Create a UserCalibration with explicit timestamps."""
    now = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
    return UserCalibration(
        user_id="timed_user",
        low_threshold=25,
        medium_threshold=55,
        high_threshold=80,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def calibration_with_feedback():
    """Create a UserCalibration with feedback history."""
    return UserCalibration(
        user_id="feedback_user",
        low_threshold=35,
        medium_threshold=65,
        high_threshold=90,
        decay_factor=0.15,
        false_positive_count=20,
        missed_detection_count=15,
    )


# =============================================================================
# UserCalibration Model Initialization Tests
# =============================================================================


class TestUserCalibrationModelInitialization:
    """Tests for UserCalibration model initialization."""

    def test_calibration_creation_minimal(self, minimal_calibration):
        """Test creating calibration with minimal fields."""
        assert minimal_calibration.user_id == "test_user"

    def test_calibration_creation_with_all_fields(self, sample_calibration):
        """Test creating calibration with all fields populated."""
        assert sample_calibration.id == 1
        assert sample_calibration.user_id == "default"
        assert sample_calibration.low_threshold == 30
        assert sample_calibration.medium_threshold == 60
        assert sample_calibration.high_threshold == 85
        assert sample_calibration.decay_factor == 0.1
        assert sample_calibration.false_positive_count == 5
        assert sample_calibration.missed_detection_count == 3

    def test_calibration_with_explicit_timestamps(self, calibration_with_timestamps):
        """Test calibration with explicit timestamps."""
        expected_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        assert calibration_with_timestamps.created_at == expected_time
        assert calibration_with_timestamps.updated_at == expected_time

    def test_calibration_custom_thresholds(self):
        """Test calibration with custom thresholds."""
        calibration = UserCalibration(
            user_id="custom",
            low_threshold=20,
            medium_threshold=50,
            high_threshold=75,
        )
        assert calibration.low_threshold == 20
        assert calibration.medium_threshold == 50
        assert calibration.high_threshold == 75

    def test_calibration_custom_decay_factor(self):
        """Test calibration with custom decay factor."""
        calibration = UserCalibration(
            user_id="custom_decay",
            decay_factor=0.25,
        )
        assert calibration.decay_factor == 0.25

    def test_calibration_with_high_feedback_counts(self, calibration_with_feedback):
        """Test calibration with substantial feedback history."""
        assert calibration_with_feedback.false_positive_count == 20
        assert calibration_with_feedback.missed_detection_count == 15


# =============================================================================
# UserCalibration Column Definition Tests
# =============================================================================


class TestUserCalibrationColumnDefinitions:
    """Tests for UserCalibration column definitions."""

    def test_calibration_has_id_column(self):
        """Test UserCalibration has id column defined."""
        mapper = inspect(UserCalibration)
        assert "id" in mapper.columns

    def test_calibration_id_is_primary_key(self):
        """Test id column is primary key."""
        mapper = inspect(UserCalibration)
        id_col = mapper.columns["id"]
        assert id_col.primary_key

    def test_calibration_id_is_autoincrement(self):
        """Test id column is autoincrement."""
        mapper = inspect(UserCalibration)
        id_col = mapper.columns["id"]
        assert id_col.autoincrement is True or id_col.autoincrement == "auto"

    def test_calibration_has_user_id_column(self):
        """Test UserCalibration has user_id column defined."""
        mapper = inspect(UserCalibration)
        assert "user_id" in mapper.columns

    def test_calibration_user_id_is_not_nullable(self):
        """Test user_id column is not nullable."""
        mapper = inspect(UserCalibration)
        user_id_col = mapper.columns["user_id"]
        assert user_id_col.nullable is False

    def test_calibration_user_id_is_unique(self):
        """Test user_id column has unique constraint."""
        mapper = inspect(UserCalibration)
        user_id_col = mapper.columns["user_id"]
        assert user_id_col.unique is True

    def test_calibration_has_low_threshold_column(self):
        """Test UserCalibration has low_threshold column defined."""
        mapper = inspect(UserCalibration)
        assert "low_threshold" in mapper.columns

    def test_calibration_low_threshold_is_not_nullable(self):
        """Test low_threshold column is not nullable."""
        mapper = inspect(UserCalibration)
        col = mapper.columns["low_threshold"]
        assert col.nullable is False

    def test_calibration_low_threshold_has_default(self):
        """Test low_threshold column has default value."""
        mapper = inspect(UserCalibration)
        col = mapper.columns["low_threshold"]
        assert col.default is not None
        assert col.default.arg == 30

    def test_calibration_has_medium_threshold_column(self):
        """Test UserCalibration has medium_threshold column defined."""
        mapper = inspect(UserCalibration)
        assert "medium_threshold" in mapper.columns

    def test_calibration_medium_threshold_has_default(self):
        """Test medium_threshold column has default value."""
        mapper = inspect(UserCalibration)
        col = mapper.columns["medium_threshold"]
        assert col.default is not None
        assert col.default.arg == 60

    def test_calibration_has_high_threshold_column(self):
        """Test UserCalibration has high_threshold column defined."""
        mapper = inspect(UserCalibration)
        assert "high_threshold" in mapper.columns

    def test_calibration_high_threshold_has_default(self):
        """Test high_threshold column has default value."""
        mapper = inspect(UserCalibration)
        col = mapper.columns["high_threshold"]
        assert col.default is not None
        assert col.default.arg == 85

    def test_calibration_has_decay_factor_column(self):
        """Test UserCalibration has decay_factor column defined."""
        mapper = inspect(UserCalibration)
        assert "decay_factor" in mapper.columns

    def test_calibration_decay_factor_has_default(self):
        """Test decay_factor column has default value."""
        mapper = inspect(UserCalibration)
        col = mapper.columns["decay_factor"]
        assert col.default is not None
        assert col.default.arg == 0.1

    def test_calibration_has_false_positive_count_column(self):
        """Test UserCalibration has false_positive_count column defined."""
        mapper = inspect(UserCalibration)
        assert "false_positive_count" in mapper.columns

    def test_calibration_false_positive_count_has_default(self):
        """Test false_positive_count column has default value."""
        mapper = inspect(UserCalibration)
        col = mapper.columns["false_positive_count"]
        assert col.default is not None
        assert col.default.arg == 0

    def test_calibration_has_missed_detection_count_column(self):
        """Test UserCalibration has missed_detection_count column defined."""
        mapper = inspect(UserCalibration)
        assert "missed_detection_count" in mapper.columns

    def test_calibration_missed_detection_count_has_default(self):
        """Test missed_detection_count column has default value."""
        mapper = inspect(UserCalibration)
        col = mapper.columns["missed_detection_count"]
        assert col.default is not None
        assert col.default.arg == 0

    def test_calibration_has_created_at_column(self):
        """Test UserCalibration has created_at column defined."""
        mapper = inspect(UserCalibration)
        assert "created_at" in mapper.columns

    def test_calibration_has_updated_at_column(self):
        """Test UserCalibration has updated_at column defined."""
        mapper = inspect(UserCalibration)
        assert "updated_at" in mapper.columns


# =============================================================================
# UserCalibration Table Args Tests
# =============================================================================


class TestUserCalibrationTableArgs:
    """Tests for UserCalibration table arguments (indexes, constraints)."""

    def test_calibration_has_table_args(self):
        """Test UserCalibration model has __table_args__."""
        assert hasattr(UserCalibration, "__table_args__")

    def test_calibration_tablename(self):
        """Test UserCalibration has correct table name."""
        assert UserCalibration.__tablename__ == "user_calibration"

    def test_calibration_has_user_id_index(self):
        """Test UserCalibration has user_id index defined."""
        indexes = UserCalibration.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name") and idx.name]
        assert "idx_user_calibration_user_id" in index_names


# =============================================================================
# UserCalibration Constraints Tests
# =============================================================================


class TestUserCalibrationConstraints:
    """Tests for UserCalibration check constraints."""

    def test_calibration_has_low_range_constraint(self):
        """Test UserCalibration has low_threshold range CHECK constraint."""
        constraints = [
            arg for arg in UserCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_user_calibration_low_range" in constraint_names

    def test_calibration_has_medium_range_constraint(self):
        """Test UserCalibration has medium_threshold range CHECK constraint."""
        constraints = [
            arg for arg in UserCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_user_calibration_medium_range" in constraint_names

    def test_calibration_has_high_range_constraint(self):
        """Test UserCalibration has high_threshold range CHECK constraint."""
        constraints = [
            arg for arg in UserCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_user_calibration_high_range" in constraint_names

    def test_calibration_has_threshold_order_constraint(self):
        """Test UserCalibration has threshold ordering CHECK constraint."""
        constraints = [
            arg for arg in UserCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_user_calibration_threshold_order" in constraint_names

    def test_calibration_has_decay_range_constraint(self):
        """Test UserCalibration has decay_factor range CHECK constraint."""
        constraints = [
            arg for arg in UserCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_user_calibration_decay_range" in constraint_names

    def test_calibration_has_fp_count_constraint(self):
        """Test UserCalibration has false_positive_count CHECK constraint."""
        constraints = [
            arg for arg in UserCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_user_calibration_fp_count" in constraint_names

    def test_calibration_has_md_count_constraint(self):
        """Test UserCalibration has missed_detection_count CHECK constraint."""
        constraints = [
            arg for arg in UserCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_user_calibration_md_count" in constraint_names


# =============================================================================
# UserCalibration Repr Tests
# =============================================================================


class TestUserCalibrationRepr:
    """Tests for UserCalibration string representation."""

    def test_calibration_repr_contains_class_name(self, sample_calibration):
        """Test repr contains class name."""
        repr_str = repr(sample_calibration)
        assert "UserCalibration" in repr_str

    def test_calibration_repr_contains_id(self, sample_calibration):
        """Test repr contains calibration id."""
        repr_str = repr(sample_calibration)
        assert "id=1" in repr_str

    def test_calibration_repr_contains_user_id(self, sample_calibration):
        """Test repr contains user_id."""
        repr_str = repr(sample_calibration)
        assert "'default'" in repr_str

    def test_calibration_repr_contains_thresholds(self, sample_calibration):
        """Test repr contains threshold values."""
        repr_str = repr(sample_calibration)
        assert "low=30" in repr_str
        assert "medium=60" in repr_str
        assert "high=85" in repr_str

    def test_calibration_repr_format(self, sample_calibration):
        """Test repr has expected format."""
        repr_str = repr(sample_calibration)
        assert repr_str.startswith("<UserCalibration(")
        assert repr_str.endswith(")>")


# =============================================================================
# Threshold Value Tests
# =============================================================================


class TestUserCalibrationThresholdValues:
    """Tests for valid threshold value scenarios."""

    def test_minimum_valid_thresholds(self):
        """Test calibration with minimum valid threshold values."""
        calibration = UserCalibration(
            user_id="min_thresh",
            low_threshold=1,
            medium_threshold=2,
            high_threshold=3,
        )
        assert calibration.low_threshold == 1
        assert calibration.medium_threshold == 2
        assert calibration.high_threshold == 3

    def test_maximum_valid_thresholds(self):
        """Test calibration with maximum valid threshold values."""
        calibration = UserCalibration(
            user_id="max_thresh",
            low_threshold=97,
            medium_threshold=98,
            high_threshold=99,
        )
        assert calibration.low_threshold == 97
        assert calibration.medium_threshold == 98
        assert calibration.high_threshold == 99

    def test_wide_gap_thresholds(self):
        """Test calibration with wide gaps between thresholds."""
        calibration = UserCalibration(
            user_id="wide_gap",
            low_threshold=10,
            medium_threshold=50,
            high_threshold=90,
        )
        assert calibration.medium_threshold - calibration.low_threshold == 40
        assert calibration.high_threshold - calibration.medium_threshold == 40

    def test_narrow_gap_thresholds(self):
        """Test calibration with narrow (but valid) gaps between thresholds."""
        calibration = UserCalibration(
            user_id="narrow_gap",
            low_threshold=48,
            medium_threshold=49,
            high_threshold=50,
        )
        assert calibration.medium_threshold - calibration.low_threshold == 1
        assert calibration.high_threshold - calibration.medium_threshold == 1


# =============================================================================
# Decay Factor Tests
# =============================================================================


class TestUserCalibrationDecayFactor:
    """Tests for decay factor values."""

    def test_minimum_decay_factor(self):
        """Test calibration with minimum decay factor (0.0)."""
        calibration = UserCalibration(
            user_id="min_decay",
            decay_factor=0.0,
        )
        assert calibration.decay_factor == 0.0

    def test_maximum_decay_factor(self):
        """Test calibration with maximum decay factor (1.0)."""
        calibration = UserCalibration(
            user_id="max_decay",
            decay_factor=1.0,
        )
        assert calibration.decay_factor == 1.0

    def test_typical_decay_factor(self):
        """Test calibration with typical decay factor values."""
        for factor in [0.05, 0.1, 0.15, 0.2, 0.25]:
            calibration = UserCalibration(
                user_id=f"decay_{factor}",
                decay_factor=factor,
            )
            assert calibration.decay_factor == factor


# =============================================================================
# Feedback Count Tests
# =============================================================================


class TestUserCalibrationFeedbackCounts:
    """Tests for feedback count tracking."""

    def test_zero_feedback_counts(self):
        """Test calibration with zero feedback counts."""
        calibration = UserCalibration(
            user_id="zero_feedback",
            false_positive_count=0,
            missed_detection_count=0,
        )
        assert calibration.false_positive_count == 0
        assert calibration.missed_detection_count == 0

    def test_high_feedback_counts(self):
        """Test calibration with high feedback counts."""
        calibration = UserCalibration(
            user_id="high_feedback",
            false_positive_count=1000,
            missed_detection_count=500,
        )
        assert calibration.false_positive_count == 1000
        assert calibration.missed_detection_count == 500

    def test_asymmetric_feedback_counts(self):
        """Test calibration with asymmetric feedback (more FPs than missed)."""
        calibration = UserCalibration(
            user_id="asymmetric",
            false_positive_count=100,
            missed_detection_count=10,
        )
        # More false positives suggests system is too sensitive
        assert calibration.false_positive_count > calibration.missed_detection_count


# =============================================================================
# Property-based Tests
# =============================================================================


class TestUserCalibrationProperties:
    """Property-based tests for UserCalibration model."""

    @given(user_id=user_ids)
    @settings(max_examples=50)
    def test_user_id_roundtrip(self, user_id: str):
        """Property: User ID values roundtrip correctly."""
        calibration = UserCalibration(user_id=user_id)
        assert calibration.user_id == user_id

    @given(decay_factor=decay_factors)
    @settings(max_examples=50)
    def test_decay_factor_roundtrip(self, decay_factor: float):
        """Property: Decay factor values roundtrip correctly."""
        calibration = UserCalibration(
            user_id="test",
            decay_factor=decay_factor,
        )
        # Allow for floating point precision
        assert abs(calibration.decay_factor - decay_factor) < 1e-10

    @given(fp_count=feedback_counts, md_count=feedback_counts)
    @settings(max_examples=50)
    def test_feedback_counts_roundtrip(self, fp_count: int, md_count: int):
        """Property: Feedback count values roundtrip correctly."""
        calibration = UserCalibration(
            user_id="test",
            false_positive_count=fp_count,
            missed_detection_count=md_count,
        )
        assert calibration.false_positive_count == fp_count
        assert calibration.missed_detection_count == md_count

    @given(
        low=st.integers(min_value=0, max_value=32),
        gap1=st.integers(min_value=1, max_value=32),
        gap2=st.integers(min_value=1, max_value=32),
    )
    @settings(max_examples=100)
    def test_valid_threshold_ordering(self, low: int, gap1: int, gap2: int):
        """Property: Valid threshold orderings are accepted."""
        medium = low + gap1
        high = medium + gap2

        # Only test if all values are in valid range
        if high <= 100:
            calibration = UserCalibration(
                user_id="test",
                low_threshold=low,
                medium_threshold=medium,
                high_threshold=high,
            )
            assert calibration.low_threshold < calibration.medium_threshold
            assert calibration.medium_threshold < calibration.high_threshold


# =============================================================================
# Default User ID Tests
# =============================================================================


class TestUserCalibrationDefaultUser:
    """Tests for the default user ID convention."""

    def test_default_user_id_value(self):
        """Test 'default' is the standard user ID for single-user systems."""
        calibration = UserCalibration(user_id="default")
        assert calibration.user_id == "default"

    def test_default_user_calibration_defaults(self):
        """Test default calibration values for default user."""
        # These are the documented defaults
        calibration = UserCalibration(
            user_id="default",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
        )
        assert calibration.low_threshold == 30  # 0-29 = low risk
        assert calibration.medium_threshold == 60  # 30-59 = medium risk
        assert calibration.high_threshold == 85  # 60-84 = high, 85-100 = critical


# =============================================================================
# Semantic Tests
# =============================================================================


class TestUserCalibrationSemantics:
    """Tests for UserCalibration semantic meaning and usage."""

    def test_low_threshold_meaning(self, sample_calibration):
        """Test low_threshold semantic meaning.

        Scores below low_threshold are classified as LOW risk.
        """
        # With low_threshold=30, scores 0-29 are LOW risk
        assert sample_calibration.low_threshold == 30

    def test_medium_threshold_meaning(self, sample_calibration):
        """Test medium_threshold semantic meaning.

        Scores at or above low_threshold but below medium_threshold are MEDIUM risk.
        """
        # With medium_threshold=60, scores 30-59 are MEDIUM risk
        assert sample_calibration.medium_threshold == 60

    def test_high_threshold_meaning(self, sample_calibration):
        """Test high_threshold semantic meaning.

        Scores at or above medium_threshold but below high_threshold are HIGH risk.
        Scores at or above high_threshold are CRITICAL risk.
        """
        # With high_threshold=85, scores 60-84 are HIGH, 85-100 are CRITICAL
        assert sample_calibration.high_threshold == 85

    def test_decay_factor_controls_learning_rate(self, sample_calibration):
        """Test decay_factor semantic meaning.

        Decay factor controls how quickly thresholds adapt to feedback.
        Lower values = slower adjustment, higher values = faster adjustment.
        """
        assert 0.0 <= sample_calibration.decay_factor <= 1.0
        # Default is 0.1 which provides gradual adjustment
        assert sample_calibration.decay_factor == 0.1

    def test_feedback_counts_track_history(self, calibration_with_feedback):
        """Test feedback count tracking.

        Feedback counts help understand calibration reliability.
        More feedback = more confidence in calibrated thresholds.
        """
        total_feedback = (
            calibration_with_feedback.false_positive_count
            + calibration_with_feedback.missed_detection_count
        )
        assert total_feedback == 35  # 20 FPs + 15 missed detections
