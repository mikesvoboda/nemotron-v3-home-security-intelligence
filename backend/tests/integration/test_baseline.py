"""Unit tests for baseline activity modeling service.

Tests cover:
- BaselineService initialization and configuration
- Singleton pattern
- Time decay calculations (pure math)
- ActivityBaseline model repr/attributes
- ClassBaseline model repr/attributes

These tests do NOT require database access.
"""

import math
from datetime import UTC, datetime

import pytest

from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.services.baseline import (
    BaselineService,
    get_baseline_service,
    reset_baseline_service,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def baseline_service():
    """Create baseline service instance with default configuration."""
    return BaselineService()


@pytest.fixture
def baseline_service_custom():
    """Create baseline service instance with custom configuration."""
    return BaselineService(
        decay_factor=0.2,
        window_days=14,
        anomaly_threshold_std=3.0,
        min_samples=5,
    )


@pytest.fixture
def sample_activity_baseline():
    """Create a sample ActivityBaseline for testing."""
    baseline = ActivityBaseline(
        id=1,
        camera_id="camera_1",
        hour=10,
        day_of_week=2,  # Wednesday
        avg_count=5.0,
        sample_count=20,
        last_updated=datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC),
    )
    return baseline


@pytest.fixture
def sample_class_baseline():
    """Create a sample ClassBaseline for testing."""
    baseline = ClassBaseline(
        id=1,
        camera_id="camera_1",
        detection_class="person",
        hour=10,
        frequency=0.8,
        sample_count=25,
        last_updated=datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC),
    )
    return baseline


@pytest.fixture(autouse=True)
def reset_service_singleton():
    """Reset the baseline service singleton before and after each test."""
    reset_baseline_service()
    yield
    reset_baseline_service()


# ============================================================================
# Initialization Tests
# ============================================================================


class TestBaselineServiceInit:
    """Tests for BaselineService initialization."""

    def test_default_initialization(self):
        """Test BaselineService initializes with correct defaults."""
        service = BaselineService()

        assert service.decay_factor == 0.1
        assert service.window_days == 30
        assert service.anomaly_threshold_std == 2.0
        assert service.min_samples == 10

    def test_custom_initialization(self):
        """Test BaselineService with custom settings."""
        service = BaselineService(
            decay_factor=0.5,
            window_days=7,
            anomaly_threshold_std=1.5,
            min_samples=5,
        )

        assert service.decay_factor == 0.5
        assert service.window_days == 7
        assert service.anomaly_threshold_std == 1.5
        assert service.min_samples == 5

    def test_invalid_decay_factor_zero(self):
        """Test that decay_factor of 0 raises ValueError."""
        with pytest.raises(ValueError, match="decay_factor must be between"):
            BaselineService(decay_factor=0.0)

    def test_invalid_decay_factor_negative(self):
        """Test that negative decay_factor raises ValueError."""
        with pytest.raises(ValueError, match="decay_factor must be between"):
            BaselineService(decay_factor=-0.1)

    def test_invalid_decay_factor_greater_than_one(self):
        """Test that decay_factor > 1 raises ValueError."""
        with pytest.raises(ValueError, match="decay_factor must be between"):
            BaselineService(decay_factor=1.5)

    def test_valid_decay_factor_one(self):
        """Test that decay_factor of 1 is valid."""
        service = BaselineService(decay_factor=1.0)
        assert service.decay_factor == 1.0

    def test_invalid_window_days(self):
        """Test that window_days < 1 raises ValueError."""
        with pytest.raises(ValueError, match="window_days must be at least 1"):
            BaselineService(window_days=0)

    def test_invalid_anomaly_threshold(self):
        """Test that negative anomaly_threshold raises ValueError."""
        with pytest.raises(ValueError, match="anomaly_threshold_std must be non-negative"):
            BaselineService(anomaly_threshold_std=-1.0)

    def test_invalid_min_samples(self):
        """Test that min_samples < 1 raises ValueError."""
        with pytest.raises(ValueError, match="min_samples must be at least 1"):
            BaselineService(min_samples=0)


# ============================================================================
# Singleton Pattern Tests
# ============================================================================


class TestBaselineServiceSingleton:
    """Tests for the singleton pattern."""

    def test_get_baseline_service_returns_singleton(self):
        """Test that get_baseline_service returns the same instance."""
        service1 = get_baseline_service()
        service2 = get_baseline_service()

        assert service1 is service2

    def test_reset_baseline_service_clears_singleton(self):
        """Test that reset_baseline_service clears the singleton."""
        service1 = get_baseline_service()
        reset_baseline_service()
        service2 = get_baseline_service()

        assert service1 is not service2


# ============================================================================
# Time Decay Calculation Tests
# ============================================================================


class TestTimeDecayCalculation:
    """Tests for time-based decay calculations."""

    def test_decay_same_day(self, baseline_service):
        """Test decay when last update was today."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        last_updated = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

        decay = baseline_service._calculate_time_decay(last_updated, now)

        # 2 hours = 2/24 days elapsed
        expected = math.exp(-(2 / 24) * math.log(1 / 0.1))
        assert abs(decay - expected) < 0.001

    def test_decay_one_day_ago(self, baseline_service):
        """Test decay when last update was one day ago."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        last_updated = datetime(2025, 1, 14, 12, 0, 0, tzinfo=UTC)

        decay = baseline_service._calculate_time_decay(last_updated, now)

        # 1 day elapsed: decay_factor^1 = 0.1
        assert abs(decay - 0.1) < 0.001

    def test_decay_two_days_ago(self, baseline_service):
        """Test decay when last update was two days ago."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        last_updated = datetime(2025, 1, 13, 12, 0, 0, tzinfo=UTC)

        decay = baseline_service._calculate_time_decay(last_updated, now)

        # 2 days elapsed: decay_factor^2 = 0.1^2 = 0.01
        assert abs(decay - 0.01) < 0.001

    def test_decay_outside_window(self, baseline_service):
        """Test decay when last update is outside the window."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        last_updated = datetime(2024, 12, 1, 12, 0, 0, tzinfo=UTC)  # 45 days ago

        decay = baseline_service._calculate_time_decay(last_updated, now)

        # Outside 30-day window, should return 0
        assert decay == 0.0

    def test_decay_custom_window(self, baseline_service_custom):
        """Test decay with custom window days."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        last_updated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)  # 14 days ago

        decay = baseline_service_custom._calculate_time_decay(last_updated, now)

        # Exactly at window boundary, should be non-zero
        assert decay > 0

    def test_decay_past_custom_window(self, baseline_service_custom):
        """Test decay past custom window days returns 0."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        last_updated = datetime(2024, 12, 31, 12, 0, 0, tzinfo=UTC)  # 15 days ago

        decay = baseline_service_custom._calculate_time_decay(last_updated, now)

        # Outside 14-day window, should return 0
        assert decay == 0.0

    def test_decay_handles_naive_datetimes(self, baseline_service):
        """Test that decay calculation handles naive datetimes."""
        now = datetime(2025, 1, 15, 12, 0, 0)  # naive
        last_updated = datetime(2025, 1, 14, 12, 0, 0)  # naive

        decay = baseline_service._calculate_time_decay(last_updated, now)

        # Should work without raising
        assert abs(decay - 0.1) < 0.001


# ============================================================================
# Model Tests
# ============================================================================


class TestActivityBaselineModel:
    """Tests for the ActivityBaseline model."""

    def test_activity_baseline_repr(self, sample_activity_baseline):
        """Test ActivityBaseline string representation."""
        repr_str = repr(sample_activity_baseline)

        assert "ActivityBaseline" in repr_str
        assert "camera_1" in repr_str
        assert "hour=10" in repr_str
        assert "day_of_week=2" in repr_str

    def test_activity_baseline_attributes(self, sample_activity_baseline):
        """Test ActivityBaseline has correct attributes."""
        assert sample_activity_baseline.camera_id == "camera_1"
        assert sample_activity_baseline.hour == 10
        assert sample_activity_baseline.day_of_week == 2
        assert sample_activity_baseline.avg_count == 5.0
        assert sample_activity_baseline.sample_count == 20


class TestClassBaselineModel:
    """Tests for the ClassBaseline model."""

    def test_class_baseline_repr(self, sample_class_baseline):
        """Test ClassBaseline string representation."""
        repr_str = repr(sample_class_baseline)

        assert "ClassBaseline" in repr_str
        assert "camera_1" in repr_str
        assert "person" in repr_str
        assert "hour=10" in repr_str

    def test_class_baseline_attributes(self, sample_class_baseline):
        """Test ClassBaseline has correct attributes."""
        assert sample_class_baseline.camera_id == "camera_1"
        assert sample_class_baseline.detection_class == "person"
        assert sample_class_baseline.hour == 10
        assert sample_class_baseline.frequency == 0.8
        assert sample_class_baseline.sample_count == 25
