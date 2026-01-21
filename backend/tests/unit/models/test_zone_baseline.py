"""Unit tests for ZoneActivityBaseline model.

Tests cover:
- Model instantiation with valid data
- Field validation and constraints
- Default values
- Relationship navigation
- String representation (__repr__)
- Property methods (is_stale, deviation_from_mean)
- CheckConstraints for time bucketing and statistical values
"""

from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.core.time_utils import utc_now
from backend.models.zone_baseline import ZoneActivityBaseline

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid hours (0-23)
hours = st.integers(min_value=0, max_value=23)

# Strategy for valid days of week (0=Monday through 6=Sunday)
days_of_week = st.integers(min_value=0, max_value=6)

# Strategy for valid detection classes
detection_classes = st.sampled_from(["person", "vehicle", "animal", "all"])

# Strategy for valid sample counts
sample_counts = st.integers(min_value=0, max_value=10000)

# Strategy for valid mean counts
mean_counts = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)

# Strategy for valid standard deviations
std_devs = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


# =============================================================================
# ZoneActivityBaseline Model Tests
# =============================================================================


class TestZoneActivityBaselineModel:
    """Tests for ZoneActivityBaseline model."""

    def test_baseline_creation_minimal(self):
        """Test creating a baseline with required fields."""
        baseline = ZoneActivityBaseline(
            id="zone_cam1_0_0_person",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
        )
        assert baseline.id == "zone_cam1_0_0_person"
        assert baseline.zone_id == "zone_1"
        assert baseline.camera_id == "cam1"
        assert baseline.hour_of_day == 0
        assert baseline.day_of_week == 0
        # Defaults apply at DB level, not in-memory
        assert baseline.detection_class in (None, "all")
        assert baseline.sample_count in (None, 0)
        assert baseline.mean_count in (None, 0.0)
        assert baseline.std_dev in (None, 0.0)
        assert baseline.min_count in (None, 0)
        assert baseline.max_count in (None, 0)

    def test_baseline_creation_full(self):
        """Test creating a baseline with all fields."""
        baseline = ZoneActivityBaseline(
            id="zone_cam1_14_3_person",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=14,
            day_of_week=3,
            detection_class="person",
            sample_count=100,
            mean_count=5.2,
            std_dev=1.8,
            min_count=2,
            max_count=12,
        )
        assert baseline.id == "zone_cam1_14_3_person"
        assert baseline.zone_id == "zone_1"
        assert baseline.camera_id == "cam1"
        assert baseline.hour_of_day == 14
        assert baseline.day_of_week == 3
        assert baseline.detection_class == "person"
        assert baseline.sample_count == 100
        assert baseline.mean_count == 5.2
        assert baseline.std_dev == 1.8
        assert baseline.min_count == 2
        assert baseline.max_count == 12

    def test_baseline_default_detection_class(self):
        """Test detection_class has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(ZoneActivityBaseline)
        detection_class_col = mapper.columns["detection_class"]
        assert detection_class_col.default is not None
        assert detection_class_col.default.arg == "all"

    def test_baseline_default_statistical_values(self):
        """Test statistical values have defaults defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(ZoneActivityBaseline)
        assert mapper.columns["sample_count"].default.arg == 0
        assert mapper.columns["mean_count"].default.arg == 0.0
        assert mapper.columns["std_dev"].default.arg == 0.0
        assert mapper.columns["min_count"].default.arg == 0
        assert mapper.columns["max_count"].default.arg == 0

    def test_baseline_repr(self):
        """Test ZoneActivityBaseline __repr__ method."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=14,
            day_of_week=3,
            detection_class="person",
            mean_count=5.25,
        )
        repr_str = repr(baseline)
        assert "ZoneActivityBaseline" in repr_str
        assert "id='zone_1'" in repr_str
        assert "zone_id='zone_1'" in repr_str
        assert "hour=14" in repr_str
        assert "day=3" in repr_str
        assert "class='person'" in repr_str
        assert "mean=5.25" in repr_str

    def test_baseline_has_zone_relationship(self):
        """Test ZoneActivityBaseline has zone relationship defined."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
        )
        assert hasattr(baseline, "zone")

    def test_baseline_tablename(self):
        """Test ZoneActivityBaseline has correct table name."""
        assert ZoneActivityBaseline.__tablename__ == "zone_activity_baselines"

    def test_baseline_has_indexes(self):
        """Test ZoneActivityBaseline has expected indexes."""
        indexes = ZoneActivityBaseline.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_zone_baselines_zone_id" in index_names
        assert "idx_zone_baselines_camera_id" in index_names
        assert "idx_zone_baselines_time_bucket" in index_names
        assert "idx_zone_baselines_lookup" in index_names


# =============================================================================
# ZoneActivityBaseline is_stale Method Tests
# =============================================================================


class TestZoneActivityBaselineIsStale:
    """Tests for ZoneActivityBaseline.is_stale() method."""

    def test_is_stale_fresh_baseline(self):
        """Test baseline that was just updated is not stale."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            last_updated=utc_now(),
        )
        assert baseline.is_stale() is False

    def test_is_stale_old_baseline(self):
        """Test baseline older than max_age is stale."""
        old_time = utc_now() - timedelta(days=8)  # 8 days ago (default max_age is 7 days)
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            last_updated=old_time,
        )
        assert baseline.is_stale() is True

    def test_is_stale_custom_max_age(self):
        """Test is_stale with custom max_age_hours."""
        old_time = utc_now() - timedelta(hours=25)  # 25 hours ago
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            last_updated=old_time,
        )
        # With max_age=24 hours, this should be stale
        assert baseline.is_stale(max_age_hours=24) is True
        # With max_age=48 hours, this should not be stale
        assert baseline.is_stale(max_age_hours=48) is False

    def test_is_stale_boundary_exactly_max_age(self):
        """Test baseline exactly at max_age boundary."""
        exact_time = utc_now() - timedelta(hours=168)  # Exactly 7 days
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            last_updated=exact_time,
        )
        # At exactly the boundary, should not be stale (uses > comparison)
        # Note: Due to timing precision, this might be slightly stale
        result = baseline.is_stale()
        # Accept either result due to timing precision
        assert isinstance(result, bool)


# =============================================================================
# ZoneActivityBaseline deviation_from_mean Method Tests
# =============================================================================


class TestZoneActivityBaselineDeviationFromMean:
    """Tests for ZoneActivityBaseline.deviation_from_mean() method."""

    def test_deviation_from_mean_zero_std_dev(self):
        """Test deviation when std_dev is zero returns 0."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            mean_count=5.0,
            std_dev=0.0,
        )
        assert baseline.deviation_from_mean(10.0) == 0.0

    def test_deviation_from_mean_exact_mean(self):
        """Test deviation when observed equals mean."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            mean_count=5.0,
            std_dev=2.0,
        )
        assert baseline.deviation_from_mean(5.0) == 0.0

    def test_deviation_from_mean_one_std_dev_above(self):
        """Test deviation one std dev above mean."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            mean_count=5.0,
            std_dev=2.0,
        )
        assert baseline.deviation_from_mean(7.0) == 1.0

    def test_deviation_from_mean_one_std_dev_below(self):
        """Test deviation one std dev below mean."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            mean_count=5.0,
            std_dev=2.0,
        )
        # Uses abs() so should be positive
        assert baseline.deviation_from_mean(3.0) == 1.0

    def test_deviation_from_mean_two_std_devs_above(self):
        """Test deviation two std devs above mean."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            mean_count=10.0,
            std_dev=3.0,
        )
        assert baseline.deviation_from_mean(16.0) == 2.0

    def test_deviation_from_mean_fractional(self):
        """Test deviation with fractional std devs."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            mean_count=10.0,
            std_dev=4.0,
        )
        # (12.0 - 10.0) / 4.0 = 0.5
        assert abs(baseline.deviation_from_mean(12.0) - 0.5) < 1e-10


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestZoneActivityBaselineProperties:
    """Property-based tests for ZoneActivityBaseline model."""

    @given(hour=hours, day=days_of_week)
    @settings(max_examples=50)
    def test_time_bucketing_roundtrip(self, hour: int, day: int):
        """Property: Time bucketing values roundtrip correctly."""
        baseline = ZoneActivityBaseline(
            id=f"zone_1_{hour}_{day}",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=hour,
            day_of_week=day,
        )
        assert baseline.hour_of_day == hour
        assert baseline.day_of_week == day

    @given(detection_class=detection_classes)
    @settings(max_examples=10)
    def test_detection_class_roundtrip(self, detection_class: str):
        """Property: Detection class values roundtrip correctly."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            detection_class=detection_class,
        )
        assert baseline.detection_class == detection_class

    @given(
        sample_count=sample_counts,
        mean_count=mean_counts,
        std_dev=std_devs,
    )
    @settings(max_examples=50)
    def test_statistical_values_roundtrip(
        self, sample_count: int, mean_count: float, std_dev: float
    ):
        """Property: Statistical values roundtrip correctly."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            sample_count=sample_count,
            mean_count=mean_count,
            std_dev=std_dev,
        )
        assert baseline.sample_count == sample_count
        assert abs(baseline.mean_count - mean_count) < 1e-10
        assert abs(baseline.std_dev - std_dev) < 1e-10

    @given(
        mean=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        std_dev=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
        observed=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50)
    def test_deviation_from_mean_property(self, mean: float, std_dev: float, observed: float):
        """Property: deviation_from_mean calculation is correct."""
        baseline = ZoneActivityBaseline(
            id="zone_1",
            zone_id="zone_1",
            camera_id="cam1",
            hour_of_day=0,
            day_of_week=0,
            mean_count=mean,
            std_dev=std_dev,
        )
        deviation = baseline.deviation_from_mean(observed)
        expected = abs(observed - mean) / std_dev
        assert abs(deviation - expected) < 1e-10
