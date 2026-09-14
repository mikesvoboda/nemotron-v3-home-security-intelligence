"""Unit tests for Alert and AlertRule models.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- AlertSeverity and AlertStatus enums
- AlertRule conditions and configuration
- Property-based tests for field values
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.alert import Alert, AlertRule, AlertSeverity, AlertStatus
from backend.tests.factories import AlertFactory, AlertRuleFactory

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for alert severities
alert_severities = st.sampled_from(list(AlertSeverity))

# Strategy for alert statuses
alert_statuses = st.sampled_from(list(AlertStatus))

# Strategy for risk thresholds (0-100)
risk_thresholds = st.integers(min_value=0, max_value=100)

# Strategy for cooldown seconds (reasonable range)
cooldown_seconds = st.integers(min_value=0, max_value=86400)

# Strategy for confidence values (0.0-1.0)
confidence_values = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for dedup key templates
dedup_templates = st.sampled_from(
    [
        "{camera_id}:{rule_id}",
        "{camera_id}:{object_type}:{rule_id}",
        "{camera_id}",
        "{rule_id}",
    ]
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_alert():
    """Create a sample alert for testing using factory."""
    return AlertFactory(
        id="alert-001",
        event_id=1,
        rule_id="rule-001",
        high_severity=True,  # Use factory trait
        dedup_key="front_door:rule-001",
        channels=["email", "push"],
        alert_metadata={"triggered_by": "person_detection"},
    )


@pytest.fixture
def minimal_alert():
    """Create an alert with minimal required fields."""
    # Use direct model instantiation for minimal test
    # to verify model's actual defaults (not factory defaults)
    return Alert(
        event_id=1,
        dedup_key="test_key",
    )


@pytest.fixture
def delivered_alert():
    """Create a delivered alert using factory."""
    return AlertFactory(
        id="alert-002",
        event_id=2,
        delivered=True,  # Use factory trait
        dedup_key="back_yard:rule-002",
    )


@pytest.fixture
def sample_alert_rule():
    """Create a sample alert rule for testing."""
    # Use direct model instantiation to match original test expectations
    return AlertRule(
        id="rule-001",
        name="High Risk Alert",
        description="Alert on high risk events",
        enabled=True,
        severity=AlertSeverity.HIGH,
        risk_threshold=70,
        object_types=["person", "vehicle"],
        camera_ids=["front_door", "back_yard"],
        min_confidence=0.8,
        cooldown_seconds=300,
    )


@pytest.fixture
def minimal_alert_rule():
    """Create an alert rule with minimal required fields."""
    # Use direct model instantiation to verify model's actual defaults
    return AlertRule(
        name="Test Rule",
    )


@pytest.fixture
def disabled_rule():
    """Create a disabled alert rule using factory."""
    return AlertRuleFactory(
        id="rule-disabled",
        name="Disabled Rule",
        disabled=True,  # Use factory trait
    )


# =============================================================================
# AlertSeverity Enum Tests
# =============================================================================


class TestAlertSeverityEnum:
    """Tests for AlertSeverity enum."""

    def test_alert_severity_low(self):
        """Test LOW alert severity."""
        assert AlertSeverity.LOW.value == "low"

    def test_alert_severity_medium(self):
        """Test MEDIUM alert severity."""
        assert AlertSeverity.MEDIUM.value == "medium"

    def test_alert_severity_high(self):
        """Test HIGH alert severity."""
        assert AlertSeverity.HIGH.value == "high"

    def test_alert_severity_critical(self):
        """Test CRITICAL alert severity."""
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_alert_severity_is_string_enum(self):
        """Test AlertSeverity is a string enum."""
        for severity in AlertSeverity:
            assert isinstance(severity, str)
            assert isinstance(severity.value, str)

    def test_alert_severity_count(self):
        """Test AlertSeverity has expected number of values."""
        assert len(AlertSeverity) == 4


# =============================================================================
# AlertStatus Enum Tests
# =============================================================================


class TestAlertStatusEnum:
    """Tests for AlertStatus enum."""

    def test_alert_status_pending(self):
        """Test PENDING alert status."""
        assert AlertStatus.PENDING.value == "pending"

    def test_alert_status_delivered(self):
        """Test DELIVERED alert status."""
        assert AlertStatus.DELIVERED.value == "delivered"

    def test_alert_status_acknowledged(self):
        """Test ACKNOWLEDGED alert status."""
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"

    def test_alert_status_dismissed(self):
        """Test DISMISSED alert status."""
        assert AlertStatus.DISMISSED.value == "dismissed"

    def test_alert_status_is_string_enum(self):
        """Test AlertStatus is a string enum."""
        for status in AlertStatus:
            assert isinstance(status, str)
            assert isinstance(status.value, str)

    def test_alert_status_count(self):
        """Test AlertStatus has expected number of values."""
        assert len(AlertStatus) == 4


# =============================================================================
# Alert Model Initialization Tests
# =============================================================================


class TestAlertModelInitialization:
    """Tests for Alert model initialization."""

    def test_alert_creation_minimal(self):
        """Test creating an alert with minimal required fields."""
        alert = Alert(
            event_id=1,
            dedup_key="test_key",
        )

        assert alert.event_id == 1
        assert alert.dedup_key == "test_key"

    def test_alert_with_all_fields(self, sample_alert):
        """Test alert with all fields populated."""
        assert sample_alert.id == "alert-001"
        assert sample_alert.event_id == 1
        assert sample_alert.rule_id == "rule-001"
        assert sample_alert.severity == AlertSeverity.HIGH
        assert sample_alert.status == AlertStatus.PENDING
        assert sample_alert.dedup_key == "front_door:rule-001"
        assert sample_alert.channels == ["email", "push"]
        assert sample_alert.alert_metadata == {"triggered_by": "person_detection"}

    def test_alert_default_severity_column_definition(self):
        """Test alert default severity column has MEDIUM.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Alert)
        severity_col = mapper.columns["severity"]
        assert severity_col.default is not None
        assert severity_col.default.arg == AlertSeverity.MEDIUM

    def test_alert_default_status_column_definition(self):
        """Test alert default status column has PENDING.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Alert)
        status_col = mapper.columns["status"]
        assert status_col.default is not None
        assert status_col.default.arg == AlertStatus.PENDING

    def test_alert_optional_fields_default_to_none(self, minimal_alert):
        """Test optional fields default to None."""
        assert minimal_alert.rule_id is None
        assert minimal_alert.delivered_at is None
        assert minimal_alert.channels is None
        assert minimal_alert.alert_metadata is None


# =============================================================================
# Alert Field Tests
# =============================================================================


class TestAlertSeverityField:
    """Tests for Alert severity field."""

    def test_alert_severity_low(self):
        """Test alert with LOW severity."""
        alert = Alert(event_id=1, dedup_key="key", severity=AlertSeverity.LOW)
        assert alert.severity == AlertSeverity.LOW

    def test_alert_severity_critical(self):
        """Test alert with CRITICAL severity."""
        alert = Alert(event_id=1, dedup_key="key", severity=AlertSeverity.CRITICAL)
        assert alert.severity == AlertSeverity.CRITICAL


class TestAlertStatusField:
    """Tests for Alert status field."""

    def test_alert_status_pending_explicit(self):
        """Test alert with explicit PENDING status."""
        alert = Alert(event_id=1, dedup_key="key", status=AlertStatus.PENDING)
        assert alert.status == AlertStatus.PENDING

    def test_alert_status_delivered(self, delivered_alert):
        """Test alert with DELIVERED status."""
        assert delivered_alert.status == AlertStatus.DELIVERED

    def test_alert_status_acknowledged(self):
        """Test alert with ACKNOWLEDGED status."""
        alert = Alert(event_id=1, dedup_key="key", status=AlertStatus.ACKNOWLEDGED)
        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_alert_status_dismissed(self):
        """Test alert with DISMISSED status."""
        alert = Alert(event_id=1, dedup_key="key", status=AlertStatus.DISMISSED)
        assert alert.status == AlertStatus.DISMISSED


class TestAlertChannels:
    """Tests for Alert channels field."""

    def test_alert_single_channel(self):
        """Test alert with single channel."""
        alert = Alert(event_id=1, dedup_key="key", channels=["email"])
        assert alert.channels == ["email"]

    def test_alert_multiple_channels(self, sample_alert):
        """Test alert with multiple channels."""
        assert sample_alert.channels == ["email", "push"]

    def test_alert_empty_channels(self):
        """Test alert with empty channels list."""
        alert = Alert(event_id=1, dedup_key="key", channels=[])
        assert alert.channels == []


class TestAlertMetadata:
    """Tests for Alert metadata field."""

    def test_alert_metadata_dict(self, sample_alert):
        """Test alert with metadata dict."""
        assert sample_alert.alert_metadata == {"triggered_by": "person_detection"}

    def test_alert_metadata_complex(self):
        """Test alert with complex metadata."""
        metadata = {
            "triggered_by": "person_detection",
            "confidence": 0.95,
            "objects": ["person", "vehicle"],
            "nested": {"key": "value"},
        }
        alert = Alert(event_id=1, dedup_key="key", alert_metadata=metadata)
        assert alert.alert_metadata == metadata


class TestAlertDeliveredAt:
    """Tests for Alert delivered_at field."""

    def test_alert_delivered_at_none(self, minimal_alert):
        """Test alert without delivered_at."""
        assert minimal_alert.delivered_at is None

    def test_alert_delivered_at_set(self, delivered_alert):
        """Test alert with delivered_at timestamp."""
        assert delivered_alert.delivered_at is not None


# =============================================================================
# Alert Repr Tests
# =============================================================================


class TestAlertRepr:
    """Tests for Alert string representation."""

    def test_alert_repr_contains_class_name(self, sample_alert):
        """Test repr contains class name."""
        repr_str = repr(sample_alert)
        assert "Alert" in repr_str

    def test_alert_repr_contains_id(self, sample_alert):
        """Test repr contains alert id."""
        repr_str = repr(sample_alert)
        assert "alert-001" in repr_str

    def test_alert_repr_contains_event_id(self, sample_alert):
        """Test repr contains event_id."""
        repr_str = repr(sample_alert)
        assert "event_id=1" in repr_str

    def test_alert_repr_contains_severity(self, sample_alert):
        """Test repr contains severity."""
        repr_str = repr(sample_alert)
        assert "high" in repr_str

    def test_alert_repr_contains_status(self, sample_alert):
        """Test repr contains status."""
        repr_str = repr(sample_alert)
        assert "pending" in repr_str

    def test_alert_repr_format(self, sample_alert):
        """Test repr has expected format."""
        repr_str = repr(sample_alert)
        assert repr_str.startswith("<Alert(")
        assert repr_str.endswith(")>")


# =============================================================================
# AlertRule Model Initialization Tests
# =============================================================================


class TestAlertRuleModelInitialization:
    """Tests for AlertRule model initialization."""

    def test_alert_rule_creation_minimal(self):
        """Test creating an alert rule with minimal required fields."""
        rule = AlertRule(name="Test Rule")

        assert rule.name == "Test Rule"

    def test_alert_rule_with_all_fields(self, sample_alert_rule):
        """Test alert rule with all fields populated."""
        assert sample_alert_rule.id == "rule-001"
        assert sample_alert_rule.name == "High Risk Alert"
        assert sample_alert_rule.description == "Alert on high risk events"
        assert sample_alert_rule.enabled is True
        assert sample_alert_rule.severity == AlertSeverity.HIGH
        assert sample_alert_rule.risk_threshold == 70
        assert sample_alert_rule.object_types == ["person", "vehicle"]
        assert sample_alert_rule.camera_ids == ["front_door", "back_yard"]
        assert sample_alert_rule.min_confidence == 0.8
        assert sample_alert_rule.cooldown_seconds == 300

    def test_alert_rule_default_enabled_column_definition(self):
        """Test alert rule default enabled column has True.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(AlertRule)
        enabled_col = mapper.columns["enabled"]
        assert enabled_col.default is not None
        assert enabled_col.default.arg is True

    def test_alert_rule_default_severity_column_definition(self):
        """Test alert rule default severity column has MEDIUM.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(AlertRule)
        severity_col = mapper.columns["severity"]
        assert severity_col.default is not None
        assert severity_col.default.arg == AlertSeverity.MEDIUM

    def test_alert_rule_default_cooldown_column_definition(self):
        """Test alert rule default cooldown column has 300.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(AlertRule)
        cooldown_col = mapper.columns["cooldown_seconds"]
        assert cooldown_col.default is not None
        assert cooldown_col.default.arg == 300

    def test_alert_rule_default_dedup_template_column_definition(self):
        """Test alert rule default dedup key template column.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(AlertRule)
        template_col = mapper.columns["dedup_key_template"]
        assert template_col.default is not None
        assert template_col.default.arg == "{camera_id}:{rule_id}"

    def test_alert_rule_optional_fields_default_to_none(self, minimal_alert_rule):
        """Test optional fields default to None."""
        assert minimal_alert_rule.description is None
        assert minimal_alert_rule.risk_threshold is None
        assert minimal_alert_rule.object_types is None
        assert minimal_alert_rule.camera_ids is None
        assert minimal_alert_rule.zone_ids is None
        assert minimal_alert_rule.min_confidence is None
        assert minimal_alert_rule.schedule is None
        assert minimal_alert_rule.conditions is None
        assert minimal_alert_rule.channels is None


# =============================================================================
# AlertRule Field Tests
# =============================================================================


class TestAlertRuleConditions:
    """Tests for AlertRule condition fields."""

    def test_alert_rule_risk_threshold(self, sample_alert_rule):
        """Test alert rule with risk threshold."""
        assert sample_alert_rule.risk_threshold == 70

    def test_alert_rule_object_types(self, sample_alert_rule):
        """Test alert rule with object types."""
        assert sample_alert_rule.object_types == ["person", "vehicle"]

    def test_alert_rule_camera_ids(self, sample_alert_rule):
        """Test alert rule with camera IDs."""
        assert sample_alert_rule.camera_ids == ["front_door", "back_yard"]

    def test_alert_rule_zone_ids(self):
        """Test alert rule with zone IDs."""
        rule = AlertRule(name="Test", zone_ids=["zone_1", "zone_2"])
        assert rule.zone_ids == ["zone_1", "zone_2"]

    def test_alert_rule_min_confidence(self, sample_alert_rule):
        """Test alert rule with min confidence."""
        assert sample_alert_rule.min_confidence == 0.8

    def test_alert_rule_schedule(self):
        """Test alert rule with schedule."""
        schedule = {
            "days": [0, 1, 2, 3, 4],
            "start_time": "22:00",
            "end_time": "06:00",
            "timezone": "America/New_York",
        }
        rule = AlertRule(name="Test", schedule=schedule)
        assert rule.schedule == schedule


class TestAlertRuleCooldown:
    """Tests for AlertRule cooldown fields."""

    def test_alert_rule_explicit_cooldown(self, sample_alert_rule):
        """Test explicit cooldown is 300 seconds (5 minutes)."""
        assert sample_alert_rule.cooldown_seconds == 300

    def test_alert_rule_custom_cooldown(self):
        """Test custom cooldown."""
        rule = AlertRule(name="Test", cooldown_seconds=600)
        assert rule.cooldown_seconds == 600

    def test_alert_rule_zero_cooldown(self):
        """Test zero cooldown (no deduplication)."""
        rule = AlertRule(name="Test", cooldown_seconds=0)
        assert rule.cooldown_seconds == 0


class TestAlertRuleDedupTemplate:
    """Tests for AlertRule dedup key template."""

    def test_alert_rule_explicit_template(self):
        """Test explicit dedup key template."""
        rule = AlertRule(name="Test", dedup_key_template="{camera_id}:{rule_id}")
        assert rule.dedup_key_template == "{camera_id}:{rule_id}"

    def test_alert_rule_custom_template(self):
        """Test custom dedup key template."""
        rule = AlertRule(
            name="Test",
            dedup_key_template="{camera_id}:{object_type}:{rule_id}",
        )
        assert rule.dedup_key_template == "{camera_id}:{object_type}:{rule_id}"


class TestAlertRuleChannels:
    """Tests for AlertRule channels field."""

    def test_alert_rule_channels(self):
        """Test alert rule with channels."""
        rule = AlertRule(name="Test", channels=["email", "sms", "push"])
        assert rule.channels == ["email", "sms", "push"]

    def test_alert_rule_no_channels(self, minimal_alert_rule):
        """Test alert rule without channels."""
        assert minimal_alert_rule.channels is None


# =============================================================================
# AlertRule Repr Tests
# =============================================================================


class TestAlertRuleRepr:
    """Tests for AlertRule string representation."""

    def test_alert_rule_repr_contains_class_name(self, sample_alert_rule):
        """Test repr contains class name."""
        repr_str = repr(sample_alert_rule)
        assert "AlertRule" in repr_str

    def test_alert_rule_repr_contains_id(self, sample_alert_rule):
        """Test repr contains rule id."""
        repr_str = repr(sample_alert_rule)
        assert "rule-001" in repr_str

    def test_alert_rule_repr_contains_name(self, sample_alert_rule):
        """Test repr contains rule name."""
        repr_str = repr(sample_alert_rule)
        assert "High Risk Alert" in repr_str

    def test_alert_rule_repr_contains_enabled(self, sample_alert_rule):
        """Test repr contains enabled status."""
        repr_str = repr(sample_alert_rule)
        assert "enabled=True" in repr_str

    def test_alert_rule_repr_contains_severity(self, sample_alert_rule):
        """Test repr contains severity."""
        repr_str = repr(sample_alert_rule)
        assert "high" in repr_str

    def test_alert_rule_repr_format(self, sample_alert_rule):
        """Test repr has expected format."""
        repr_str = repr(sample_alert_rule)
        assert repr_str.startswith("<AlertRule(")
        assert repr_str.endswith(")>")


# =============================================================================
# Relationship Tests
# =============================================================================


class TestAlertRelationships:
    """Tests for Alert relationship definitions."""

    def test_alert_has_event_relationship(self, sample_alert):
        """Test alert has event relationship defined."""
        assert hasattr(sample_alert, "event")

    def test_alert_has_rule_relationship(self, sample_alert):
        """Test alert has rule relationship defined."""
        assert hasattr(sample_alert, "rule")


class TestAlertRuleRelationships:
    """Tests for AlertRule relationship definitions."""

    def test_alert_rule_has_alerts_relationship(self, sample_alert_rule):
        """Test alert rule has alerts relationship defined."""
        assert hasattr(sample_alert_rule, "alerts")


# =============================================================================
# Table Args Tests
# =============================================================================


class TestTableArgs:
    """Tests for table arguments (indexes)."""

    def test_alert_has_table_args(self):
        """Test Alert model has __table_args__."""
        assert hasattr(Alert, "__table_args__")

    def test_alert_tablename(self):
        """Test Alert has correct table name."""
        assert Alert.__tablename__ == "alerts"

    def test_alert_rule_has_table_args(self):
        """Test AlertRule model has __table_args__."""
        assert hasattr(AlertRule, "__table_args__")

    def test_alert_rule_tablename(self):
        """Test AlertRule has correct table name."""
        assert AlertRule.__tablename__ == "alert_rules"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestAlertProperties:
    """Property-based tests for Alert model."""

    @given(severity=alert_severities)
    @settings(max_examples=10)
    def test_alert_severity_roundtrip(self, severity: AlertSeverity):
        """Property: Severity values roundtrip correctly."""
        alert = Alert(event_id=1, dedup_key="key", severity=severity)
        assert alert.severity == severity

    @given(status=alert_statuses)
    @settings(max_examples=10)
    def test_alert_status_roundtrip(self, status: AlertStatus):
        """Property: Status values roundtrip correctly."""
        alert = Alert(event_id=1, dedup_key="key", status=status)
        assert alert.status == status

    @given(event_id=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=20)
    def test_alert_event_id_roundtrip(self, event_id: int):
        """Property: Event ID values roundtrip correctly."""
        alert = Alert(event_id=event_id, dedup_key="key")
        assert alert.event_id == event_id

    @given(dedup_key=st.text(min_size=1, max_size=255))
    @settings(max_examples=20)
    def test_alert_dedup_key_roundtrip(self, dedup_key: str):
        """Property: Dedup key values roundtrip correctly."""
        alert = Alert(event_id=1, dedup_key=dedup_key)
        assert alert.dedup_key == dedup_key


class TestAlertRuleProperties:
    """Property-based tests for AlertRule model."""

    @given(severity=alert_severities)
    @settings(max_examples=10)
    def test_rule_severity_roundtrip(self, severity: AlertSeverity):
        """Property: Severity values roundtrip correctly."""
        rule = AlertRule(name="Test", severity=severity)
        assert rule.severity == severity

    @given(threshold=risk_thresholds)
    @settings(max_examples=20)
    def test_rule_threshold_roundtrip(self, threshold: int):
        """Property: Risk threshold values roundtrip correctly."""
        rule = AlertRule(name="Test", risk_threshold=threshold)
        assert rule.risk_threshold == threshold

    @given(cooldown=cooldown_seconds)
    @settings(max_examples=20)
    def test_rule_cooldown_roundtrip(self, cooldown: int):
        """Property: Cooldown values roundtrip correctly."""
        rule = AlertRule(name="Test", cooldown_seconds=cooldown)
        assert rule.cooldown_seconds == cooldown

    @given(confidence=confidence_values)
    @settings(max_examples=20)
    def test_rule_confidence_roundtrip(self, confidence: float):
        """Property: Min confidence values roundtrip correctly."""
        rule = AlertRule(name="Test", min_confidence=confidence)
        assert abs(rule.min_confidence - confidence) < 1e-10

    @given(enabled=st.booleans())
    @settings(max_examples=10)
    def test_rule_enabled_roundtrip(self, enabled: bool):
        """Property: Enabled values roundtrip correctly."""
        rule = AlertRule(name="Test", enabled=enabled)
        assert rule.enabled == enabled

    @given(template=dedup_templates)
    @settings(max_examples=10)
    def test_rule_template_roundtrip(self, template: str):
        """Property: Dedup key template values roundtrip correctly."""
        rule = AlertRule(name="Test", dedup_key_template=template)
        assert rule.dedup_key_template == template

    @given(name=st.text(min_size=1, max_size=255))
    @settings(max_examples=20)
    def test_rule_name_roundtrip(self, name: str):
        """Property: Name values roundtrip correctly."""
        rule = AlertRule(name=name)
        assert rule.name == name


# =============================================================================
# Alert.to_dict() Serialization Tests (NEM-2583)
# =============================================================================


class TestAlertToDict:
    """Tests for Alert.to_dict() unified serialization method."""

    def test_to_dict_api_response_format(self, sample_alert):
        """Test to_dict returns all fields for API response format."""
        result = sample_alert.to_dict()

        assert result["id"] == "alert-001"
        assert result["event_id"] == 1
        assert result["rule_id"] == "rule-001"
        assert result["severity"] == "high"
        assert result["status"] == "pending"
        assert result["dedup_key"] == "front_door:rule-001"
        assert result["channels"] == ["email", "push"]
        assert result["alert_metadata"] == {"triggered_by": "person_detection"}
        # API format returns datetime objects
        assert "created_at" in result
        assert "updated_at" in result
        assert "delivered_at" in result

    def test_to_dict_websocket_format(self, sample_alert):
        """Test to_dict returns minimal fields with ISO timestamps for WebSocket."""
        result = sample_alert.to_dict(for_websocket=True)

        assert result["id"] == "alert-001"
        assert result["event_id"] == 1
        assert result["rule_id"] == "rule-001"
        assert result["severity"] == "high"
        assert result["status"] == "pending"
        assert result["dedup_key"] == "front_door:rule-001"
        # WebSocket format excludes these fields
        assert "channels" not in result
        assert "alert_metadata" not in result
        assert "delivered_at" not in result
        # WebSocket format uses ISO strings for timestamps
        assert "created_at" in result
        assert "updated_at" in result

    def test_to_dict_websocket_iso_timestamp_format(self, delivered_alert):
        """Test WebSocket format uses ISO string timestamps."""
        result = delivered_alert.to_dict(for_websocket=True)

        # Check timestamps are ISO strings, not datetime objects
        if result["created_at"] is not None:
            assert isinstance(result["created_at"], str)
            assert "T" in result["created_at"]  # ISO format has T separator
        if result["updated_at"] is not None:
            assert isinstance(result["updated_at"], str)
            assert "T" in result["updated_at"]

    def test_to_dict_api_response_datetime_objects(self, delivered_alert):
        """Test API response format returns datetime objects."""
        result = delivered_alert.to_dict(for_websocket=False)

        # API format returns datetime objects (or None)
        from datetime import datetime

        if result["created_at"] is not None:
            assert isinstance(result["created_at"], datetime)
        if result["updated_at"] is not None:
            assert isinstance(result["updated_at"], datetime)
        if result["delivered_at"] is not None:
            assert isinstance(result["delivered_at"], datetime)

    def test_to_dict_none_channels_returns_empty_list(self, minimal_alert):
        """Test that None channels returns empty list in API format."""
        result = minimal_alert.to_dict()
        assert result["channels"] == []

    def test_to_dict_handles_enum_values(self):
        """Test to_dict correctly extracts enum values."""
        alert = Alert(
            event_id=1,
            dedup_key="test",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.ACKNOWLEDGED,
        )
        result = alert.to_dict()

        assert result["severity"] == "critical"
        assert result["status"] == "acknowledged"

    def test_to_dict_handles_raw_string_values(self):
        """Test to_dict handles raw string values (non-enum)."""
        alert = Alert(
            event_id=1,
            dedup_key="test",
        )
        # Simulate raw string values (edge case)
        alert.severity = "high"  # type: ignore[assignment]
        alert.status = "pending"  # type: ignore[assignment]

        result = alert.to_dict()
        assert result["severity"] == "high"
        assert result["status"] == "pending"

    def test_to_dict_default_is_api_format(self):
        """Test that default (no args) returns API response format."""
        alert = Alert(
            event_id=1,
            dedup_key="test",
            channels=["email"],
            alert_metadata={"key": "value"},
        )
        result = alert.to_dict()

        # Default should include all fields (API format)
        assert "channels" in result
        assert "alert_metadata" in result
        assert "delivered_at" in result
        assert result["channels"] == ["email"]
        assert result["alert_metadata"] == {"key": "value"}

    def test_to_dict_websocket_excludes_fields(self):
        """Test WebSocket format excludes non-essential fields."""
        alert = Alert(
            event_id=1,
            dedup_key="test",
            channels=["email", "sms"],
            alert_metadata={"camera": "front_door"},
        )
        result = alert.to_dict(for_websocket=True)

        # WebSocket format should not include these
        assert "channels" not in result
        assert "alert_metadata" not in result
        assert "delivered_at" not in result

    @given(severity=alert_severities, status=alert_statuses)
    @settings(max_examples=20)
    def test_to_dict_enum_roundtrip(self, severity: AlertSeverity, status: AlertStatus):
        """Property: All enum combinations serialize correctly."""
        alert = Alert(
            event_id=1,
            dedup_key="test",
            severity=severity,
            status=status,
        )
        result = alert.to_dict()

        assert result["severity"] == severity.value
        assert result["status"] == status.value

        ws_result = alert.to_dict(for_websocket=True)
        assert ws_result["severity"] == severity.value
        assert ws_result["status"] == status.value
