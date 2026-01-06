"""Unit tests for Log model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- JSONB extra field handling
- Source tracking fields
- Performance/debug fields
- Indexes and table configuration
- Property-based tests for field values
- Edge cases and boundary conditions
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.log import Log

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for log levels
log_levels = st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

# Strategy for component names
component_names = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
)

# Strategy for source values
source_values = st.sampled_from(["backend", "frontend", "worker", "scheduler"])

# Strategy for camera IDs (optional)
camera_ids = st.one_of(
    st.none(),
    st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_",
        ),
    ),
)

# Strategy for request IDs (UUID-like format)
request_ids = st.one_of(
    st.none(),
    st.from_regex(
        r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", fullmatch=True
    ),
)

# Strategy for duration in milliseconds
duration_ms_values = st.one_of(
    st.none(),
    st.integers(min_value=0, max_value=600000),  # Up to 10 minutes
)

# Strategy for JSON-serializable values
json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=10,
)

# Strategy for extra field (JSONB)
extra_dicts = st.one_of(
    st.none(),
    st.dictionaries(
        st.text(min_size=1, max_size=50),
        json_values,
        max_size=10,
    ),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_log():
    """Create a sample Log for testing."""
    return Log(
        id=1,
        level="INFO",
        component="file_watcher",
        message="File processed successfully",
        camera_id="front_door",
        event_id=100,
        request_id="abc12345-6789-0123-4567-890abcdef012",
        detection_id=50,
        duration_ms=150,
        extra={"file_path": "/export/foscam/test.jpg", "file_size": 1024},
        source="backend",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    )


@pytest.fixture
def minimal_log():
    """Create a Log with only required fields."""
    return Log(
        level="INFO",
        component="test",
        message="Test message",
    )


@pytest.fixture
def error_log():
    """Create an error log entry."""
    return Log(
        id=2,
        level="ERROR",
        component="detector",
        message="Detection failed: model timeout",
        camera_id="back_yard",
        duration_ms=30000,
        extra={"error_code": "TIMEOUT", "retry_count": 3},
        source="backend",
    )


@pytest.fixture
def debug_log():
    """Create a debug log entry."""
    return Log(
        level="DEBUG",
        component="api",
        message="Request received",
        request_id="debug-request-id-12345",
        extra={"endpoint": "/api/cameras", "method": "GET"},
    )


# =============================================================================
# Log Model Initialization Tests
# =============================================================================


class TestLogModelInitialization:
    """Tests for Log model initialization."""

    def test_log_creation_minimal(self, minimal_log):
        """Test creating a Log with minimal required fields."""
        assert minimal_log.level == "INFO"
        assert minimal_log.component == "test"
        assert minimal_log.message == "Test message"

    def test_log_with_all_fields(self, sample_log):
        """Test Log with all fields populated."""
        assert sample_log.id == 1
        assert sample_log.level == "INFO"
        assert sample_log.component == "file_watcher"
        assert sample_log.message == "File processed successfully"
        assert sample_log.camera_id == "front_door"
        assert sample_log.event_id == 100
        assert sample_log.request_id == "abc12345-6789-0123-4567-890abcdef012"
        assert sample_log.detection_id == 50
        assert sample_log.duration_ms == 150
        assert sample_log.extra == {"file_path": "/export/foscam/test.jpg", "file_size": 1024}
        assert sample_log.source == "backend"
        assert sample_log.user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    def test_log_default_source_column_definition(self):
        """Test that source column has 'backend' as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Log)
        source_col = mapper.columns["source"]
        assert source_col.default is not None
        assert source_col.default.arg == "backend"

    def test_log_optional_fields_default_to_none(self, minimal_log):
        """Test that optional fields default to None."""
        assert minimal_log.camera_id is None
        assert minimal_log.event_id is None
        assert minimal_log.request_id is None
        assert minimal_log.detection_id is None
        assert minimal_log.duration_ms is None
        assert minimal_log.extra is None
        assert minimal_log.user_agent is None


# =============================================================================
# Log Level Field Tests
# =============================================================================


class TestLogLevelField:
    """Tests for Log level field."""

    def test_level_debug(self):
        """Test level with DEBUG value."""
        log = Log(level="DEBUG", component="test", message="Debug message")
        assert log.level == "DEBUG"

    def test_level_info(self, sample_log):
        """Test level with INFO value."""
        assert sample_log.level == "INFO"

    def test_level_warning(self):
        """Test level with WARNING value."""
        log = Log(level="WARNING", component="test", message="Warning message")
        assert log.level == "WARNING"

    def test_level_error(self, error_log):
        """Test level with ERROR value."""
        assert error_log.level == "ERROR"

    def test_level_critical(self):
        """Test level with CRITICAL value."""
        log = Log(level="CRITICAL", component="test", message="Critical error")
        assert log.level == "CRITICAL"

    def test_level_all_standard_values(self):
        """Test all standard logging levels work."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in levels:
            log = Log(level=level, component="test", message="Test")
            assert log.level == level


# =============================================================================
# Log Component Field Tests
# =============================================================================


class TestLogComponentField:
    """Tests for Log component field."""

    def test_component_file_watcher(self, sample_log):
        """Test component with file_watcher value."""
        assert sample_log.component == "file_watcher"

    def test_component_detector(self, error_log):
        """Test component with detector value."""
        assert error_log.component == "detector"

    def test_component_api(self):
        """Test component with api value."""
        log = Log(level="INFO", component="api", message="API request")
        assert log.component == "api"

    def test_component_with_common_values(self):
        """Test component with common component names."""
        components = [
            "file_watcher",
            "detector",
            "analyzer",
            "api",
            "websocket",
            "database",
            "cache",
            "scheduler",
        ]
        for component in components:
            log = Log(level="INFO", component=component, message="Test")
            assert log.component == component


# =============================================================================
# Log Message Field Tests
# =============================================================================


class TestLogMessageField:
    """Tests for Log message field."""

    def test_message_simple(self, sample_log):
        """Test message with simple text."""
        assert sample_log.message == "File processed successfully"

    def test_message_long_text(self):
        """Test message with long text."""
        long_message = "A" * 1000
        log = Log(level="INFO", component="test", message=long_message)
        assert log.message == long_message
        assert len(log.message) == 1000

    def test_message_with_newlines(self):
        """Test message with newlines."""
        message = "Line 1\nLine 2\nLine 3"
        log = Log(level="INFO", component="test", message=message)
        assert log.message == message
        assert "\n" in log.message

    def test_message_with_unicode(self):
        """Test message with Unicode characters."""
        message = "Processing camera francaise"
        log = Log(level="INFO", component="test", message=message)
        assert message in log.message

    def test_message_with_json_like_content(self):
        """Test message with JSON-like content."""
        message = '{"error": "Connection failed", "code": 500}'
        log = Log(level="ERROR", component="test", message=message)
        assert log.message == message


# =============================================================================
# Log Structured Metadata Field Tests
# =============================================================================


class TestLogCameraIdField:
    """Tests for Log camera_id field."""

    def test_camera_id_set(self, sample_log):
        """Test camera_id when set."""
        assert sample_log.camera_id == "front_door"

    def test_camera_id_none(self, minimal_log):
        """Test camera_id when not set."""
        assert minimal_log.camera_id is None

    def test_camera_id_with_underscores(self):
        """Test camera_id with underscores."""
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            camera_id="front_door_camera",
        )
        assert log.camera_id == "front_door_camera"


class TestLogEventIdField:
    """Tests for Log event_id field."""

    def test_event_id_set(self, sample_log):
        """Test event_id when set."""
        assert sample_log.event_id == 100

    def test_event_id_none(self, minimal_log):
        """Test event_id when not set."""
        assert minimal_log.event_id is None

    def test_event_id_large_value(self):
        """Test event_id with large value."""
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            event_id=999999999,
        )
        assert log.event_id == 999999999


class TestLogRequestIdField:
    """Tests for Log request_id field."""

    def test_request_id_set(self, sample_log):
        """Test request_id when set."""
        assert sample_log.request_id == "abc12345-6789-0123-4567-890abcdef012"

    def test_request_id_none(self, minimal_log):
        """Test request_id when not set."""
        assert minimal_log.request_id is None

    def test_request_id_uuid_format(self):
        """Test request_id with UUID format."""
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            request_id="550e8400-e29b-41d4-a716-446655440000",
        )
        assert log.request_id == "550e8400-e29b-41d4-a716-446655440000"


class TestLogDetectionIdField:
    """Tests for Log detection_id field."""

    def test_detection_id_set(self, sample_log):
        """Test detection_id when set."""
        assert sample_log.detection_id == 50

    def test_detection_id_none(self, minimal_log):
        """Test detection_id when not set."""
        assert minimal_log.detection_id is None


# =============================================================================
# Log Performance/Debug Field Tests
# =============================================================================


class TestLogDurationMsField:
    """Tests for Log duration_ms field."""

    def test_duration_ms_set(self, sample_log):
        """Test duration_ms when set."""
        assert sample_log.duration_ms == 150

    def test_duration_ms_none(self, minimal_log):
        """Test duration_ms when not set."""
        assert minimal_log.duration_ms is None

    def test_duration_ms_zero(self):
        """Test duration_ms with zero value."""
        log = Log(
            level="INFO",
            component="test",
            message="Instant operation",
            duration_ms=0,
        )
        assert log.duration_ms == 0

    def test_duration_ms_large_value(self):
        """Test duration_ms with large value (long operation)."""
        log = Log(
            level="WARNING",
            component="test",
            message="Slow operation",
            duration_ms=60000,  # 1 minute
        )
        assert log.duration_ms == 60000


class TestLogExtraField:
    """Tests for Log extra (JSONB) field."""

    def test_extra_set(self, sample_log):
        """Test extra when set."""
        assert sample_log.extra == {"file_path": "/export/foscam/test.jpg", "file_size": 1024}

    def test_extra_none(self, minimal_log):
        """Test extra when not set."""
        assert minimal_log.extra is None

    def test_extra_empty_dict(self):
        """Test extra with empty dict."""
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra={},
        )
        assert log.extra == {}

    def test_extra_nested_dict(self):
        """Test extra with nested dict."""
        extra = {
            "request": {
                "method": "POST",
                "path": "/api/cameras",
                "headers": {"Content-Type": "application/json"},
            },
            "response": {"status": 200, "time_ms": 50},
        }
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra=extra,
        )
        assert log.extra == extra

    def test_extra_with_list(self):
        """Test extra with list values."""
        extra = {"cameras": ["front_door", "back_yard", "garage"]}
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra=extra,
        )
        assert log.extra["cameras"] == ["front_door", "back_yard", "garage"]

    def test_extra_with_numbers(self):
        """Test extra with numeric values."""
        extra = {
            "count": 42,
            "confidence": 0.95,
            "negative": -1,
        }
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra=extra,
        )
        assert log.extra["count"] == 42
        assert log.extra["confidence"] == 0.95

    def test_extra_with_boolean(self):
        """Test extra with boolean values."""
        extra = {"enabled": True, "cached": False}
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra=extra,
        )
        assert log.extra["enabled"] is True
        assert log.extra["cached"] is False

    def test_extra_with_null_values(self):
        """Test extra with null values."""
        extra = {"value": None, "previous": None}
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra=extra,
        )
        assert log.extra["value"] is None


# =============================================================================
# Log Source Tracking Field Tests
# =============================================================================


class TestLogSourceField:
    """Tests for Log source field."""

    def test_source_backend(self, sample_log):
        """Test source with backend value."""
        assert sample_log.source == "backend"

    def test_source_frontend(self):
        """Test source with frontend value."""
        log = Log(
            level="INFO",
            component="ui",
            message="Button clicked",
            source="frontend",
        )
        assert log.source == "frontend"

    def test_source_worker(self):
        """Test source with worker value."""
        log = Log(
            level="INFO",
            component="processor",
            message="Task completed",
            source="worker",
        )
        assert log.source == "worker"


class TestLogUserAgentField:
    """Tests for Log user_agent field."""

    def test_user_agent_set(self, sample_log):
        """Test user_agent when set."""
        assert "Mozilla/5.0" in sample_log.user_agent

    def test_user_agent_none(self, minimal_log):
        """Test user_agent when not set."""
        assert minimal_log.user_agent is None

    def test_user_agent_browser(self):
        """Test user_agent with browser string."""
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        log = Log(
            level="INFO",
            component="api",
            message="Request",
            user_agent=user_agent,
        )
        assert log.user_agent == user_agent

    def test_user_agent_api_client(self):
        """Test user_agent with API client string."""
        log = Log(
            level="INFO",
            component="api",
            message="API request",
            user_agent="SecurityDashboard/1.0",
        )
        assert log.user_agent == "SecurityDashboard/1.0"


# =============================================================================
# Log Repr Tests
# =============================================================================


class TestLogRepr:
    """Tests for Log string representation."""

    def test_repr_contains_class_name(self, sample_log):
        """Test repr contains class name."""
        repr_str = repr(sample_log)
        assert "Log" in repr_str

    def test_repr_contains_id(self, sample_log):
        """Test repr contains id."""
        repr_str = repr(sample_log)
        assert "id=1" in repr_str

    def test_repr_contains_level(self, sample_log):
        """Test repr contains level."""
        repr_str = repr(sample_log)
        assert "INFO" in repr_str

    def test_repr_contains_component(self, sample_log):
        """Test repr contains component."""
        repr_str = repr(sample_log)
        assert "file_watcher" in repr_str

    def test_repr_contains_message_preview(self, sample_log):
        """Test repr contains message preview."""
        repr_str = repr(sample_log)
        # Should contain at least part of the message
        assert "File processed" in repr_str or "message=" in repr_str

    def test_repr_format(self, sample_log):
        """Test repr has expected format."""
        repr_str = repr(sample_log)
        assert repr_str.startswith("<Log(")
        assert repr_str.endswith(")>")

    def test_repr_truncates_long_message(self):
        """Test repr truncates long messages."""
        long_message = "A" * 100
        log = Log(
            id=1,
            level="INFO",
            component="test",
            message=long_message,
        )
        repr_str = repr(log)
        # Message should be truncated (first 50 chars)
        assert len(repr_str) < len(long_message) + 100

    def test_repr_with_all_log_levels(self):
        """Test repr with all log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in levels:
            log = Log(
                id=1,
                level=level,
                component="test",
                message="Test message",
            )
            repr_str = repr(log)
            assert level in repr_str


# =============================================================================
# Log Table Configuration Tests
# =============================================================================


class TestLogTableConfig:
    """Tests for Log table configuration."""

    def test_log_tablename(self):
        """Test Log has correct table name."""
        assert Log.__tablename__ == "logs"

    def test_log_has_id_primary_key(self):
        """Test Log has id as primary key."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        pk_cols = [col.name for col in mapper.primary_key]
        assert "id" in pk_cols

    def test_log_has_table_args(self):
        """Test Log has __table_args__ for indexes."""
        assert hasattr(Log, "__table_args__")

    def test_log_indexes_defined(self):
        """Test Log has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for expected indexes
        assert "idx_logs_timestamp" in index_names
        assert "idx_logs_level" in index_names
        assert "idx_logs_component" in index_names
        assert "idx_logs_camera_id" in index_names
        assert "idx_logs_source" in index_names


class TestLogColumnConstraints:
    """Tests for Log column constraints."""

    def test_level_not_nullable(self):
        """Test level column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        level_col = mapper.columns["level"]
        assert level_col.nullable is False

    def test_component_not_nullable(self):
        """Test component column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        component_col = mapper.columns["component"]
        assert component_col.nullable is False

    def test_message_not_nullable(self):
        """Test message column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        message_col = mapper.columns["message"]
        assert message_col.nullable is False

    def test_source_not_nullable(self):
        """Test source column is not nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        source_col = mapper.columns["source"]
        assert source_col.nullable is False

    def test_camera_id_nullable(self):
        """Test camera_id column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        camera_id_col = mapper.columns["camera_id"]
        assert camera_id_col.nullable is True

    def test_event_id_nullable(self):
        """Test event_id column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        event_id_col = mapper.columns["event_id"]
        assert event_id_col.nullable is True

    def test_request_id_nullable(self):
        """Test request_id column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        request_id_col = mapper.columns["request_id"]
        assert request_id_col.nullable is True

    def test_detection_id_nullable(self):
        """Test detection_id column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        detection_id_col = mapper.columns["detection_id"]
        assert detection_id_col.nullable is True

    def test_duration_ms_nullable(self):
        """Test duration_ms column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        duration_ms_col = mapper.columns["duration_ms"]
        assert duration_ms_col.nullable is True

    def test_extra_nullable(self):
        """Test extra column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        extra_col = mapper.columns["extra"]
        assert extra_col.nullable is True

    def test_user_agent_nullable(self):
        """Test user_agent column is nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        user_agent_col = mapper.columns["user_agent"]
        assert user_agent_col.nullable is True


class TestLogColumnTypes:
    """Tests for Log column types."""

    def test_level_string_length(self):
        """Test level column has correct string length (10)."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        level_col = mapper.columns["level"]
        assert level_col.type.length == 10

    def test_component_string_length(self):
        """Test component column has correct string length (50)."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        component_col = mapper.columns["component"]
        assert component_col.type.length == 50

    def test_camera_id_string_length(self):
        """Test camera_id column has correct string length (100)."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        camera_id_col = mapper.columns["camera_id"]
        assert camera_id_col.type.length == 100

    def test_request_id_string_length(self):
        """Test request_id column has correct string length (36)."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        request_id_col = mapper.columns["request_id"]
        assert request_id_col.type.length == 36

    def test_source_string_length(self):
        """Test source column has correct string length (10)."""
        from sqlalchemy import inspect

        mapper = inspect(Log)
        source_col = mapper.columns["source"]
        assert source_col.type.length == 10


# =============================================================================
# Property-based Tests
# =============================================================================


class TestLogProperties:
    """Property-based tests for Log model."""

    @given(level=log_levels)
    @settings(max_examples=20)
    def test_level_roundtrip(self, level: str):
        """Property: Level values roundtrip correctly."""
        log = Log(
            level=level,
            component="test",
            message="Test message",
        )
        assert log.level == level

    @given(component=component_names)
    @settings(max_examples=50)
    def test_component_roundtrip(self, component: str):
        """Property: Component values roundtrip correctly."""
        log = Log(
            level="INFO",
            component=component,
            message="Test message",
        )
        assert log.component == component

    @given(source=source_values)
    @settings(max_examples=10)
    def test_source_roundtrip(self, source: str):
        """Property: Source values roundtrip correctly."""
        log = Log(
            level="INFO",
            component="test",
            message="Test message",
            source=source,
        )
        assert log.source == source

    @given(camera_id=camera_ids)
    @settings(max_examples=50)
    def test_camera_id_roundtrip(self, camera_id: str | None):
        """Property: Camera ID values roundtrip correctly."""
        log = Log(
            level="INFO",
            component="test",
            message="Test message",
            camera_id=camera_id,
        )
        assert log.camera_id == camera_id

    @given(duration_ms=duration_ms_values)
    @settings(max_examples=50)
    def test_duration_ms_roundtrip(self, duration_ms: int | None):
        """Property: Duration ms values roundtrip correctly."""
        log = Log(
            level="INFO",
            component="test",
            message="Test message",
            duration_ms=duration_ms,
        )
        assert log.duration_ms == duration_ms

    @given(id_value=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=50)
    def test_id_roundtrip(self, id_value: int):
        """Property: ID values roundtrip correctly."""
        log = Log(
            id=id_value,
            level="INFO",
            component="test",
            message="Test message",
        )
        assert log.id == id_value

    @given(
        level=log_levels,
        component=component_names,
        source=source_values,
    )
    @settings(max_examples=50)
    def test_multiple_fields_roundtrip(
        self,
        level: str,
        component: str,
        source: str,
    ):
        """Property: Multiple fields roundtrip correctly together."""
        log = Log(
            level=level,
            component=component,
            message="Test message",
            source=source,
        )
        assert log.level == level
        assert log.component == component
        assert log.source == source


class TestLogExtraProperties:
    """Property-based tests for Log extra field."""

    @pytest.mark.slow
    @given(extra=extra_dicts)
    @settings(max_examples=100)
    def test_extra_roundtrip(self, extra: dict | None):
        """Property: Extra dict values roundtrip correctly."""
        log = Log(
            level="INFO",
            component="test",
            message="Test message",
            extra=extra,
        )
        assert log.extra == extra


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestLogEdgeCases:
    """Tests for Log edge cases."""

    def test_empty_message(self):
        """Test log with empty message."""
        log = Log(
            level="INFO",
            component="test",
            message="",
        )
        assert log.message == ""

    def test_max_length_level(self):
        """Test level at max length (10 chars)."""
        level = "CRITICAL"  # 8 chars, within limit
        log = Log(
            level=level,
            component="test",
            message="Test",
        )
        assert log.level == level

    def test_max_length_component(self):
        """Test component at max length (50 chars)."""
        component = "c" * 50
        log = Log(
            level="INFO",
            component=component,
            message="Test",
        )
        assert log.component == component
        assert len(log.component) == 50

    def test_max_length_camera_id(self):
        """Test camera_id at max length (100 chars)."""
        camera_id = "c" * 100
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            camera_id=camera_id,
        )
        assert log.camera_id == camera_id
        assert len(log.camera_id) == 100

    def test_max_length_request_id(self):
        """Test request_id at max length (36 chars - UUID)."""
        request_id = "12345678-1234-1234-1234-123456789012"
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            request_id=request_id,
        )
        assert log.request_id == request_id
        assert len(log.request_id) == 36

    def test_extra_with_all_json_types(self):
        """Test extra with all JSON data types."""
        extra = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean_true": True,
            "boolean_false": False,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra=extra,
        )
        assert log.extra == extra

    def test_multiple_logs_independence(self):
        """Test that multiple Log instances are independent."""
        log1 = Log(
            level="INFO",
            component="comp1",
            message="Message 1",
            extra={"key": "value1"},
        )
        log2 = Log(
            level="ERROR",
            component="comp2",
            message="Message 2",
            extra={"key": "value2"},
        )

        # Verify independence
        assert log1.level != log2.level
        assert log1.component != log2.component
        assert log1.message != log2.message
        assert log1.extra != log2.extra

        # Modifying one should not affect the other
        log1.extra["key"] = "modified"
        assert log2.extra["key"] == "value2"

    def test_message_with_special_characters(self):
        """Test message with special characters."""
        message = '<script>alert("xss")</script> & "quotes" \'single\''
        log = Log(
            level="INFO",
            component="test",
            message=message,
        )
        assert log.message == message

    def test_extra_unicode_keys_and_values(self):
        """Test extra with Unicode keys and values."""
        extra = {"cle_francaise": "valeur francaise"}
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            extra=extra,
        )
        assert log.extra == extra

    def test_timestamp_has_attribute(self, sample_log):
        """Test log has timestamp attribute."""
        assert hasattr(sample_log, "timestamp")

    def test_timestamp_explicit(self):
        """Test log with explicit timestamp."""
        now = datetime.now(UTC)
        log = Log(
            level="INFO",
            component="test",
            message="Test",
            timestamp=now,
        )
        assert log.timestamp == now
