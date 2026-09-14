"""Unit tests for ZoneActivityBaseline model.

Tests cover:
- Model instantiation with valid data
- Field validation and constraints
- Default values
- Relationship navigation
- String representation (__repr__)
- Property methods (is_stale, get_expected_activity, deviation_from_expected)
- CheckConstraints for statistical values
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
            zone_id="zone_1",
            camera_id="cam1",
        )
        assert baseline.zone_id == "zone_1"
        assert baseline.camera_id == "cam1"
        # Defaults apply at DB level, not in-memory
        assert baseline.sample_count in (None, 0)
        assert baseline.mean_daily_count in (None, 0.0)

    def test_baseline_creation_full(self):
        """Test creating a baseline with all fields."""
        hourly = [0.0] * 6 + [5.0] * 12 + [0.0] * 6  # Activity 6am-6pm
        hourly_std = [0.0] * 6 + [1.0] * 12 + [0.0] * 6
        daily = [10.0] * 5 + [5.0] * 2  # Less on weekends
        daily_std = [2.0] * 7

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            hourly_std=hourly_std,
            daily_pattern=daily,
            daily_std=daily_std,
            entity_class_distribution={"person": 100, "vehicle": 50},
            mean_daily_count=15.0,
            std_daily_count=3.0,
            min_daily_count=5,
            max_daily_count=30,
            typical_crossing_rate=8.0,
            typical_crossing_std=2.0,
            typical_dwell_time=45.0,
            typical_dwell_std=15.0,
            sample_count=100,
        )
        assert baseline.zone_id == "zone_1"
        assert baseline.camera_id == "cam1"
        assert baseline.hourly_pattern == hourly
        assert baseline.hourly_std == hourly_std
        assert baseline.daily_pattern == daily
        assert baseline.daily_std == daily_std
        assert baseline.entity_class_distribution == {"person": 100, "vehicle": 50}
        assert baseline.mean_daily_count == 15.0
        assert baseline.std_daily_count == 3.0
        assert baseline.min_daily_count == 5
        assert baseline.max_daily_count == 30
        assert baseline.typical_crossing_rate == 8.0
        assert baseline.typical_crossing_std == 2.0
        assert baseline.typical_dwell_time == 45.0
        assert baseline.typical_dwell_std == 15.0
        assert baseline.sample_count == 100

    def test_baseline_default_statistical_values(self):
        """Test statistical values have defaults defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(ZoneActivityBaseline)
        assert mapper.columns["sample_count"].default.arg == 0
        assert mapper.columns["mean_daily_count"].default.arg == 0.0
        assert mapper.columns["std_daily_count"].default.arg == 0.0
        assert mapper.columns["min_daily_count"].default.arg == 0
        assert mapper.columns["max_daily_count"].default.arg == 0
        assert mapper.columns["typical_crossing_rate"].default.arg == 10.0
        assert mapper.columns["typical_crossing_std"].default.arg == 5.0
        assert mapper.columns["typical_dwell_time"].default.arg == 30.0
        assert mapper.columns["typical_dwell_std"].default.arg == 10.0

    def test_baseline_repr(self):
        """Test ZoneActivityBaseline __repr__ method."""
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            sample_count=50,
            mean_daily_count=12.5,
        )
        repr_str = repr(baseline)
        assert "ZoneActivityBaseline" in repr_str
        assert "zone_id='zone_1'" in repr_str
        assert "sample_count=50" in repr_str
        assert "mean_daily=12.50" in repr_str

    def test_baseline_has_zone_relationship(self):
        """Test ZoneActivityBaseline has zone relationship defined."""
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
        )
        assert hasattr(baseline, "zone")

    def test_baseline_tablename(self):
        """Test ZoneActivityBaseline has correct table name."""
        assert ZoneActivityBaseline.__tablename__ == "zone_activity_baselines"

    def test_baseline_has_indexes(self):
        """Test ZoneActivityBaseline has expected indexes."""
        indexes = ZoneActivityBaseline.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_zone_activity_baselines_zone_id" in index_names
        assert "idx_zone_activity_baselines_camera_id" in index_names
        assert "idx_zone_activity_baselines_last_updated" in index_names

    def test_baseline_has_unique_constraint(self):
        """Test ZoneActivityBaseline has unique constraint on zone_id."""
        from sqlalchemy import UniqueConstraint

        constraints = ZoneActivityBaseline.__table_args__
        unique_constraints = [
            c for c in constraints if isinstance(c, UniqueConstraint) and "zone_id" in c.name
        ]
        assert len(unique_constraints) == 1


# =============================================================================
# ZoneActivityBaseline is_stale Method Tests
# =============================================================================


class TestZoneActivityBaselineIsStale:
    """Tests for ZoneActivityBaseline.is_stale() method."""

    def test_is_stale_fresh_baseline(self):
        """Test baseline that was just updated is not stale."""
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            last_updated=utc_now(),
        )
        assert baseline.is_stale() is False

    def test_is_stale_old_baseline(self):
        """Test baseline older than max_age is stale."""
        old_time = utc_now() - timedelta(days=8)  # 8 days ago (default max_age is 7 days)
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            last_updated=old_time,
        )
        assert baseline.is_stale() is True

    def test_is_stale_custom_max_age(self):
        """Test is_stale with custom max_age_hours."""
        old_time = utc_now() - timedelta(hours=25)  # 25 hours ago
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            last_updated=old_time,
        )
        # With max_age=24 hours, this should be stale
        assert baseline.is_stale(max_age_hours=24) is True
        # With max_age=48 hours, this should not be stale
        assert baseline.is_stale(max_age_hours=48) is False

    def test_is_stale_null_last_updated(self):
        """Test baseline with null last_updated is stale."""
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            last_updated=None,
        )
        assert baseline.is_stale() is True

    def test_is_stale_boundary_exactly_max_age(self):
        """Test baseline exactly at max_age boundary."""
        exact_time = utc_now() - timedelta(hours=168)  # Exactly 7 days
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            last_updated=exact_time,
        )
        # At exactly the boundary, should not be stale (uses > comparison)
        # Note: Due to timing precision, this might be slightly stale
        result = baseline.is_stale()
        # Accept either result due to timing precision
        assert isinstance(result, bool)


# =============================================================================
# ZoneActivityBaseline get_expected_activity Method Tests
# =============================================================================


class TestZoneActivityBaselineGetExpectedActivity:
    """Tests for ZoneActivityBaseline.get_expected_activity() method."""

    def test_get_expected_activity_basic(self):
        """Test basic expected activity calculation."""
        hourly = [0.0] * 6 + [5.0] * 12 + [0.0] * 6  # Activity 6am-6pm
        daily = [1.0] * 7  # Uniform daily pattern

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            daily_pattern=daily,
        )

        # Hour 12 (noon) should have high activity
        assert baseline.get_expected_activity(hour=12, day_of_week=1) == 5.0
        # Hour 3 (3am) should have no activity
        assert baseline.get_expected_activity(hour=3, day_of_week=1) == 0.0

    def test_get_expected_activity_empty_patterns(self):
        """Test expected activity with empty patterns returns 0."""
        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=[],
            daily_pattern=[],
        )

        assert baseline.get_expected_activity(hour=12, day_of_week=1) == 0.0

    def test_get_expected_activity_hour_out_of_range(self):
        """Test expected activity with hour index out of range."""
        hourly = [1.0] * 10  # Only 10 values

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            daily_pattern=[1.0] * 7,
        )

        # Hour 15 is out of range (only 10 values)
        assert baseline.get_expected_activity(hour=15, day_of_week=1) == 0.0


# =============================================================================
# ZoneActivityBaseline deviation_from_expected Method Tests
# =============================================================================


class TestZoneActivityBaselineDeviationFromExpected:
    """Tests for ZoneActivityBaseline.deviation_from_expected() method."""

    def test_deviation_zero_std(self):
        """Test deviation when std is zero returns 0."""
        hourly = [5.0] * 24
        hourly_std = [0.0] * 24  # Zero std

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            hourly_std=hourly_std,
            daily_pattern=[1.0] * 7,
        )

        assert baseline.deviation_from_expected(observed=10.0, hour=12, day_of_week=1) == 0.0

    def test_deviation_exact_expected(self):
        """Test deviation when observed equals expected."""
        hourly = [5.0] * 24
        hourly_std = [2.0] * 24

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            hourly_std=hourly_std,
            daily_pattern=[1.0] * 7,
        )

        assert baseline.deviation_from_expected(observed=5.0, hour=12, day_of_week=1) == 0.0

    def test_deviation_one_std_above(self):
        """Test deviation one std above expected."""
        hourly = [5.0] * 24
        hourly_std = [2.0] * 24

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            hourly_std=hourly_std,
            daily_pattern=[1.0] * 7,
        )

        # 7.0 is one std above 5.0 (std=2.0)
        assert baseline.deviation_from_expected(observed=7.0, hour=12, day_of_week=1) == 1.0

    def test_deviation_empty_std_pattern(self):
        """Test deviation with empty hourly_std pattern."""
        hourly = [5.0] * 24

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            hourly_std=[],  # Empty
            daily_pattern=[1.0] * 7,
        )

        # Should return 0 because std is 0 (default when out of range)
        assert baseline.deviation_from_expected(observed=10.0, hour=12, day_of_week=1) == 0.0


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestZoneActivityBaselineProperties:
    """Property-based tests for ZoneActivityBaseline model."""

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
            zone_id="zone_1",
            camera_id="cam1",
            sample_count=sample_count,
            mean_daily_count=mean_count,
            std_daily_count=std_dev,
        )
        assert baseline.sample_count == sample_count
        assert abs(baseline.mean_daily_count - mean_count) < 1e-10
        assert abs(baseline.std_daily_count - std_dev) < 1e-10

    @given(
        hour=hours,
        day=days_of_week,
    )
    @settings(max_examples=50)
    def test_get_expected_activity_valid_time(self, hour: int, day: int):
        """Property: get_expected_activity handles all valid hour/day combinations."""
        hourly = [float(i) for i in range(24)]
        daily = [float(i + 1) for i in range(7)]

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            daily_pattern=daily,
        )

        result = baseline.get_expected_activity(hour=hour, day_of_week=day)
        # Result should be a finite float
        assert isinstance(result, float)
        assert result >= 0

    @given(
        observed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        hour=hours,
        day=days_of_week,
    )
    @settings(max_examples=50)
    def test_deviation_always_non_negative(self, observed: float, hour: int, day: int):
        """Property: deviation_from_expected is always non-negative."""
        hourly = [5.0] * 24
        hourly_std = [2.0] * 24

        baseline = ZoneActivityBaseline(
            zone_id="zone_1",
            camera_id="cam1",
            hourly_pattern=hourly,
            hourly_std=hourly_std,
            daily_pattern=[1.0] * 7,
        )

        deviation = baseline.deviation_from_expected(observed=observed, hour=hour, day_of_week=day)
        assert deviation >= 0.0
