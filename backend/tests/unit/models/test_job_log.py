"""Unit tests for JobLog model.

Tests cover:
- JobLog model initialization and default values
- JobLog level handling (DEBUG, INFO, WARNING, ERROR)
- JobLog message and context storage
- JobLog timestamp handling
- String representation (__repr__)
- Model validation and constraints
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.job_log import JobLog, LogLevel

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid log levels
log_levels = st.sampled_from(["debug", "info", "warning", "error"])

# Strategy for log messages
log_messages = st.text(min_size=1, max_size=500)

# Strategy for attempt numbers (1+)
attempt_numbers = st.integers(min_value=1, max_value=10)


# =============================================================================
# JobLog Model Initialization Tests
# =============================================================================


class TestJobLogModelInitialization:
    """Tests for JobLog model initialization."""

    def test_job_log_creation_minimal(self):
        """Test creating a job log with minimal required fields."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            message="Job started",
        )

        assert log.job_id == job_id
        assert log.message == "Job started"
        # Note: Defaults apply at database level, not in-memory
        assert log.context is None

    def test_job_log_with_all_fields(self):
        """Test job log with all fields populated."""
        job_id = uuid4()
        log_id = uuid4()
        timestamp = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        context_data = {"worker_id": "worker-1", "duration_ms": 5000}

        log = JobLog(
            id=log_id,
            job_id=job_id,
            attempt_number=2,
            timestamp=timestamp,
            level=str(LogLevel.ERROR),
            message="Database connection failed",
            context=context_data,
        )

        assert log.id == log_id
        assert log.job_id == job_id
        assert log.attempt_number == 2
        assert log.timestamp == timestamp
        assert log.level == str(LogLevel.ERROR)
        assert log.message == "Database connection failed"
        assert log.context == context_data

    def test_job_log_default_column_definitions(self):
        """Test that job log columns have correct default definitions.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobLog)

        attempt_col = mapper.columns["attempt_number"]
        assert attempt_col.default is not None
        assert attempt_col.default.arg == 1

        timestamp_col = mapper.columns["timestamp"]
        assert timestamp_col.default is not None

        level_col = mapper.columns["level"]
        assert level_col.default is not None
        assert level_col.default.arg == str(LogLevel.INFO)

    def test_job_log_auto_generates_id(self):
        """Test that job log auto-generates UUID if not provided.

        Note: UUID defaults apply at database level, not in-memory.
        This would be tested in integration tests.
        """
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            message="Test message",
        )

        # In-memory model won't have UUID generated yet
        # This is verified in integration tests


# =============================================================================
# JobLog Level Tests
# =============================================================================


class TestJobLogLevel:
    """Tests for JobLog level values."""

    def test_job_log_debug_level(self):
        """Test job log with DEBUG level."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            level=str(LogLevel.DEBUG),
            message="Debug info",
        )

        assert log.level == str(LogLevel.DEBUG)

    def test_job_log_info_level(self):
        """Test job log with INFO level."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            level=str(LogLevel.INFO),
            message="Job processing",
        )

        assert log.level == str(LogLevel.INFO)

    def test_job_log_warning_level(self):
        """Test job log with WARNING level."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            level=str(LogLevel.WARNING),
            message="Slow query detected",
        )

        assert log.level == str(LogLevel.WARNING)

    def test_job_log_error_level(self):
        """Test job log with ERROR level."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            level=str(LogLevel.ERROR),
            message="Connection timeout",
        )

        assert log.level == str(LogLevel.ERROR)

    def test_job_log_default_level_column_definition(self):
        """Test that default log level column definition is INFO.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobLog)
        level_col = mapper.columns["level"]
        assert level_col.default is not None
        assert level_col.default.arg == str(LogLevel.INFO)


# =============================================================================
# JobLog Message Tests
# =============================================================================


class TestJobLogMessage:
    """Tests for JobLog message field."""

    def test_job_log_short_message(self):
        """Test job log with short message."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            message="Started",
        )

        assert log.message == "Started"

    def test_job_log_long_message(self):
        """Test job log with long message."""
        job_id = uuid4()
        long_message = "Processing batch of 10000 records from source database " * 10

        log = JobLog(
            job_id=job_id,
            message=long_message,
        )

        assert log.message == long_message

    def test_job_log_multiline_message(self):
        """Test job log with multiline message."""
        job_id = uuid4()
        multiline_message = """Step 1: Connect to database
Step 2: Fetch records
Step 3: Process data
Step 4: Write results"""

        log = JobLog(
            job_id=job_id,
            message=multiline_message,
        )

        assert log.message == multiline_message
        assert "\n" in log.message


# =============================================================================
# JobLog Context Tests
# =============================================================================


class TestJobLogContext:
    """Tests for JobLog context field."""

    def test_job_log_with_context_data(self):
        """Test job log with context JSON data."""
        job_id = uuid4()
        context = {
            "worker_id": "worker-123",
            "batch_size": 1000,
            "duration_ms": 5000,
            "memory_mb": 512,
        }

        log = JobLog(
            job_id=job_id,
            message="Batch processed",
            context=context,
        )

        assert log.context == context
        assert log.context["worker_id"] == "worker-123"
        assert log.context["batch_size"] == 1000

    def test_job_log_without_context(self):
        """Test job log without context data."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            message="Simple log entry",
        )

        assert log.context is None

    def test_job_log_with_nested_context(self):
        """Test job log with nested context structure."""
        job_id = uuid4()
        context = {
            "metrics": {
                "cpu_percent": 75.5,
                "memory_mb": 512,
            },
            "tags": ["production", "high-priority"],
            "metadata": {
                "version": "1.0.0",
                "region": "us-west",
            },
        }

        log = JobLog(
            job_id=job_id,
            message="Metrics collected",
            context=context,
        )

        assert log.context["metrics"]["cpu_percent"] == 75.5
        assert log.context["tags"] == ["production", "high-priority"]
        assert log.context["metadata"]["version"] == "1.0.0"


# =============================================================================
# JobLog Attempt Number Tests
# =============================================================================


class TestJobLogAttemptNumber:
    """Tests for JobLog attempt_number field."""

    def test_job_log_first_attempt(self):
        """Test log for first attempt."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            attempt_number=1,
            message="First attempt started",
        )

        assert log.attempt_number == 1

    def test_job_log_retry_attempts(self):
        """Test logs for retry attempts."""
        job_id = uuid4()

        log1 = JobLog(job_id=job_id, attempt_number=1, message="Attempt 1")
        log2 = JobLog(job_id=job_id, attempt_number=2, message="Attempt 2")
        log3 = JobLog(job_id=job_id, attempt_number=3, message="Attempt 3")

        assert log1.attempt_number == 1
        assert log2.attempt_number == 2
        assert log3.attempt_number == 3

    def test_job_log_default_attempt_number_column_definition(self):
        """Test default attempt_number column definition is 1.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobLog)
        attempt_col = mapper.columns["attempt_number"]
        assert attempt_col.default is not None
        assert attempt_col.default.arg == 1


# =============================================================================
# JobLog Timestamp Tests
# =============================================================================


class TestJobLogTimestamp:
    """Tests for JobLog timestamp field."""

    def test_job_log_timestamp_column_has_default(self):
        """Test that timestamp column has a default function.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobLog)
        timestamp_col = mapper.columns["timestamp"]
        assert timestamp_col.default is not None

    def test_job_log_timestamp_with_explicit_value(self):
        """Test job log with explicitly set timestamp."""
        job_id = uuid4()
        custom_timestamp = datetime(2025, 1, 15, 12, 30, 45, tzinfo=UTC)

        log = JobLog(
            job_id=job_id,
            timestamp=custom_timestamp,
            message="Test message",
        )

        assert log.timestamp == custom_timestamp


# =============================================================================
# JobLog Repr Tests
# =============================================================================


class TestJobLogRepr:
    """Tests for JobLog string representation."""

    def test_job_log_repr_contains_class_name(self):
        """Test repr contains class name."""
        job_id = uuid4()
        log = JobLog(job_id=job_id, message="Test")
        repr_str = repr(log)
        assert "JobLog" in repr_str

    def test_job_log_repr_contains_id(self):
        """Test repr contains log id."""
        job_id = uuid4()
        log = JobLog(job_id=job_id, message="Test")
        repr_str = repr(log)
        assert str(log.id) in repr_str

    def test_job_log_repr_contains_job_id(self):
        """Test repr contains job_id."""
        job_id = uuid4()
        log = JobLog(job_id=job_id, message="Test")
        repr_str = repr(log)
        assert str(job_id) in repr_str

    def test_job_log_repr_contains_level(self):
        """Test repr contains log level."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            level=str(LogLevel.ERROR),
            message="Error occurred",
        )
        repr_str = repr(log)
        assert "error" in repr_str

    def test_job_log_repr_truncates_long_message(self):
        """Test repr truncates long messages to 50 characters."""
        job_id = uuid4()
        long_message = "A" * 100

        log = JobLog(
            job_id=job_id,
            message=long_message,
        )

        repr_str = repr(log)
        # Should contain truncated message (50 chars) + "..."
        assert "AAAAA" in repr_str
        assert "..." in repr_str

    def test_job_log_repr_format(self):
        """Test repr has expected format."""
        job_id = uuid4()
        log = JobLog(job_id=job_id, message="Test")
        repr_str = repr(log)
        assert repr_str.startswith("<JobLog(")
        assert repr_str.endswith(")>")


# =============================================================================
# LogLevel Enum Tests
# =============================================================================


class TestLogLevelEnum:
    """Tests for LogLevel enum."""

    def test_log_level_values(self):
        """Test LogLevel enum has expected values."""
        assert LogLevel.DEBUG == "debug"
        assert LogLevel.INFO == "info"
        assert LogLevel.WARNING == "warning"
        assert LogLevel.ERROR == "error"

    def test_log_level_str(self):
        """Test LogLevel can be converted to string."""
        assert str(LogLevel.DEBUG) == "debug"
        assert str(LogLevel.INFO) == "info"
        assert str(LogLevel.WARNING) == "warning"
        assert str(LogLevel.ERROR) == "error"


# =============================================================================
# JobLog Table Args Tests
# =============================================================================


class TestJobLogTableArgs:
    """Tests for JobLog table arguments (indexes and constraints)."""

    def test_job_log_has_table_args(self):
        """Test JobLog model has __table_args__."""
        assert hasattr(JobLog, "__table_args__")

    def test_job_log_tablename(self):
        """Test JobLog has correct table name."""
        assert JobLog.__tablename__ == "job_logs"

    def test_job_log_indexes_defined(self):
        """Test JobLog has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(JobLog)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for composite indexes
        assert "idx_job_logs_job_attempt" in index_names
        assert "idx_job_logs_job_timestamp" in index_names

        # Check for level index
        assert "idx_job_logs_level" in index_names

    def test_job_log_brin_index(self):
        """Test JobLog has BRIN index for time-series queries."""
        from sqlalchemy import inspect

        mapper = inspect(JobLog)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "ix_job_logs_timestamp_brin" in index_names

        # Verify it uses BRIN
        for idx in table.indexes:
            if idx.name == "ix_job_logs_timestamp_brin":
                assert idx.dialect_options.get("postgresql", {}).get("using") == "brin"
                break

    def test_job_log_composite_indexes_columns(self):
        """Test composite indexes have correct columns."""
        from sqlalchemy import inspect

        mapper = inspect(JobLog)
        table = mapper.local_table

        for idx in table.indexes:
            if idx.name == "idx_job_logs_job_attempt":
                col_names = [col.name for col in idx.columns]
                assert col_names == ["job_id", "attempt_number"]
            elif idx.name == "idx_job_logs_job_timestamp":
                col_names = [col.name for col in idx.columns]
                assert col_names == ["job_id", "timestamp"]


# =============================================================================
# Property-based Tests
# =============================================================================


class TestJobLogProperties:
    """Property-based tests for JobLog model."""

    @given(level=log_levels)
    @settings(max_examples=20)
    def test_log_level_roundtrip(self, level: str):
        """Property: Log level values roundtrip correctly."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            level=level,
            message="Test message",
        )
        assert log.level == level

    @given(message=log_messages)
    @settings(max_examples=20)
    def test_message_roundtrip(self, message: str):
        """Property: Message values roundtrip correctly."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            message=message,
        )
        assert log.message == message

    @given(attempt_number=attempt_numbers)
    @settings(max_examples=20)
    def test_attempt_number_roundtrip(self, attempt_number: int):
        """Property: Attempt number values roundtrip correctly."""
        job_id = uuid4()
        log = JobLog(
            job_id=job_id,
            attempt_number=attempt_number,
            message="Test message",
        )
        assert log.attempt_number == attempt_number


# =============================================================================
# JobLog Use Case Tests
# =============================================================================


class TestJobLogUseCases:
    """Tests for common JobLog use cases."""

    def test_job_log_sequence_for_single_job(self):
        """Test creating sequence of logs for a single job."""
        job_id = uuid4()

        log1 = JobLog(job_id=job_id, level=str(LogLevel.INFO), message="Job started")
        log2 = JobLog(
            job_id=job_id,
            level=str(LogLevel.INFO),
            message="Processing batch 1",
            context={"batch_size": 1000},
        )
        log3 = JobLog(
            job_id=job_id,
            level=str(LogLevel.WARNING),
            message="Slow query detected",
        )
        log4 = JobLog(
            job_id=job_id,
            level=str(LogLevel.INFO),
            message="Job completed",
            context={"total_processed": 5000},
        )

        assert all(log.job_id == job_id for log in [log1, log2, log3, log4])
        assert log1.level == str(LogLevel.INFO)
        assert log3.level == str(LogLevel.WARNING)

    def test_job_log_error_with_context(self):
        """Test error log with diagnostic context."""
        job_id = uuid4()
        context = {
            "error_code": "DB_CONNECTION_TIMEOUT",
            "retry_count": 3,
            "last_successful_query": "SELECT COUNT(*) FROM events",
            "connection_pool_size": 10,
        }

        log = JobLog(
            job_id=job_id,
            level=str(LogLevel.ERROR),
            message="Database connection timeout after 30 seconds",
            context=context,
        )

        assert log.level == str(LogLevel.ERROR)
        assert log.context["error_code"] == "DB_CONNECTION_TIMEOUT"
        assert log.context["retry_count"] == 3

    def test_job_log_performance_metrics(self):
        """Test log with performance metrics in context."""
        job_id = uuid4()
        context = {
            "duration_ms": 5432,
            "records_processed": 10000,
            "throughput_records_per_sec": 1841,
            "memory_peak_mb": 512,
            "cpu_avg_percent": 75.5,
        }

        log = JobLog(
            job_id=job_id,
            level=str(LogLevel.INFO),
            message="Batch processing completed",
            context=context,
        )

        assert log.context["duration_ms"] == 5432
        assert log.context["throughput_records_per_sec"] == 1841
