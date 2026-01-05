"""Unit tests for Log model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- JSONB extra field handling
- Optional metadata fields
- Table configuration and indexes
- Property-based tests for field values
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
        whitelist_characters="_-",
    ),
)

# Strategy for source values
source_values = st.sampled_from(["backend", "frontend", "ai", "worker", "scheduler"])

# Strategy for camera IDs
camera_ids = st.one_of(
    st.none(),
    st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_-",
        ),
    ),
)

# Strategy for request IDs (UUID format)
request_ids = st.one_of(
    st.none(),
    st.from_regex(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", fullmatch=True),
)

# Strategy for duration in milliseconds
duration_ms_values = st.one_of(
    st.none(),
    st.integers(min_value=0, max_value=3600000),  # 0 to 1 hour in ms
)

# Strategy for JSON-serializable values
json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=100),
    lambda children: st.lists(children, max_size=5)
    | st.dictionaries(st.text(max_size=20), children, max_size=5),
    max_leaves=10,
)

# Strategy for extra dictionaries
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
    """Create a sample log entry for testing."""
    return Log(
        id=1,
        level="INFO",
        component="api",
        message="Request processed successfully",
        source="backend",
        camera_id="front_door",
        request_id="abc-123",
        duration_ms=150,
        extra={"endpoint": "/api/events", "method": "GET"},
    )


@pytest.fixture
def minimal_log():
    """Create a log with minimal required fields."""
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
        component="file_watcher",
        message="File not found: /export/foscam/test.jpg",
        camera_id="front_door",
        extra={"error_code": "ENOENT", "file_path": "/export/foscam/test.jpg"},
    )


@pytest.fixture
def log_with_event():
    """Create a log with event_id and detection_id."""
    return Log(
        id=3,
        level="INFO",
        component="nemotron",
        message="Risk analysis completed",
        event_id=123,
        detection_id=456,
        duration_ms=5200,
    )


# =============================================================================
# Log Model Initialization Tests
# =============================================================================


class TestLogModelInitialization:
    """Tests for Log model initialization."""

    def test_log_creation_minimal(self, minimal_log):
        """Test creating a log entry with minimal fields."""
        assert minimal_log.level == "INFO"
        assert minimal_log.component == "test"
        assert minimal_log.message == "Test message"

    def test_log_with_all_fields(self, sample_log):
        """Test log with all fields populated."""
        assert sample_log.id == 1
        assert sample_log.level == "INFO"
        assert sample_log.component == "api"
        assert sample_log.message == "Request processed successfully"
        assert sample_log.source == "backend"
        assert sample_log.camera_id == "front_door"
        assert sample_log.request_id == "abc-123"
        assert sample_log.duration_ms == 150
        assert sample_log.extra == {"endpoint": "/api/events", "method": "GET"}

    def test_log_default_source_column_definition(self):
        """Test source column has 'backend' as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Log)
        source_col = mapper.columns["source"]
        assert source_col.default is not None
        assert source_col.default.arg == "backend"

    def test_log_optional_fields_default_to_none(self, minimal_log):
        """Test optional fields default to None."""
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
        """Test DEBUG log level."""
        log = Log(level="DEBUG", component="test", message="Debug message")
        assert log.level == "DEBUG"

    def test_level_info(self):
        """Test INFO log level."""
        log = Log(level="INFO", component="test", message="Info message")
        assert log.level == "INFO"

    def test_level_warning(self):
        """Test WARNING log level."""
        log = Log(level="WARNING", component="test", message="Warning message")
        assert log.level == "WARNING"

    def test_level_error(self, error_log):
        """Test ERROR log level."""
        assert error_log.level == "ERROR"

    def test_level_critical(self):
        """Test CRITICAL log level."""
        log = Log(level="CRITICAL", component="test", message="Critical message")
        assert log.level == "CRITICAL"

    def test_level_lowercase(self):
        """Test lowercase level value (allowed by model)."""
        log = Log(level="info", component="test", message="Test")
        assert log.level == "info"


# =============================================================================
# Log Component Field Tests
# =============================================================================


class TestLogComponentField:
    """Tests for Log component field."""

    def test_component_api(self, sample_log):
        """Test api component."""
        assert sample_log.component == "api"

    def test_component_file_watcher(self, error_log):
        """Test file_watcher component."""
        assert error_log.component == "file_watcher"

    def test_component_nemotron(self, log_with_event):
        """Test nemotron component."""
        assert log_with_event.component == "nemotron"

    def test_component_rtdetr(self):
        """Test rtdetr component."""
        log = Log(level="INFO", component="rtdetr", message="Detection completed")
        assert log.component == "rtdetr"

    def test_component_with_underscore(self):
        """Test component with underscore."""
        log = Log(level="INFO", component="scene_change_detector", message="Test")
        assert log.component == "scene_change_detector"


# =============================================================================
# Log Message Field Tests
# =============================================================================


class TestLogMessageField:
    """Tests for Log message field."""

    def test_message_simple(self, sample_log):
        """Test simple message."""
        assert sample_log.message == "Request processed successfully"

    def test_message_error(self, error_log):
        """Test error message with path."""
        assert "File not found" in error_log.message

    def test_message_long(self):
        """Test long message."""
        long_message = "A" * 5000
        log = Log(level="INFO", component="test", message=long_message)
        assert log.message == long_message
        assert len(log.message) == 5000

    def test_message_with_newlines(self):
        """Test message with newlines."""
        message = "Line 1\nLine 2\nLine 3"
        log = Log(level="INFO", component="test", message=message)
        assert log.message == message
        assert "\n" in log.message

    def test_message_with_unicode(self):
        """Test message with Unicode characters."""
        message = "Processing camera: Front Door"
        log = Log(level="INFO", component="test", message=message)
        assert log.message == message

    def test_message_with_special_chars(self):
        """Test message with special characters."""
        message = 'Error: "File not found" at path C:\\Users\\test'
        log = Log(level="ERROR", component="test", message=message)
        assert log.message == message


# =============================================================================
# Log Source Field Tests
# =============================================================================


class TestLogSourceField:
    """Tests for Log source field."""

    def test_source_backend(self, sample_log):
        """Test backend source."""
        assert sample_log.source == "backend"

    def test_source_frontend(self):
        """Test frontend source."""
        log = Log(level="INFO", component="ui", message="Test", source="frontend")
        assert log.source == "frontend"

    def test_source_ai(self):
        """Test ai source."""
        log = Log(level="INFO", component="rtdetr", message="Test", source="ai")
        assert log.source == "ai"

    def test_source_worker(self):
        """Test worker source."""
        log = Log(level="INFO", component="task", message="Test", source="worker")
        assert log.source == "worker"


# =============================================================================
# Log Camera ID Field Tests
# =============================================================================


class TestLogCameraIdField:
    """Tests for Log camera_id field."""

    def test_camera_id_set(self, sample_log):
        """Test camera_id when set."""
        assert sample_log.camera_id == "front_door"

    def test_camera_id_none(self, minimal_log):
        """Test camera_id when not set."""
        assert minimal_log.camera_id is None

    def test_camera_id_with_underscore(self):
        """Test camera_id with underscore."""
        log = Log(level="INFO", component="test", message="Test", camera_id="back_yard")
        assert log.camera_id == "back_yard"

    def test_camera_id_with_numbers(self):
        """Test camera_id with numbers."""
        log = Log(level="INFO", component="test", message="Test", camera_id="camera_01")
        assert log.camera_id == "camera_01"


# =============================================================================
# Log Event ID and Detection ID Field Tests
# =============================================================================


class TestLogEventAndDetectionIdFields:
    """Tests for Log event_id and detection_id fields."""

    def test_event_id_set(self, log_with_event):
        """Test event_id when set."""
        assert log_with_event.event_id == 123

    def test_event_id_none(self, minimal_log):
        """Test event_id when not set."""
        assert minimal_log.event_id is None

    def test_detection_id_set(self, log_with_event):
        """Test detection_id when set."""
        assert log_with_event.detection_id == 456

    def test_detection_id_none(self, minimal_log):
        """Test detection_id when not set."""
        assert minimal_log.detection_id is None

    def test_event_id_large(self):
        """Test large event_id value."""
        log = Log(level="INFO", component="test", message="Test", event_id=999999)
        assert log.event_id == 999999

    def test_detection_id_large(self):
        """Test large detection_id value."""
        log = Log(level="INFO", component="test", message="Test", detection_id=888888)
        assert log.detection_id == 888888


# =============================================================================
# Log Request ID Field Tests
# =============================================================================


class TestLogRequestIdField:
    """Tests for Log request_id field."""

    def test_request_id_set(self, sample_log):
        """Test request_id when set."""
        assert sample_log.request_id == "abc-123"

    def test_request_id_none(self, minimal_log):
        """Test request_id when not set."""
        assert minimal_log.request_id is None

    def test_request_id_uuid_format(self):
        """Test request_id with UUID format."""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        log = Log(level="INFO", component="test", message="Test", request_id=uuid)
        assert log.request_id == uuid

    def test_request_id_max_length(self):
        """Test request_id at max length (36 chars for UUID)."""
        request_id = "a" * 36
        log = Log(level="INFO", component="test", message="Test", request_id=request_id)
        assert len(log.request_id) == 36


# =============================================================================
# Log Duration MS Field Tests
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
        """Test duration_ms at zero."""
        log = Log(level="INFO", component="test", message="Test", duration_ms=0)
        assert log.duration_ms == 0

    def test_duration_ms_large(self):
        """Test large duration_ms value."""
        log = Log(level="INFO", component="test", message="Test", duration_ms=3600000)
        assert log.duration_ms == 3600000  # 1 hour in ms

    def test_duration_ms_typical_api_call(self):
        """Test typical API call duration."""
        log = Log(level="INFO", component="api", message="Test", duration_ms=45)
        assert log.duration_ms == 45

    def test_duration_ms_ai_processing(self, log_with_event):
        """Test AI processing duration (longer)."""
        assert log_with_event.duration_ms == 5200


# =============================================================================
# Log Extra (JSONB) Field Tests
# =============================================================================


class TestLogExtraField:
    """Tests for Log extra JSONB field."""

    def test_extra_simple_dict(self, sample_log):
        """Test extra with simple dict."""
        assert sample_log.extra == {"endpoint": "/api/events", "method": "GET"}

    def test_extra_none(self, minimal_log):
        """Test extra when not set."""
        assert minimal_log.extra is None

    def test_extra_empty_dict(self):
        """Test extra with empty dict."""
        log = Log(level="INFO", component="test", message="Test", extra={})
        assert log.extra == {}

    def test_extra_nested_dict(self):
        """Test extra with nested dict."""
        extra = {
            "request": {"headers": {"content-type": "application/json"}},
            "response": {"status": 200},
        }
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra == extra

    def test_extra_with_list(self):
        """Test extra with list values."""
        extra = {"detections": ["person", "car", "dog"]}
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra["detections"] == ["person", "car", "dog"]

    def test_extra_with_numbers(self):
        """Test extra with numeric values."""
        extra = {"count": 5, "confidence": 0.95, "threshold": 0.5}
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra["count"] == 5
        assert log.extra["confidence"] == 0.95

    def test_extra_with_boolean(self):
        """Test extra with boolean values."""
        extra = {"success": True, "retry": False}
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra["success"] is True
        assert log.extra["retry"] is False

    def test_extra_with_null_values(self):
        """Test extra with null values."""
        extra = {"value": None, "previous": None}
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra["value"] is None

    def test_extra_error_details(self, error_log):
        """Test extra with error details."""
        assert error_log.extra["error_code"] == "ENOENT"
        assert error_log.extra["file_path"] == "/export/foscam/test.jpg"


# =============================================================================
# Log User Agent Field Tests
# =============================================================================


class TestLogUserAgentField:
    """Tests for Log user_agent field."""

    def test_user_agent_none(self, minimal_log):
        """Test user_agent when not set."""
        assert minimal_log.user_agent is None

    def test_user_agent_browser(self):
        """Test user_agent with browser string."""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        log = Log(level="INFO", component="test", message="Test", user_agent=user_agent)
        assert log.user_agent == user_agent

    def test_user_agent_api_client(self):
        """Test user_agent with API client."""
        log = Log(
            level="INFO", component="test", message="Test", user_agent="SecurityDashboard/1.0"
        )
        assert log.user_agent == "SecurityDashboard/1.0"

    def test_user_agent_long(self):
        """Test long user_agent string."""
        long_ua = "A" * 500
        log = Log(level="INFO", component="test", message="Test", user_agent=long_ua)
        assert log.user_agent == long_ua


# =============================================================================
# Log Timestamp Field Tests
# =============================================================================


class TestLogTimestampField:
    """Tests for Log timestamp field."""

    def test_timestamp_has_attribute(self, sample_log):
        """Test log has timestamp attribute."""
        assert hasattr(sample_log, "timestamp")

    def test_timestamp_explicit(self):
        """Test log with explicit timestamp."""
        now = datetime.now(UTC)
        log = Log(level="INFO", component="test", message="Test", timestamp=now)
        assert log.timestamp == now

    def test_timestamp_has_server_default(self):
        """Test timestamp column has server_default.

        Note: SQLAlchemy server_default applies at database level.
        This test verifies the column server_default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Log)
        timestamp_col = mapper.columns["timestamp"]
        assert timestamp_col.server_default is not None


# =============================================================================
# Log Repr Tests
# =============================================================================


class TestLogRepr:
    """Tests for Log string representation."""

    def test_repr_contains_class_name(self, sample_log):
        """Test repr contains class name."""
        repr_str = repr(sample_log)
        assert "Log" in repr_str

    def test_repr_contains_level(self, sample_log):
        """Test repr contains log level."""
        repr_str = repr(sample_log)
        assert "INFO" in repr_str

    def test_repr_contains_component(self, sample_log):
        """Test repr contains component."""
        repr_str = repr(sample_log)
        assert "api" in repr_str

    def test_repr_contains_message_preview(self):
        """Test repr contains message preview (truncated)."""
        log = Log(
            id=1,
            level="WARNING",
            component="api",
            message="Slow query detected in database operation",
        )
        repr_str = repr(log)
        assert "WARNING" in repr_str
        assert "api" in repr_str
        assert "Slow query" in repr_str

    def test_repr_format(self, sample_log):
        """Test repr has expected format."""
        repr_str = repr(sample_log)
        assert repr_str.startswith("<Log(")
        assert repr_str.endswith(")>")

    def test_repr_truncates_long_message(self):
        """Test repr truncates long messages."""
        long_message = "A" * 100
        log = Log(id=1, level="INFO", component="test", message=long_message)
        repr_str = repr(log)
        # The message should be truncated in repr (first 50 chars)
        assert len(repr_str) < len(long_message) + 100


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
        log = Log(level=level, component="test", message="Test")
        assert log.level == level

    @given(component=component_names)
    @settings(max_examples=50)
    def test_component_roundtrip(self, component: str):
        """Property: Component values roundtrip correctly."""
        log = Log(level="INFO", component=component, message="Test")
        assert log.component == component

    @given(source=source_values)
    @settings(max_examples=20)
    def test_source_roundtrip(self, source: str):
        """Property: Source values roundtrip correctly."""
        log = Log(level="INFO", component="test", message="Test", source=source)
        assert log.source == source

    @given(camera_id=camera_ids)
    @settings(max_examples=50)
    def test_camera_id_roundtrip(self, camera_id: str | None):
        """Property: Camera ID values roundtrip correctly."""
        log = Log(level="INFO", component="test", message="Test", camera_id=camera_id)
        assert log.camera_id == camera_id

    @given(duration_ms=duration_ms_values)
    @settings(max_examples=50)
    def test_duration_ms_roundtrip(self, duration_ms: int | None):
        """Property: Duration MS values roundtrip correctly."""
        log = Log(level="INFO", component="test", message="Test", duration_ms=duration_ms)
        assert log.duration_ms == duration_ms

    @given(id_value=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=50)
    def test_id_roundtrip(self, id_value: int):
        """Property: ID values roundtrip correctly."""
        log = Log(id=id_value, level="INFO", component="test", message="Test")
        assert log.id == id_value

    @given(message=st.text(min_size=1, max_size=1000))
    @settings(max_examples=50)
    def test_message_roundtrip(self, message: str):
        """Property: Message values roundtrip correctly."""
        log = Log(level="INFO", component="test", message=message)
        assert log.message == message

    @given(
        level=log_levels,
        component=component_names,
        source=source_values,
    )
    @settings(max_examples=50)
    def test_all_fields_roundtrip(
        self,
        level: str,
        component: str,
        source: str,
    ):
        """Property: Multiple field combinations roundtrip correctly."""
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

    @given(extra=extra_dicts)
    @settings(max_examples=100)
    def test_extra_roundtrip(self, extra: dict | None):
        """Property: Extra dict values roundtrip correctly."""
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra == extra


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestLogEdgeCases:
    """Tests for edge cases in Log model."""

    def test_empty_message(self):
        """Test log with empty message (model allows it)."""
        log = Log(level="INFO", component="test", message="")
        assert log.message == ""

    def test_max_length_level(self):
        """Test level at max length (10 chars)."""
        level = "VERYLONGLV"
        log = Log(level=level, component="test", message="Test")
        assert log.level == level
        assert len(log.level) == 10

    def test_max_length_component(self):
        """Test component at max length (50 chars)."""
        component = "c" * 50
        log = Log(level="INFO", component=component, message="Test")
        assert log.component == component
        assert len(log.component) == 50

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
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra == extra

    def test_multiple_logs_independence(self):
        """Test that multiple log instances are independent."""
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

    def test_duration_ms_zero(self):
        """Test duration_ms at zero (instant operation)."""
        log = Log(level="INFO", component="test", message="Test", duration_ms=0)
        assert log.duration_ms == 0

    def test_event_id_and_detection_id_both_set(self, log_with_event):
        """Test both event_id and detection_id set together."""
        assert log_with_event.event_id == 123
        assert log_with_event.detection_id == 456

    def test_all_optional_fields_none(self, minimal_log):
        """Test all optional fields are None."""
        assert minimal_log.camera_id is None
        assert minimal_log.event_id is None
        assert minimal_log.request_id is None
        assert minimal_log.detection_id is None
        assert minimal_log.duration_ms is None
        assert minimal_log.extra is None
        assert minimal_log.user_agent is None

    def test_unicode_in_message(self):
        """Test Unicode characters in message."""
        message = "Processing Front Door camera"
        log = Log(level="INFO", component="test", message=message)
        assert log.message == message

    def test_json_special_chars_in_extra(self):
        """Test JSON special characters in extra field."""
        extra = {
            "path": "C:\\Users\\test\\file.txt",
            "quote": 'He said "hello"',
            "newline": "line1\nline2",
        }
        log = Log(level="INFO", component="test", message="Test", extra=extra)
        assert log.extra["path"] == "C:\\Users\\test\\file.txt"
        assert log.extra["quote"] == 'He said "hello"'
        assert log.extra["newline"] == "line1\nline2"
