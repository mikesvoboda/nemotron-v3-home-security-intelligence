"""Unit tests for ZoneAnomaly model.

Tests cover:
- Model instantiation with valid data
- Field validation and constraints
- Default values
- Relationship navigation
- String representation (__repr__)
- Property methods (acknowledge)
- CheckConstraints for enum values
- Acknowledgment workflow
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.core.time_utils import utc_now
from backend.models.zone_anomaly import AnomalySeverity, AnomalyType, ZoneAnomaly

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid anomaly types
anomaly_types = st.sampled_from([e.value for e in AnomalyType])

# Strategy for valid severity levels
severity_levels = st.sampled_from([e.value for e in AnomalySeverity])

# Strategy for valid deviation values
deviations = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# Strategy for valid float values
float_values = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)


# =============================================================================
# ZoneAnomaly Model Tests
# =============================================================================


class TestZoneAnomalyModel:
    """Tests for ZoneAnomaly model."""

    def test_anomaly_creation_minimal(self):
        """Test creating an anomaly with required fields."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_frequency",
            title="Unusual activity detected",
        )
        assert anomaly.id == "anomaly_1"
        assert anomaly.zone_id == "zone_1"
        assert anomaly.camera_id == "cam1"
        assert anomaly.anomaly_type == "unusual_frequency"
        # Defaults apply at DB level, not in-memory
        assert anomaly.severity in (None, "info")
        assert anomaly.title == "Unusual activity detected"
        assert anomaly.description is None
        assert anomaly.acknowledged in (None, False)

    def test_anomaly_creation_full(self):
        """Test creating an anomaly with all fields."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_frequency",
            severity="critical",
            title="Critical: Unusual activity",
            description="Detected 50 people in normally quiet zone",
            expected_value=5.0,
            actual_value=50.0,
            deviation=9.0,
            detection_id=123,
            thumbnail_url="/thumbnails/anomaly_1.jpg",
            acknowledged=False,
        )
        assert anomaly.id == "anomaly_1"
        assert anomaly.zone_id == "zone_1"
        assert anomaly.camera_id == "cam1"
        assert anomaly.anomaly_type == "unusual_frequency"
        assert anomaly.severity == "critical"
        assert anomaly.title == "Critical: Unusual activity"
        assert anomaly.description == "Detected 50 people in normally quiet zone"
        assert anomaly.expected_value == 5.0
        assert anomaly.actual_value == 50.0
        assert anomaly.deviation == 9.0
        assert anomaly.detection_id == 123
        assert anomaly.thumbnail_url == "/thumbnails/anomaly_1.jpg"
        assert anomaly.acknowledged is False

    def test_anomaly_default_severity(self):
        """Test severity has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(ZoneAnomaly)
        severity_col = mapper.columns["severity"]
        assert severity_col.default is not None
        assert severity_col.default.arg == "info"

    def test_anomaly_default_acknowledged(self):
        """Test acknowledged has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(ZoneAnomaly)
        acknowledged_col = mapper.columns["acknowledged"]
        assert acknowledged_col.default is not None
        assert acknowledged_col.default.arg is False

    def test_anomaly_repr(self):
        """Test ZoneAnomaly __repr__ method."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_frequency",
            severity="warning",
            title="Unusual activity",
            timestamp=utc_now(),
        )
        repr_str = repr(anomaly)
        assert "ZoneAnomaly" in repr_str
        assert "id='anomaly_1'" in repr_str
        assert "zone_id='zone_1'" in repr_str
        assert "anomaly_type='unusual_frequency'" in repr_str
        assert "severity='warning'" in repr_str

    def test_anomaly_has_zone_relationship(self):
        """Test ZoneAnomaly has zone relationship defined."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_time",
            title="Activity",
        )
        assert hasattr(anomaly, "zone")

    def test_anomaly_has_detection_relationship(self):
        """Test ZoneAnomaly has detection relationship defined."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_time",
            title="Activity",
        )
        assert hasattr(anomaly, "detection")

    def test_anomaly_tablename(self):
        """Test ZoneAnomaly has correct table name."""
        assert ZoneAnomaly.__tablename__ == "zone_anomalies"

    def test_anomaly_has_indexes(self):
        """Test ZoneAnomaly has expected indexes."""
        indexes = ZoneAnomaly.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_zone_anomalies_zone_id" in index_names
        assert "idx_zone_anomalies_camera_id" in index_names
        assert "idx_zone_anomalies_timestamp" in index_names
        assert "idx_zone_anomalies_severity" in index_names
        assert "idx_zone_anomalies_acknowledged" in index_names
        assert "idx_zone_anomalies_zone_timestamp" in index_names
        assert "idx_zone_anomalies_unacknowledged" in index_names


# =============================================================================
# ZoneAnomaly Enum Tests
# =============================================================================


class TestZoneAnomalyEnums:
    """Tests for ZoneAnomaly enum classes."""

    def test_anomaly_type_enum_values(self):
        """Test AnomalyType enum has expected values."""
        assert AnomalyType.UNUSUAL_TIME.value == "unusual_time"
        assert AnomalyType.UNUSUAL_FREQUENCY.value == "unusual_frequency"
        assert AnomalyType.UNUSUAL_DWELL.value == "unusual_dwell"
        assert AnomalyType.UNUSUAL_ENTITY.value == "unusual_entity"

    def test_anomaly_severity_enum_values(self):
        """Test AnomalySeverity enum has expected values."""
        assert AnomalySeverity.INFO.value == "info"
        assert AnomalySeverity.WARNING.value == "warning"
        assert AnomalySeverity.CRITICAL.value == "critical"

    def test_anomaly_type_is_string_enum(self):
        """Test AnomalyType inherits from str."""
        assert isinstance(AnomalyType.UNUSUAL_TIME, str)

    def test_anomaly_severity_is_string_enum(self):
        """Test AnomalySeverity inherits from str."""
        assert isinstance(AnomalySeverity.INFO, str)


# =============================================================================
# ZoneAnomaly Type-Specific Tests
# =============================================================================


class TestZoneAnomalyTypes:
    """Tests for different anomaly types."""

    def test_unusual_time_anomaly(self):
        """Test creating an unusual_time anomaly."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            title="Activity at unusual time",
            severity=AnomalySeverity.WARNING,
        )
        assert anomaly.anomaly_type == "unusual_time"
        assert anomaly.severity == "warning"

    def test_unusual_frequency_anomaly(self):
        """Test creating an unusual_frequency anomaly."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type=AnomalyType.UNUSUAL_FREQUENCY,
            title="Unusual activity frequency",
            expected_value=5.0,
            actual_value=25.0,
            deviation=4.0,
        )
        assert anomaly.anomaly_type == "unusual_frequency"
        assert anomaly.expected_value == 5.0
        assert anomaly.actual_value == 25.0
        assert anomaly.deviation == 4.0

    def test_unusual_dwell_anomaly(self):
        """Test creating an unusual_dwell anomaly."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type=AnomalyType.UNUSUAL_DWELL,
            title="Person loitering",
            severity=AnomalySeverity.CRITICAL,
            detection_id=123,
        )
        assert anomaly.anomaly_type == "unusual_dwell"
        assert anomaly.severity == "critical"
        assert anomaly.detection_id == 123

    def test_unusual_entity_anomaly(self):
        """Test creating an unusual_entity anomaly."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type=AnomalyType.UNUSUAL_ENTITY,
            title="Unknown person detected",
            severity=AnomalySeverity.WARNING,
        )
        assert anomaly.anomaly_type == "unusual_entity"
        assert anomaly.severity == "warning"


# =============================================================================
# ZoneAnomaly acknowledge Method Tests
# =============================================================================


class TestZoneAnomalyAcknowledge:
    """Tests for ZoneAnomaly.acknowledge() method."""

    def test_acknowledge_without_user(self):
        """Test acknowledging an anomaly without specifying user."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_time",
            title="Activity",
            acknowledged=False,  # Explicitly set for test
        )
        assert anomaly.acknowledged is False
        assert anomaly.acknowledged_at is None
        assert anomaly.acknowledged_by is None

        anomaly.acknowledge()

        assert anomaly.acknowledged is True
        assert anomaly.acknowledged_at is not None
        assert anomaly.acknowledged_by is None

    def test_acknowledge_with_user(self):
        """Test acknowledging an anomaly with user."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_time",
            title="Activity",
            acknowledged=False,  # Explicitly set for test
        )
        assert anomaly.acknowledged is False

        anomaly.acknowledge(acknowledged_by="admin")

        assert anomaly.acknowledged is True
        assert anomaly.acknowledged_at is not None
        assert anomaly.acknowledged_by == "admin"

    def test_acknowledge_sets_timestamp(self):
        """Test acknowledge sets timestamp to current time."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_time",
            title="Activity",
        )
        before_acknowledge = utc_now()
        anomaly.acknowledge()
        after_acknowledge = utc_now()

        assert before_acknowledge <= anomaly.acknowledged_at <= after_acknowledge

    def test_acknowledge_idempotent(self):
        """Test calling acknowledge multiple times."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_time",
            title="Activity",
        )
        anomaly.acknowledge(acknowledged_by="user1")
        first_timestamp = anomaly.acknowledged_at
        first_user = anomaly.acknowledged_by

        # Acknowledge again with different user
        anomaly.acknowledge(acknowledged_by="user2")

        # Should update both timestamp and user
        assert anomaly.acknowledged is True
        assert anomaly.acknowledged_at >= first_timestamp
        assert anomaly.acknowledged_by == "user2"


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestZoneAnomalyProperties:
    """Property-based tests for ZoneAnomaly model."""

    @given(anomaly_type=anomaly_types, severity=severity_levels)
    @settings(max_examples=20)
    def test_anomaly_type_severity_roundtrip(self, anomaly_type: str, severity: str):
        """Property: Anomaly type and severity values roundtrip correctly."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type=anomaly_type,
            severity=severity,
            title="Test anomaly",
        )
        assert anomaly.anomaly_type == anomaly_type
        assert anomaly.severity == severity

    @given(
        expected=float_values,
        actual=float_values,
        deviation=deviations,
    )
    @settings(max_examples=50)
    def test_quantitative_values_roundtrip(self, expected: float, actual: float, deviation: float):
        """Property: Quantitative values roundtrip correctly."""
        anomaly = ZoneAnomaly(
            id="anomaly_1",
            zone_id="zone_1",
            camera_id="cam1",
            anomaly_type="unusual_frequency",
            title="Activity",
            expected_value=expected,
            actual_value=actual,
            deviation=deviation,
        )
        assert abs(anomaly.expected_value - expected) < 1e-10
        assert abs(anomaly.actual_value - actual) < 1e-10
        assert abs(anomaly.deviation - deviation) < 1e-10
