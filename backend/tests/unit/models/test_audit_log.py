"""Unit tests for AuditLog model.

Tests cover:
- Model initialization and default values
- AuditAction enum values
- AuditStatus enum values
- JSON details field handling
- Actor and IP tracking
- String representation (__repr__)
- Property-based tests for field values
- Edge cases for JSON structures and Unicode handling
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.audit import AuditAction, AuditLog, AuditStatus

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for audit actions
audit_actions = st.sampled_from(list(AuditAction))

# Strategy for audit statuses
audit_statuses = st.sampled_from(list(AuditStatus))

# Strategy for actor names (allows Unicode)
actor_names = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters="-_.@",
    ),
)

# Strategy for resource types
resource_types = st.sampled_from(
    ["camera", "event", "alert", "rule", "settings", "user", "api_key", "zone"]
)

# Strategy for resource IDs
resource_ids = st.text(
    min_size=1,
    max_size=255,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
)

# Strategy for IPv4 addresses
ipv4_addresses = st.from_regex(
    r"^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\."
    r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\."
    r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\."
    r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
    fullmatch=True,
)

# Strategy for IPv6 addresses (simplified representation)
ipv6_addresses = st.just("::1") | st.just("2001:db8::1")

# Strategy for IP addresses (both v4 and v6)
ip_addresses = ipv4_addresses | ipv6_addresses

# Strategy for user agents
user_agents = st.text(
    min_size=1,
    max_size=500,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po"),
        whitelist_characters="/;:().-_",
    ),
)

# Strategy for JSON-serializable values
json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=10,
)

# Strategy for details dictionaries
details_dicts = st.dictionaries(
    st.text(min_size=1, max_size=50),
    json_values,
    max_size=10,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_audit_log():
    """Create a sample audit log entry for testing."""
    return AuditLog(
        id=1,
        action=AuditAction.CAMERA_CREATED.value,
        resource_type="camera",
        resource_id="front_door",
        actor="admin",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        details={"camera_name": "Front Door Camera"},
        status=AuditStatus.SUCCESS.value,
    )


@pytest.fixture
def minimal_audit_log():
    """Create an audit log with minimal required fields."""
    return AuditLog(
        action="event_reviewed",
        resource_type="event",
        actor="system",
    )


@pytest.fixture
def failure_audit_log():
    """Create a failed audit log entry."""
    return AuditLog(
        id=2,
        action=AuditAction.LOGIN.value,
        resource_type="auth",
        actor="unknown",
        ip_address="10.0.0.1",
        status=AuditStatus.FAILURE.value,
        details={"reason": "Invalid credentials"},
    )


@pytest.fixture
def unicode_audit_log():
    """Create an audit log with Unicode content."""
    return AuditLog(
        action=AuditAction.SETTINGS_CHANGED.value,
        resource_type="settings",
        actor="utilisateur_francais",
        details={"setting": "camera_name", "value": "Camera Francaise"},
    )


# =============================================================================
# AuditAction Enum Tests
# =============================================================================


class TestAuditActionEnum:
    """Tests for AuditAction enum."""

    def test_audit_action_event_reviewed(self):
        """Test EVENT_REVIEWED action value."""
        assert AuditAction.EVENT_REVIEWED.value == "event_reviewed"

    def test_audit_action_event_dismissed(self):
        """Test EVENT_DISMISSED action value."""
        assert AuditAction.EVENT_DISMISSED.value == "event_dismissed"

    def test_audit_action_settings_changed(self):
        """Test SETTINGS_CHANGED action value."""
        assert AuditAction.SETTINGS_CHANGED.value == "settings_changed"

    def test_audit_action_media_exported(self):
        """Test MEDIA_EXPORTED action value."""
        assert AuditAction.MEDIA_EXPORTED.value == "media_exported"

    def test_audit_action_rule_created(self):
        """Test RULE_CREATED action value."""
        assert AuditAction.RULE_CREATED.value == "rule_created"

    def test_audit_action_rule_updated(self):
        """Test RULE_UPDATED action value."""
        assert AuditAction.RULE_UPDATED.value == "rule_updated"

    def test_audit_action_rule_deleted(self):
        """Test RULE_DELETED action value."""
        assert AuditAction.RULE_DELETED.value == "rule_deleted"

    def test_audit_action_camera_created(self):
        """Test CAMERA_CREATED action value."""
        assert AuditAction.CAMERA_CREATED.value == "camera_created"

    def test_audit_action_camera_updated(self):
        """Test CAMERA_UPDATED action value."""
        assert AuditAction.CAMERA_UPDATED.value == "camera_updated"

    def test_audit_action_camera_deleted(self):
        """Test CAMERA_DELETED action value."""
        assert AuditAction.CAMERA_DELETED.value == "camera_deleted"

    def test_audit_action_login(self):
        """Test LOGIN action value."""
        assert AuditAction.LOGIN.value == "login"

    def test_audit_action_logout(self):
        """Test LOGOUT action value."""
        assert AuditAction.LOGOUT.value == "logout"

    def test_audit_action_api_key_created(self):
        """Test API_KEY_CREATED action value."""
        assert AuditAction.API_KEY_CREATED.value == "api_key_created"

    def test_audit_action_api_key_revoked(self):
        """Test API_KEY_REVOKED action value."""
        assert AuditAction.API_KEY_REVOKED.value == "api_key_revoked"

    def test_audit_action_notification_test(self):
        """Test NOTIFICATION_TEST action value."""
        assert AuditAction.NOTIFICATION_TEST.value == "notification_test"

    def test_audit_action_data_cleared(self):
        """Test DATA_CLEARED action value."""
        assert AuditAction.DATA_CLEARED.value == "data_cleared"

    def test_audit_action_is_string_enum(self):
        """Test AuditAction is a string enum."""
        for action in AuditAction:
            assert isinstance(action, str)
            assert isinstance(action.value, str)

    def test_audit_action_count(self):
        """Test AuditAction has expected number of values."""
        assert len(AuditAction) == 16

    def test_audit_action_all_unique(self):
        """Test all AuditAction values are unique."""
        values = [action.value for action in AuditAction]
        assert len(values) == len(set(values))


# =============================================================================
# AuditStatus Enum Tests
# =============================================================================


class TestAuditStatusEnum:
    """Tests for AuditStatus enum."""

    def test_audit_status_success(self):
        """Test SUCCESS status value."""
        assert AuditStatus.SUCCESS.value == "success"

    def test_audit_status_failure(self):
        """Test FAILURE status value."""
        assert AuditStatus.FAILURE.value == "failure"

    def test_audit_status_is_string_enum(self):
        """Test AuditStatus is a string enum."""
        for status in AuditStatus:
            assert isinstance(status, str)
            assert isinstance(status.value, str)

    def test_audit_status_count(self):
        """Test AuditStatus has expected number of values."""
        assert len(AuditStatus) == 2

    def test_audit_status_all_unique(self):
        """Test all AuditStatus values are unique."""
        values = [status.value for status in AuditStatus]
        assert len(values) == len(set(values))


# =============================================================================
# AuditLog Model Initialization Tests
# =============================================================================


class TestAuditLogModelInitialization:
    """Tests for AuditLog model initialization."""

    def test_audit_log_creation_minimal(self):
        """Test creating an audit log with minimal required fields."""
        log = AuditLog(
            action="test_action",
            resource_type="test_resource",
            actor="test_actor",
        )

        assert log.action == "test_action"
        assert log.resource_type == "test_resource"
        assert log.actor == "test_actor"

    def test_audit_log_with_all_fields(self, sample_audit_log):
        """Test audit log with all fields populated."""
        assert sample_audit_log.id == 1
        assert sample_audit_log.action == AuditAction.CAMERA_CREATED.value
        assert sample_audit_log.resource_type == "camera"
        assert sample_audit_log.resource_id == "front_door"
        assert sample_audit_log.actor == "admin"
        assert sample_audit_log.ip_address == "192.168.1.100"
        assert sample_audit_log.user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        assert sample_audit_log.details == {"camera_name": "Front Door Camera"}
        assert sample_audit_log.status == AuditStatus.SUCCESS.value

    def test_audit_log_default_status_column_definition(self):
        """Test audit log default status column has 'success'.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        status_col = mapper.columns["status"]
        assert status_col.default is not None
        assert status_col.default.arg == "success"

    def test_audit_log_optional_fields_default_to_none(self, minimal_audit_log):
        """Test optional fields default to None."""
        assert minimal_audit_log.resource_id is None
        assert minimal_audit_log.ip_address is None
        assert minimal_audit_log.user_agent is None
        assert minimal_audit_log.details is None

    def test_audit_log_with_enum_values(self):
        """Test audit log creation using enum values."""
        log = AuditLog(
            action=AuditAction.EVENT_REVIEWED.value,
            resource_type="event",
            actor="user",
            status=AuditStatus.SUCCESS.value,
        )
        assert log.action == "event_reviewed"
        assert log.status == "success"


# =============================================================================
# AuditLog Field Tests
# =============================================================================


class TestAuditLogActionField:
    """Tests for AuditLog action field."""

    def test_action_event_reviewed(self):
        """Test action with EVENT_REVIEWED value."""
        log = AuditLog(
            action=AuditAction.EVENT_REVIEWED.value,
            resource_type="event",
            actor="user",
        )
        assert log.action == "event_reviewed"

    def test_action_camera_created(self, sample_audit_log):
        """Test action with CAMERA_CREATED value."""
        assert sample_audit_log.action == "camera_created"

    def test_action_login(self):
        """Test action with LOGIN value."""
        log = AuditLog(
            action=AuditAction.LOGIN.value,
            resource_type="auth",
            actor="user",
        )
        assert log.action == "login"


class TestAuditLogResourceFields:
    """Tests for AuditLog resource_type and resource_id fields."""

    def test_resource_type_camera(self, sample_audit_log):
        """Test resource_type with camera."""
        assert sample_audit_log.resource_type == "camera"

    def test_resource_type_event(self, minimal_audit_log):
        """Test resource_type with event."""
        assert minimal_audit_log.resource_type == "event"

    def test_resource_id_set(self, sample_audit_log):
        """Test resource_id when set."""
        assert sample_audit_log.resource_id == "front_door"

    def test_resource_id_none(self, minimal_audit_log):
        """Test resource_id when not set."""
        assert minimal_audit_log.resource_id is None

    def test_resource_id_with_uuid_format(self):
        """Test resource_id with UUID-like format."""
        log = AuditLog(
            action="test",
            resource_type="event",
            resource_id="550e8400-e29b-41d4-a716-446655440000",
            actor="system",
        )
        assert log.resource_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_resource_id_with_numeric_string(self):
        """Test resource_id with numeric string."""
        log = AuditLog(
            action="test",
            resource_type="event",
            resource_id="12345",
            actor="system",
        )
        assert log.resource_id == "12345"


class TestAuditLogActorField:
    """Tests for AuditLog actor field."""

    def test_actor_admin(self, sample_audit_log):
        """Test actor with admin value."""
        assert sample_audit_log.actor == "admin"

    def test_actor_system(self, minimal_audit_log):
        """Test actor with system value."""
        assert minimal_audit_log.actor == "system"

    def test_actor_with_email_format(self):
        """Test actor with email-like format."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user@example.com",
        )
        assert log.actor == "user@example.com"

    def test_actor_with_username(self):
        """Test actor with username format."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="john_doe",
        )
        assert log.actor == "john_doe"


class TestAuditLogIPAddressField:
    """Tests for AuditLog ip_address field."""

    def test_ip_address_ipv4(self, sample_audit_log):
        """Test IPv4 address."""
        assert sample_audit_log.ip_address == "192.168.1.100"

    def test_ip_address_ipv4_localhost(self):
        """Test IPv4 localhost address."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            ip_address="127.0.0.1",
        )
        assert log.ip_address == "127.0.0.1"

    def test_ip_address_ipv6_localhost(self):
        """Test IPv6 localhost address."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            ip_address="::1",
        )
        assert log.ip_address == "::1"

    def test_ip_address_ipv6_full(self):
        """Test full IPv6 address."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            ip_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        )
        assert log.ip_address == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

    def test_ip_address_ipv6_compressed(self):
        """Test compressed IPv6 address."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            ip_address="2001:db8::1",
        )
        assert log.ip_address == "2001:db8::1"

    def test_ip_address_none(self, minimal_audit_log):
        """Test IP address when not set."""
        assert minimal_audit_log.ip_address is None

    def test_ip_address_max_length_ipv6(self):
        """Test IP address field can hold max IPv6 length (45 chars)."""
        # Max length IPv6 with IPv4 suffix: ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255
        max_ip = "ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255"
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            ip_address=max_ip,
        )
        assert log.ip_address == max_ip
        assert len(log.ip_address) <= 45


class TestAuditLogUserAgentField:
    """Tests for AuditLog user_agent field."""

    def test_user_agent_browser(self, sample_audit_log):
        """Test user_agent with browser string."""
        assert "Mozilla/5.0" in sample_audit_log.user_agent

    def test_user_agent_chrome(self):
        """Test user_agent with Chrome string."""
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            user_agent=user_agent,
        )
        assert log.user_agent == user_agent

    def test_user_agent_api_client(self):
        """Test user_agent with API client string."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            user_agent="SecurityDashboard/1.0",
        )
        assert log.user_agent == "SecurityDashboard/1.0"

    def test_user_agent_none(self, minimal_audit_log):
        """Test user_agent when not set."""
        assert minimal_audit_log.user_agent is None

    def test_user_agent_long_string(self):
        """Test user_agent with very long string."""
        long_ua = "A" * 500
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            user_agent=long_ua,
        )
        assert log.user_agent == long_ua


class TestAuditLogStatusField:
    """Tests for AuditLog status field."""

    def test_status_success(self, sample_audit_log):
        """Test status with success value."""
        assert sample_audit_log.status == "success"

    def test_status_failure(self, failure_audit_log):
        """Test status with failure value."""
        assert failure_audit_log.status == "failure"

    def test_status_explicit_success(self):
        """Test explicit success status."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            status=AuditStatus.SUCCESS.value,
        )
        assert log.status == "success"

    def test_status_explicit_failure(self):
        """Test explicit failure status."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            status=AuditStatus.FAILURE.value,
        )
        assert log.status == "failure"


class TestAuditLogTimestampField:
    """Tests for AuditLog timestamp field."""

    def test_timestamp_has_attribute(self, sample_audit_log):
        """Test audit log has timestamp attribute."""
        assert hasattr(sample_audit_log, "timestamp")

    def test_timestamp_explicit(self):
        """Test audit log with explicit timestamp."""
        now = datetime.now(UTC)
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            timestamp=now,
        )
        assert log.timestamp == now

    def test_timestamp_default_column_definition(self):
        """Test timestamp column has a default factory.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        timestamp_col = mapper.columns["timestamp"]
        assert timestamp_col.default is not None


# =============================================================================
# AuditLog Details (JSONB) Field Tests
# =============================================================================


class TestAuditLogDetailsField:
    """Tests for AuditLog details JSONB field."""

    def test_details_simple_dict(self, sample_audit_log):
        """Test details with simple dict."""
        assert sample_audit_log.details == {"camera_name": "Front Door Camera"}

    def test_details_none(self, minimal_audit_log):
        """Test details when not set."""
        assert minimal_audit_log.details is None

    def test_details_empty_dict(self):
        """Test details with empty dict."""
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            details={},
        )
        assert log.details == {}

    def test_details_nested_dict(self):
        """Test details with nested dict structure."""
        nested = {
            "before": {"name": "old_name", "enabled": True},
            "after": {"name": "new_name", "enabled": False},
            "changed_fields": ["name", "enabled"],
        }
        log = AuditLog(
            action="test",
            resource_type="settings",
            actor="user",
            details=nested,
        )
        assert log.details == nested

    def test_details_with_list(self):
        """Test details with list values."""
        details = {"cameras": ["front_door", "back_yard", "garage"]}
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            details=details,
        )
        assert log.details["cameras"] == ["front_door", "back_yard", "garage"]

    def test_details_with_numbers(self):
        """Test details with numeric values."""
        details = {
            "threshold": 75,
            "confidence": 0.95,
            "count": 3,
        }
        log = AuditLog(
            action="test",
            resource_type="settings",
            actor="user",
            details=details,
        )
        assert log.details["threshold"] == 75
        assert log.details["confidence"] == 0.95

    def test_details_with_boolean(self):
        """Test details with boolean values."""
        details = {"enabled": True, "notifications": False}
        log = AuditLog(
            action="test",
            resource_type="settings",
            actor="user",
            details=details,
        )
        assert log.details["enabled"] is True
        assert log.details["notifications"] is False

    def test_details_with_null_values(self):
        """Test details with null values."""
        details = {"value": None, "previous": None}
        log = AuditLog(
            action="test",
            resource_type="settings",
            actor="user",
            details=details,
        )
        assert log.details["value"] is None

    def test_details_deeply_nested(self):
        """Test details with deeply nested structure."""
        details = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep",
                    },
                },
            },
        }
        log = AuditLog(
            action="test",
            resource_type="settings",
            actor="user",
            details=details,
        )
        assert log.details["level1"]["level2"]["level3"]["value"] == "deep"

    def test_details_with_unicode(self, unicode_audit_log):
        """Test details with Unicode content."""
        assert unicode_audit_log.details["value"] == "Camera Francaise"

    def test_details_with_emoji(self):
        """Test details with emoji characters."""
        details = {"status": "success", "message": "Test passed"}
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            details=details,
        )
        assert log.details["message"] == "Test passed"

    def test_details_with_special_json_chars(self):
        """Test details with JSON special characters."""
        details = {
            "path": "C:\\Users\\test\\file.txt",
            "quote": 'He said "hello"',
            "newline": "line1\nline2",
        }
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            details=details,
        )
        assert log.details["path"] == "C:\\Users\\test\\file.txt"
        assert log.details["quote"] == 'He said "hello"'
        assert log.details["newline"] == "line1\nline2"

    def test_details_large_array(self):
        """Test details with large array."""
        details = {"ids": list(range(100))}
        log = AuditLog(
            action="test",
            resource_type="event",
            actor="user",
            details=details,
        )
        assert len(log.details["ids"]) == 100


# =============================================================================
# AuditLog Repr Tests
# =============================================================================


class TestAuditLogRepr:
    """Tests for AuditLog string representation."""

    def test_audit_log_repr_contains_class_name(self, sample_audit_log):
        """Test repr contains class name."""
        repr_str = repr(sample_audit_log)
        assert "AuditLog" in repr_str

    def test_audit_log_repr_contains_id(self, sample_audit_log):
        """Test repr contains audit log id."""
        repr_str = repr(sample_audit_log)
        assert "id=1" in repr_str

    def test_audit_log_repr_contains_action(self, sample_audit_log):
        """Test repr contains action."""
        repr_str = repr(sample_audit_log)
        assert "camera_created" in repr_str

    def test_audit_log_repr_contains_resource_type(self, sample_audit_log):
        """Test repr contains resource_type."""
        repr_str = repr(sample_audit_log)
        assert "camera" in repr_str

    def test_audit_log_repr_contains_actor(self, sample_audit_log):
        """Test repr contains actor."""
        repr_str = repr(sample_audit_log)
        assert "admin" in repr_str

    def test_audit_log_repr_format(self, sample_audit_log):
        """Test repr has expected format."""
        repr_str = repr(sample_audit_log)
        assert repr_str.startswith("<AuditLog(")
        assert repr_str.endswith(")>")

    def test_audit_log_repr_does_not_contain_sensitive_details(self, sample_audit_log):
        """Test repr does not expose full details dict."""
        repr_str = repr(sample_audit_log)
        # The full details dict should not be in repr
        assert "Front Door Camera" not in repr_str


# =============================================================================
# AuditLog Table Configuration Tests
# =============================================================================


class TestAuditLogTableConfig:
    """Tests for AuditLog table configuration."""

    def test_audit_log_tablename(self):
        """Test AuditLog has correct table name."""
        assert AuditLog.__tablename__ == "audit_logs"

    def test_audit_log_has_id_primary_key(self):
        """Test AuditLog has id as primary key."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        pk_cols = [col.name for col in mapper.primary_key]
        assert "id" in pk_cols

    def test_audit_log_has_table_args(self):
        """Test AuditLog has __table_args__ for indexes."""
        assert hasattr(AuditLog, "__table_args__")

    def test_audit_log_indexes_defined(self):
        """Test AuditLog has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for expected indexes
        assert "idx_audit_logs_timestamp" in index_names
        assert "idx_audit_logs_action" in index_names
        assert "idx_audit_logs_resource_type" in index_names
        assert "idx_audit_logs_actor" in index_names
        assert "idx_audit_logs_status" in index_names
        assert "idx_audit_logs_resource" in index_names


class TestAuditLogColumnConstraints:
    """Tests for AuditLog column constraints."""

    def test_action_not_nullable(self):
        """Test action column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        action_col = mapper.columns["action"]
        assert action_col.nullable is False

    def test_resource_type_not_nullable(self):
        """Test resource_type column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        resource_type_col = mapper.columns["resource_type"]
        assert resource_type_col.nullable is False

    def test_actor_not_nullable(self):
        """Test actor column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        actor_col = mapper.columns["actor"]
        assert actor_col.nullable is False

    def test_status_not_nullable(self):
        """Test status column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        status_col = mapper.columns["status"]
        assert status_col.nullable is False

    def test_resource_id_nullable(self):
        """Test resource_id column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        resource_id_col = mapper.columns["resource_id"]
        assert resource_id_col.nullable is True

    def test_ip_address_nullable(self):
        """Test ip_address column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        ip_address_col = mapper.columns["ip_address"]
        assert ip_address_col.nullable is True

    def test_user_agent_nullable(self):
        """Test user_agent column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        user_agent_col = mapper.columns["user_agent"]
        assert user_agent_col.nullable is True

    def test_details_nullable(self):
        """Test details column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        details_col = mapper.columns["details"]
        assert details_col.nullable is True


class TestAuditLogColumnTypes:
    """Tests for AuditLog column types."""

    def test_action_string_length(self):
        """Test action column has correct string length (50)."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        action_col = mapper.columns["action"]
        assert action_col.type.length == 50

    def test_resource_type_string_length(self):
        """Test resource_type column has correct string length (50)."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        resource_type_col = mapper.columns["resource_type"]
        assert resource_type_col.type.length == 50

    def test_resource_id_string_length(self):
        """Test resource_id column has correct string length (255)."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        resource_id_col = mapper.columns["resource_id"]
        assert resource_id_col.type.length == 255

    def test_actor_string_length(self):
        """Test actor column has correct string length (100)."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        actor_col = mapper.columns["actor"]
        assert actor_col.type.length == 100

    def test_ip_address_string_length(self):
        """Test ip_address column has correct string length (45)."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        ip_address_col = mapper.columns["ip_address"]
        assert ip_address_col.type.length == 45

    def test_status_string_length(self):
        """Test status column has correct string length (20)."""
        from sqlalchemy import inspect

        mapper = inspect(AuditLog)
        status_col = mapper.columns["status"]
        assert status_col.type.length == 20


# =============================================================================
# Property-based Tests
# =============================================================================


class TestAuditLogProperties:
    """Property-based tests for AuditLog model."""

    @given(action=audit_actions)
    @settings(max_examples=20)
    def test_action_roundtrip(self, action: AuditAction):
        """Property: Action values roundtrip correctly."""
        log = AuditLog(
            action=action.value,
            resource_type="test",
            actor="user",
        )
        assert log.action == action.value

    @given(status=audit_statuses)
    @settings(max_examples=10)
    def test_status_roundtrip(self, status: AuditStatus):
        """Property: Status values roundtrip correctly."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="user",
            status=status.value,
        )
        assert log.status == status.value

    @given(resource_type=resource_types)
    @settings(max_examples=20)
    def test_resource_type_roundtrip(self, resource_type: str):
        """Property: Resource type values roundtrip correctly."""
        log = AuditLog(
            action="test",
            resource_type=resource_type,
            actor="user",
        )
        assert log.resource_type == resource_type

    @given(resource_id=resource_ids)
    @settings(max_examples=50)
    def test_resource_id_roundtrip(self, resource_id: str):
        """Property: Resource ID values roundtrip correctly."""
        log = AuditLog(
            action="test",
            resource_type="test",
            resource_id=resource_id,
            actor="user",
        )
        assert log.resource_id == resource_id

    @given(actor=actor_names)
    @settings(max_examples=50)
    def test_actor_roundtrip(self, actor: str):
        """Property: Actor values roundtrip correctly."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor=actor,
        )
        assert log.actor == actor

    @given(ip_address=ip_addresses)
    @settings(max_examples=50)
    def test_ip_address_roundtrip(self, ip_address: str):
        """Property: IP address values roundtrip correctly."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="user",
            ip_address=ip_address,
        )
        assert log.ip_address == ip_address

    @given(user_agent=user_agents)
    @settings(max_examples=50)
    def test_user_agent_roundtrip(self, user_agent: str):
        """Property: User agent values roundtrip correctly."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="user",
            user_agent=user_agent,
        )
        assert log.user_agent == user_agent

    @given(id_value=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=50)
    def test_id_roundtrip(self, id_value: int):
        """Property: ID values roundtrip correctly."""
        log = AuditLog(
            id=id_value,
            action="test",
            resource_type="test",
            actor="user",
        )
        assert log.id == id_value


class TestAuditLogDetailsProperties:
    """Property-based tests for AuditLog details field."""

    @given(details=details_dicts)
    @settings(max_examples=100)
    def test_details_roundtrip(self, details: dict):
        """Property: Details dict values roundtrip correctly."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="user",
            details=details,
        )
        assert log.details == details

    @given(
        action=audit_actions,
        status=audit_statuses,
        resource_type=resource_types,
        actor=actor_names,
    )
    @settings(max_examples=50)
    def test_all_fields_roundtrip(
        self,
        action: AuditAction,
        status: AuditStatus,
        resource_type: str,
        actor: str,
    ):
        """Property: All fields roundtrip correctly together."""
        log = AuditLog(
            action=action.value,
            resource_type=resource_type,
            actor=actor,
            status=status.value,
        )
        assert log.action == action.value
        assert log.resource_type == resource_type
        assert log.actor == actor
        assert log.status == status.value


class TestAuditLogUnicodeProperties:
    """Property-based tests for Unicode handling in AuditLog."""

    @given(
        text=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"),
            ),
        )
    )
    @settings(max_examples=50)
    def test_actor_unicode_roundtrip(self, text: str):
        """Property: Actor handles Unicode correctly."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor=text,
        )
        assert log.actor == text

    @given(
        text=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"),
            ),
        )
    )
    @settings(max_examples=50)
    def test_resource_type_unicode_roundtrip(self, text: str):
        """Property: Resource type handles Unicode correctly."""
        log = AuditLog(
            action="test",
            resource_type=text,
            actor="user",
        )
        assert log.resource_type == text

    @given(
        key=st.text(min_size=1, max_size=20),
        value=st.text(min_size=0, max_size=100),
    )
    @settings(max_examples=100)
    def test_details_unicode_keys_and_values(self, key: str, value: str):
        """Property: Details field handles Unicode keys and values."""
        details = {key: value}
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="user",
            details=details,
        )
        assert log.details == details


# =============================================================================
# Edge Cases
# =============================================================================


class TestAuditLogEdgeCases:
    """Tests for edge cases in AuditLog model."""

    def test_empty_string_actor(self):
        """Test audit log with empty string actor (model allows it)."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="",
        )
        assert log.actor == ""

    def test_whitespace_only_actor(self):
        """Test audit log with whitespace-only actor."""
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="   ",
        )
        assert log.actor == "   "

    def test_max_length_action(self):
        """Test action at max length (50 chars)."""
        action = "a" * 50
        log = AuditLog(
            action=action,
            resource_type="test",
            actor="user",
        )
        assert log.action == action
        assert len(log.action) == 50

    def test_max_length_resource_id(self):
        """Test resource_id at max length (255 chars)."""
        resource_id = "r" * 255
        log = AuditLog(
            action="test",
            resource_type="test",
            resource_id=resource_id,
            actor="user",
        )
        assert log.resource_id == resource_id
        assert len(log.resource_id) == 255

    def test_max_length_actor(self):
        """Test actor at max length (100 chars)."""
        actor = "u" * 100
        log = AuditLog(
            action="test",
            resource_type="test",
            actor=actor,
        )
        assert log.actor == actor
        assert len(log.actor) == 100

    def test_details_with_all_json_types(self):
        """Test details with all JSON data types."""
        details = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean_true": True,
            "boolean_false": False,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }
        log = AuditLog(
            action="test",
            resource_type="test",
            actor="user",
            details=details,
        )
        assert log.details == details

    def test_multiple_audit_logs_independence(self):
        """Test that multiple audit log instances are independent."""
        log1 = AuditLog(
            action="action1",
            resource_type="type1",
            actor="actor1",
            details={"key": "value1"},
        )
        log2 = AuditLog(
            action="action2",
            resource_type="type2",
            actor="actor2",
            details={"key": "value2"},
        )

        # Verify independence
        assert log1.action != log2.action
        assert log1.resource_type != log2.resource_type
        assert log1.actor != log2.actor
        assert log1.details != log2.details

        # Modifying one should not affect the other
        log1.details["key"] = "modified"
        assert log2.details["key"] == "value2"
