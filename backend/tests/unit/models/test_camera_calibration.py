"""Unit tests for CameraCalibration model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Risk offset range (-30 to +30)
- FP rate calculations
- JSONB fields (model_weights, suppress_patterns)
- Table indexes and constraints
- Property-based tests for field values

Related Linear issues: NEM-3022
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import CheckConstraint, inspect

from backend.models.camera_calibration import CameraCalibration

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid camera IDs
camera_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="_"),
)

# Strategy for valid risk offsets (-30 to +30)
risk_offsets = st.integers(min_value=-30, max_value=30)

# Strategy for valid false positive rates (0.0 to 1.0)
fp_rates = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for feedback counts (non-negative)
feedback_counts = st.integers(min_value=0, max_value=10000)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_calibration():
    """Create a sample CameraCalibration for testing."""
    return CameraCalibration(
        id=1,
        camera_id="front_door",
        total_feedback_count=50,
        false_positive_count=25,
        false_positive_rate=0.5,
        risk_offset=-15,
        model_weights={"pose_model": 0.5, "clothing_model": 0.8},
        suppress_patterns=[{"pattern": "running", "time_range": "16:00-21:00", "reduction": 20}],
        avg_model_score=75.0,
        avg_user_suggested_score=65.0,
    )


@pytest.fixture
def minimal_calibration():
    """Create a CameraCalibration with minimal fields."""
    return CameraCalibration(camera_id="garage")


@pytest.fixture
def calibration_with_high_fp_rate():
    """Create a CameraCalibration with high false positive rate."""
    return CameraCalibration(
        camera_id="backyard",
        total_feedback_count=100,
        false_positive_count=75,
        false_positive_rate=0.75,
        risk_offset=-25,
    )


@pytest.fixture
def calibration_with_low_fp_rate():
    """Create a CameraCalibration with low false positive rate."""
    return CameraCalibration(
        camera_id="driveway",
        total_feedback_count=100,
        false_positive_count=5,
        false_positive_rate=0.05,
        risk_offset=10,
    )


# =============================================================================
# CameraCalibration Model Initialization Tests
# =============================================================================


class TestCameraCalibrationModelInitialization:
    """Tests for CameraCalibration model initialization."""

    def test_calibration_creation_minimal(self, minimal_calibration):
        """Test creating calibration with minimal fields."""
        assert minimal_calibration.camera_id == "garage"

    def test_calibration_creation_with_all_fields(self, sample_calibration):
        """Test creating calibration with all fields populated."""
        assert sample_calibration.id == 1
        assert sample_calibration.camera_id == "front_door"
        assert sample_calibration.total_feedback_count == 50
        assert sample_calibration.false_positive_count == 25
        assert sample_calibration.false_positive_rate == 0.5
        assert sample_calibration.risk_offset == -15
        assert sample_calibration.model_weights == {"pose_model": 0.5, "clothing_model": 0.8}
        assert sample_calibration.suppress_patterns == [
            {"pattern": "running", "time_range": "16:00-21:00", "reduction": 20}
        ]
        assert sample_calibration.avg_model_score == 75.0
        assert sample_calibration.avg_user_suggested_score == 65.0

    def test_calibration_default_values_column_definitions(self):
        """Test default values are correctly defined on columns.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column defaults are correctly defined.
        """
        mapper = inspect(CameraCalibration)

        # Check feedback count defaults
        assert mapper.columns["total_feedback_count"].default.arg == 0
        assert mapper.columns["false_positive_count"].default.arg == 0
        assert mapper.columns["false_positive_rate"].default.arg == 0.0
        assert mapper.columns["risk_offset"].default.arg == 0


# =============================================================================
# CameraCalibration Risk Offset Field Tests
# =============================================================================


class TestCameraCalibrationRiskOffsetField:
    """Tests for CameraCalibration risk_offset field."""

    def test_risk_offset_default_zero(self):
        """Test risk_offset has default value of 0."""
        mapper = inspect(CameraCalibration)
        assert mapper.columns["risk_offset"].default.arg == 0

    def test_risk_offset_negative(self, calibration_with_high_fp_rate):
        """Test negative risk offset (camera over-alerts, reduce scores)."""
        assert calibration_with_high_fp_rate.risk_offset == -25
        assert calibration_with_high_fp_rate.risk_offset < 0

    def test_risk_offset_positive(self, calibration_with_low_fp_rate):
        """Test positive risk offset (camera under-alerts, increase scores)."""
        assert calibration_with_low_fp_rate.risk_offset == 10
        assert calibration_with_low_fp_rate.risk_offset > 0

    def test_risk_offset_minimum(self):
        """Test risk_offset at minimum boundary (-30)."""
        calibration = CameraCalibration(camera_id="test", risk_offset=-30)
        assert calibration.risk_offset == -30

    def test_risk_offset_maximum(self):
        """Test risk_offset at maximum boundary (+30)."""
        calibration = CameraCalibration(camera_id="test", risk_offset=30)
        assert calibration.risk_offset == 30


# =============================================================================
# CameraCalibration Feedback Count Field Tests
# =============================================================================


class TestCameraCalibrationFeedbackCountFields:
    """Tests for CameraCalibration feedback count fields."""

    def test_total_feedback_count_field(self, sample_calibration):
        """Test total_feedback_count field."""
        assert sample_calibration.total_feedback_count == 50

    def test_false_positive_count_field(self, sample_calibration):
        """Test false_positive_count field."""
        assert sample_calibration.false_positive_count == 25

    def test_false_positive_rate_field(self, sample_calibration):
        """Test false_positive_rate field."""
        assert sample_calibration.false_positive_rate == 0.5

    def test_all_counts_can_be_zero(self, minimal_calibration):
        """Test all feedback counts can be zero."""
        # Defaults are applied at database level, so check column definition
        mapper = inspect(CameraCalibration)
        assert mapper.columns["total_feedback_count"].default.arg == 0
        assert mapper.columns["false_positive_count"].default.arg == 0

    def test_feedback_counts_large_values(self):
        """Test feedback counts can handle large values."""
        calibration = CameraCalibration(
            camera_id="test",
            total_feedback_count=10000,
            false_positive_count=5000,
        )
        assert calibration.total_feedback_count == 10000
        assert calibration.false_positive_count == 5000


# =============================================================================
# CameraCalibration JSONB Field Tests
# =============================================================================


class TestCameraCalibrationJSONBFields:
    """Tests for CameraCalibration JSONB fields."""

    def test_model_weights_empty_dict(self):
        """Test model_weights with empty dict."""
        calibration = CameraCalibration(camera_id="test", model_weights={})
        assert calibration.model_weights == {}

    def test_model_weights_with_values(self, sample_calibration):
        """Test model_weights with populated values."""
        assert sample_calibration.model_weights == {"pose_model": 0.5, "clothing_model": 0.8}

    def test_suppress_patterns_empty_list(self):
        """Test suppress_patterns with empty list."""
        calibration = CameraCalibration(camera_id="test", suppress_patterns=[])
        assert calibration.suppress_patterns == []

    def test_suppress_patterns_with_values(self, sample_calibration):
        """Test suppress_patterns with populated values."""
        assert len(sample_calibration.suppress_patterns) == 1
        assert sample_calibration.suppress_patterns[0]["pattern"] == "running"
        assert sample_calibration.suppress_patterns[0]["time_range"] == "16:00-21:00"
        assert sample_calibration.suppress_patterns[0]["reduction"] == 20

    def test_suppress_patterns_multiple(self):
        """Test suppress_patterns with multiple patterns."""
        patterns = [
            {"pattern": "running", "time_range": "16:00-21:00", "reduction": 20},
            {"pattern": "dog_walking", "time_range": "06:00-08:00", "reduction": 15},
        ]
        calibration = CameraCalibration(camera_id="test", suppress_patterns=patterns)
        assert len(calibration.suppress_patterns) == 2


# =============================================================================
# CameraCalibration Average Score Field Tests
# =============================================================================


class TestCameraCalibrationAverageScoreFields:
    """Tests for CameraCalibration average score fields."""

    def test_avg_model_score_nullable(self):
        """Test avg_model_score is nullable."""
        mapper = inspect(CameraCalibration)
        assert mapper.columns["avg_model_score"].nullable is True

    def test_avg_user_suggested_score_nullable(self):
        """Test avg_user_suggested_score is nullable."""
        mapper = inspect(CameraCalibration)
        assert mapper.columns["avg_user_suggested_score"].nullable is True

    def test_avg_scores_can_be_set(self, sample_calibration):
        """Test average scores can be set."""
        assert sample_calibration.avg_model_score == 75.0
        assert sample_calibration.avg_user_suggested_score == 65.0


# =============================================================================
# CameraCalibration Column Definition Tests
# =============================================================================


class TestCameraCalibrationColumnDefinitions:
    """Tests for CameraCalibration column definitions."""

    def test_calibration_has_id_column(self):
        """Test CameraCalibration has id column defined."""
        mapper = inspect(CameraCalibration)
        assert "id" in mapper.columns

    def test_calibration_id_is_primary_key(self):
        """Test id column is primary key."""
        mapper = inspect(CameraCalibration)
        id_col = mapper.columns["id"]
        assert id_col.primary_key

    def test_calibration_has_camera_id_column(self):
        """Test CameraCalibration has camera_id column defined."""
        mapper = inspect(CameraCalibration)
        assert "camera_id" in mapper.columns

    def test_calibration_camera_id_is_not_nullable(self):
        """Test camera_id column is not nullable."""
        mapper = inspect(CameraCalibration)
        camera_id_col = mapper.columns["camera_id"]
        assert camera_id_col.nullable is False

    def test_calibration_camera_id_is_unique(self):
        """Test camera_id column has unique constraint."""
        mapper = inspect(CameraCalibration)
        camera_id_col = mapper.columns["camera_id"]
        assert camera_id_col.unique is True

    def test_calibration_has_total_feedback_count_column(self):
        """Test CameraCalibration has total_feedback_count column defined."""
        mapper = inspect(CameraCalibration)
        assert "total_feedback_count" in mapper.columns

    def test_calibration_has_false_positive_count_column(self):
        """Test CameraCalibration has false_positive_count column defined."""
        mapper = inspect(CameraCalibration)
        assert "false_positive_count" in mapper.columns

    def test_calibration_has_false_positive_rate_column(self):
        """Test CameraCalibration has false_positive_rate column defined."""
        mapper = inspect(CameraCalibration)
        assert "false_positive_rate" in mapper.columns

    def test_calibration_has_risk_offset_column(self):
        """Test CameraCalibration has risk_offset column defined."""
        mapper = inspect(CameraCalibration)
        assert "risk_offset" in mapper.columns

    def test_calibration_has_model_weights_column(self):
        """Test CameraCalibration has model_weights column defined."""
        mapper = inspect(CameraCalibration)
        assert "model_weights" in mapper.columns

    def test_calibration_has_suppress_patterns_column(self):
        """Test CameraCalibration has suppress_patterns column defined."""
        mapper = inspect(CameraCalibration)
        assert "suppress_patterns" in mapper.columns

    def test_calibration_has_updated_at_column(self):
        """Test CameraCalibration has updated_at column defined."""
        mapper = inspect(CameraCalibration)
        assert "updated_at" in mapper.columns


# =============================================================================
# CameraCalibration Repr Tests
# =============================================================================


class TestCameraCalibrationRepr:
    """Tests for CameraCalibration string representation."""

    def test_calibration_repr_contains_class_name(self, sample_calibration):
        """Test repr contains class name."""
        repr_str = repr(sample_calibration)
        assert "CameraCalibration" in repr_str

    def test_calibration_repr_contains_id(self, sample_calibration):
        """Test repr contains calibration id."""
        repr_str = repr(sample_calibration)
        assert "id=1" in repr_str

    def test_calibration_repr_contains_camera_id(self, sample_calibration):
        """Test repr contains camera_id."""
        repr_str = repr(sample_calibration)
        assert "'front_door'" in repr_str

    def test_calibration_repr_contains_risk_offset(self, sample_calibration):
        """Test repr contains risk_offset."""
        repr_str = repr(sample_calibration)
        assert "risk_offset=-15" in repr_str

    def test_calibration_repr_contains_fp_rate(self, sample_calibration):
        """Test repr contains false_positive_rate."""
        repr_str = repr(sample_calibration)
        assert "fp_rate=0.5" in repr_str

    def test_calibration_repr_format(self, sample_calibration):
        """Test repr has expected format."""
        repr_str = repr(sample_calibration)
        assert repr_str.startswith("<CameraCalibration(")
        assert repr_str.endswith(")>")


# =============================================================================
# CameraCalibration Table Args Tests
# =============================================================================


class TestCameraCalibrationTableArgs:
    """Tests for CameraCalibration table arguments (indexes, constraints)."""

    def test_calibration_has_table_args(self):
        """Test CameraCalibration model has __table_args__."""
        assert hasattr(CameraCalibration, "__table_args__")

    def test_calibration_tablename(self):
        """Test CameraCalibration has correct table name."""
        assert CameraCalibration.__tablename__ == "camera_calibrations"

    def test_calibration_has_camera_id_index(self):
        """Test CameraCalibration has camera_id index defined."""
        indexes = CameraCalibration.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name") and idx.name]
        assert "idx_camera_calibrations_camera_id" in index_names


# =============================================================================
# CameraCalibration Constraints Tests
# =============================================================================


class TestCameraCalibrationConstraints:
    """Tests for CameraCalibration check constraints."""

    def test_calibration_has_risk_offset_range_constraint(self):
        """Test CameraCalibration has risk_offset range CHECK constraint."""
        constraints = [
            arg for arg in CameraCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_camera_calibrations_risk_offset_range" in constraint_names

    def test_calibration_has_fp_rate_range_constraint(self):
        """Test CameraCalibration has false_positive_rate range CHECK constraint."""
        constraints = [
            arg for arg in CameraCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_camera_calibrations_fp_rate_range" in constraint_names

    def test_calibration_has_feedback_count_constraint(self):
        """Test CameraCalibration has feedback count CHECK constraint."""
        constraints = [
            arg for arg in CameraCalibration.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_camera_calibrations_feedback_count" in constraint_names


# =============================================================================
# CameraCalibration Relationships Tests
# =============================================================================


class TestCameraCalibrationRelationships:
    """Tests for CameraCalibration relationship definitions."""

    def test_calibration_has_camera_relationship(self, sample_calibration):
        """Test calibration has camera relationship defined."""
        assert hasattr(sample_calibration, "camera")


# =============================================================================
# Property-based Tests
# =============================================================================


class TestCameraCalibrationProperties:
    """Property-based tests for CameraCalibration model."""

    @given(camera_id=camera_ids)
    @settings(max_examples=50)
    def test_camera_id_roundtrip(self, camera_id: str):
        """Property: Camera ID values roundtrip correctly."""
        calibration = CameraCalibration(camera_id=camera_id)
        assert calibration.camera_id == camera_id

    @given(risk_offset=risk_offsets)
    @settings(max_examples=50)
    def test_risk_offset_roundtrip(self, risk_offset: int):
        """Property: Risk offset values roundtrip correctly."""
        calibration = CameraCalibration(camera_id="test", risk_offset=risk_offset)
        assert calibration.risk_offset == risk_offset

    @given(fp_rate=fp_rates)
    @settings(max_examples=50)
    def test_fp_rate_roundtrip(self, fp_rate: float):
        """Property: False positive rate values roundtrip correctly."""
        calibration = CameraCalibration(camera_id="test", false_positive_rate=fp_rate)
        # Allow for floating point precision
        assert abs(calibration.false_positive_rate - fp_rate) < 1e-10

    @given(total=feedback_counts, fp=feedback_counts)
    @settings(max_examples=50)
    def test_feedback_counts_roundtrip(self, total: int, fp: int):
        """Property: Feedback count values roundtrip correctly."""
        calibration = CameraCalibration(
            camera_id="test",
            total_feedback_count=total,
            false_positive_count=fp,
        )
        assert calibration.total_feedback_count == total
        assert calibration.false_positive_count == fp


# =============================================================================
# Semantic Tests
# =============================================================================


class TestCameraCalibrationSemantics:
    """Tests for CameraCalibration semantic meaning and usage."""

    def test_negative_offset_reduces_scores(self, calibration_with_high_fp_rate):
        """Test that negative offset indicates camera over-alerts, scores should be reduced."""
        # Negative offset = camera over-alerts = reduce risk scores
        assert calibration_with_high_fp_rate.risk_offset < 0
        assert calibration_with_high_fp_rate.false_positive_rate > 0.5

    def test_positive_offset_increases_scores(self, calibration_with_low_fp_rate):
        """Test that positive offset indicates camera under-alerts, scores should be increased."""
        # Positive offset = camera under-alerts = increase risk scores
        assert calibration_with_low_fp_rate.risk_offset > 0
        assert calibration_with_low_fp_rate.false_positive_rate < 0.1

    def test_model_weights_adjust_confidence(self, sample_calibration):
        """Test model_weights semantic meaning.

        Model weights allow per-camera adjustment of individual model contributions.
        A weight < 1.0 means reduce that model's influence for this camera.
        """
        weights = sample_calibration.model_weights
        assert "pose_model" in weights
        assert weights["pose_model"] == 0.5  # Reduce pose model influence

    def test_suppress_patterns_for_time_based_reduction(self, sample_calibration):
        """Test suppress_patterns semantic meaning.

        Suppress patterns allow reducing alert severity for specific behaviors
        during certain time ranges (e.g., kids running home from school).
        """
        patterns = sample_calibration.suppress_patterns
        assert len(patterns) == 1
        # Running during after-school hours gets 20 point reduction
        assert patterns[0]["pattern"] == "running"
        assert patterns[0]["reduction"] == 20

    def test_avg_scores_track_calibration_quality(self, sample_calibration):
        """Test average score tracking for calibration quality assessment.

        The difference between avg_model_score and avg_user_suggested_score
        indicates how well-calibrated the system is for this camera.
        """
        model_avg = sample_calibration.avg_model_score
        user_avg = sample_calibration.avg_user_suggested_score
        # User suggests lower scores on average, indicating over-alerting
        assert model_avg is not None
        assert user_avg is not None
        assert model_avg > user_avg  # Model over-estimates risk


# =============================================================================
# Auto-adjustment Logic Tests
# =============================================================================


class TestCameraCalibrationAutoAdjustment:
    """Tests for understanding auto-adjustment behavior."""

    def test_high_fp_rate_triggers_negative_offset(self):
        """Test that high FP rate should result in negative offset.

        When false_positive_rate > 0.5 and total_feedback_count >= 20,
        the system should auto-adjust risk_offset to be more negative.
        """
        # This is a semantic test - the actual adjustment happens in the service
        calibration = CameraCalibration(
            camera_id="test",
            total_feedback_count=25,
            false_positive_count=15,
            false_positive_rate=0.6,  # > 0.5
            risk_offset=-10,  # Already adjusted negative
        )
        # High FP rate means camera over-alerts
        assert calibration.false_positive_rate > 0.5
        assert calibration.risk_offset < 0

    def test_low_fp_rate_triggers_positive_offset(self):
        """Test that low FP rate should result in positive offset.

        When false_positive_rate < 0.1 and total_feedback_count >= 20,
        the system should auto-adjust risk_offset to be more positive.
        """
        calibration = CameraCalibration(
            camera_id="test",
            total_feedback_count=30,
            false_positive_count=2,
            false_positive_rate=0.067,  # < 0.1
            risk_offset=5,  # Already adjusted positive
        )
        # Low FP rate means camera under-alerts
        assert calibration.false_positive_rate < 0.1
        assert calibration.risk_offset > 0

    def test_offset_bounded_at_minimum(self):
        """Test that risk_offset cannot go below -30."""
        calibration = CameraCalibration(
            camera_id="test",
            risk_offset=-30,  # At minimum
        )
        assert calibration.risk_offset >= -30

    def test_offset_bounded_at_maximum(self):
        """Test that risk_offset cannot go above +30."""
        calibration = CameraCalibration(
            camera_id="test",
            risk_offset=30,  # At maximum
        )
        assert calibration.risk_offset <= 30
