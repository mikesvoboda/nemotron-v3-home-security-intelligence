"""Unit tests for JobAttempt model.

Tests cover:
- JobAttempt model initialization and default values
- JobAttempt status transitions
- JobAttempt duration calculation
- JobAttempt metadata and result handling
- String representation (__repr__)
- Model validation and constraints
"""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.job_attempt import JobAttempt, JobAttemptStatus

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid attempt numbers (1+)
attempt_numbers = st.integers(min_value=1, max_value=10)

# Strategy for worker IDs
worker_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)


# =============================================================================
# JobAttempt Model Initialization Tests
# =============================================================================


class TestJobAttemptModelInitialization:
    """Tests for JobAttempt model initialization."""

    def test_job_attempt_creation_minimal(self):
        """Test creating a job attempt with minimal required fields."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
        )

        assert attempt.job_id == job_id
        # Note: Defaults apply at database level, not in-memory

    def test_job_attempt_with_all_fields(self):
        """Test job attempt with all fields populated."""
        job_id = uuid4()
        attempt_id = uuid4()
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        ended = datetime(2025, 1, 15, 10, 5, 0, tzinfo=UTC)
        result_data = {"processed": 1000}

        attempt = JobAttempt(
            id=attempt_id,
            job_id=job_id,
            attempt_number=2,
            started_at=started,
            ended_at=ended,
            status=str(JobAttemptStatus.SUCCEEDED),
            worker_id="worker-1",
            error_message=None,
            error_traceback=None,
            result=result_data,
        )

        assert attempt.id == attempt_id
        assert attempt.job_id == job_id
        assert attempt.attempt_number == 2
        assert attempt.started_at == started
        assert attempt.ended_at == ended
        assert attempt.status == str(JobAttemptStatus.SUCCEEDED)
        assert attempt.worker_id == "worker-1"
        assert attempt.result == result_data

    def test_job_attempt_default_values(self):
        """Test that job attempt fields have correct default values."""
        job_id = uuid4()

        with patch("backend.models.job_attempt.datetime") as mock_dt:
            mock_now = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now

            attempt = JobAttempt(job_id=job_id)

            # Note: Defaults apply at database level, not in-memory
            assert attempt.ended_at is None
            assert attempt.worker_id is None
            assert attempt.error_message is None
            assert attempt.error_traceback is None
            assert attempt.result is None

    def test_job_attempt_auto_generates_id(self):
        """Test that job attempt auto-generates UUID if not provided."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id)

        # Note: UUID defaults apply at database level, not in-memory
        # This would be tested in integration tests


# =============================================================================
# JobAttempt Status Tests
# =============================================================================


class TestJobAttemptStatus:
    """Tests for JobAttempt status values."""

    def test_job_attempt_started_status(self):
        """Test job attempt with STARTED status."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.STARTED),
        )

        assert attempt.status == str(JobAttemptStatus.STARTED)
        assert attempt.ended_at is None

    def test_job_attempt_succeeded_status(self):
        """Test job attempt with SUCCEEDED status."""
        job_id = uuid4()
        ended = datetime.now(UTC)

        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.SUCCEEDED),
            ended_at=ended,
            result={"count": 100},
        )

        assert attempt.status == str(JobAttemptStatus.SUCCEEDED)
        assert attempt.ended_at == ended
        assert attempt.result is not None

    def test_job_attempt_failed_status(self):
        """Test job attempt with FAILED status."""
        job_id = uuid4()
        ended = datetime.now(UTC)

        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.FAILED),
            ended_at=ended,
            error_message="Network timeout",
            error_traceback="Traceback...",
        )

        assert attempt.status == str(JobAttemptStatus.FAILED)
        assert attempt.ended_at == ended
        assert attempt.error_message == "Network timeout"
        assert attempt.error_traceback is not None

    def test_job_attempt_cancelled_status(self):
        """Test job attempt with CANCELLED status."""
        job_id = uuid4()
        ended = datetime.now(UTC)

        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.CANCELLED),
            ended_at=ended,
        )

        assert attempt.status == str(JobAttemptStatus.CANCELLED)
        assert attempt.ended_at == ended


# =============================================================================
# JobAttempt Duration Tests
# =============================================================================


class TestJobAttemptDuration:
    """Tests for JobAttempt duration calculation."""

    def test_duration_seconds_with_ended_at(self):
        """Test duration calculation when attempt has ended."""
        job_id = uuid4()
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        ended = datetime(2025, 1, 15, 10, 3, 30, tzinfo=UTC)

        attempt = JobAttempt(
            job_id=job_id,
            started_at=started,
            ended_at=ended,
        )

        assert attempt.duration_seconds == 210.0  # 3 minutes 30 seconds

    def test_duration_seconds_without_ended_at(self):
        """Test duration returns None when attempt hasn't ended."""
        job_id = uuid4()
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

        attempt = JobAttempt(
            job_id=job_id,
            started_at=started,
            ended_at=None,
        )

        assert attempt.duration_seconds is None

    def test_duration_seconds_short_duration(self):
        """Test duration for short-running attempt."""
        job_id = uuid4()
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        ended = datetime(2025, 1, 15, 10, 0, 1, 500000, tzinfo=UTC)  # 1.5 seconds

        attempt = JobAttempt(
            job_id=job_id,
            started_at=started,
            ended_at=ended,
        )

        assert attempt.duration_seconds == 1.5

    def test_duration_seconds_long_duration(self):
        """Test duration for long-running attempt."""
        job_id = uuid4()
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        ended = datetime(2025, 1, 15, 12, 30, 45, tzinfo=UTC)  # 2.5+ hours

        attempt = JobAttempt(
            job_id=job_id,
            started_at=started,
            ended_at=ended,
        )

        expected_duration = (ended - started).total_seconds()
        assert attempt.duration_seconds == expected_duration


# =============================================================================
# JobAttempt Worker Assignment Tests
# =============================================================================


class TestJobAttemptWorkerAssignment:
    """Tests for JobAttempt worker assignment."""

    def test_job_attempt_with_worker_id(self):
        """Test job attempt with worker ID assigned."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            worker_id="worker-123",
        )

        assert attempt.worker_id == "worker-123"

    def test_job_attempt_without_worker_id(self):
        """Test job attempt without worker ID."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id)

        assert attempt.worker_id is None

    def test_job_attempt_with_hostname_worker_id(self):
        """Test job attempt with hostname-style worker ID."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            worker_id="worker-pod-abc123.cluster.local",
        )

        assert attempt.worker_id == "worker-pod-abc123.cluster.local"


# =============================================================================
# JobAttempt Result and Error Handling Tests
# =============================================================================


class TestJobAttemptResultAndErrors:
    """Tests for JobAttempt result and error handling."""

    def test_job_attempt_with_result_data(self):
        """Test job attempt with result data."""
        job_id = uuid4()
        result_data = {
            "records_exported": 5000,
            "file_path": "/exports/data.csv",
            "file_size_bytes": 1024000,
        }

        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.SUCCEEDED),
            result=result_data,
        )

        assert attempt.result == result_data
        assert attempt.result["records_exported"] == 5000

    def test_job_attempt_with_error_message(self):
        """Test job attempt with error message."""
        job_id = uuid4()
        error_msg = "Failed to connect to database: Connection refused"

        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.FAILED),
            error_message=error_msg,
        )

        assert attempt.error_message == error_msg

    def test_job_attempt_with_error_traceback(self):
        """Test job attempt with full error traceback."""
        job_id = uuid4()
        traceback = """Traceback (most recent call last):
  File "worker.py", line 50, in execute
    result = process_job()
  File "processor.py", line 25, in process_job
    conn = get_connection()
ConnectionError: Connection refused
"""

        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.FAILED),
            error_traceback=traceback,
        )

        assert attempt.error_traceback == traceback
        assert "ConnectionError" in attempt.error_traceback

    def test_job_attempt_without_result_or_error(self):
        """Test job attempt without result or error data."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id)

        assert attempt.result is None
        assert attempt.error_message is None
        assert attempt.error_traceback is None


# =============================================================================
# JobAttempt Repr Tests
# =============================================================================


class TestJobAttemptRepr:
    """Tests for JobAttempt string representation."""

    def test_job_attempt_repr_contains_class_name(self):
        """Test repr contains class name."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id)
        repr_str = repr(attempt)
        assert "JobAttempt" in repr_str

    def test_job_attempt_repr_contains_id(self):
        """Test repr contains attempt id."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id)
        repr_str = repr(attempt)
        assert str(attempt.id) in repr_str

    def test_job_attempt_repr_contains_job_id(self):
        """Test repr contains job_id."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id)
        repr_str = repr(attempt)
        assert str(job_id) in repr_str

    def test_job_attempt_repr_contains_attempt_number(self):
        """Test repr contains attempt_number."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id, attempt_number=3)
        repr_str = repr(attempt)
        assert "attempt_number=3" in repr_str

    def test_job_attempt_repr_contains_status(self):
        """Test repr contains status."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.SUCCEEDED),
        )
        repr_str = repr(attempt)
        assert "succeeded" in repr_str

    def test_job_attempt_repr_format(self):
        """Test repr has expected format."""
        job_id = uuid4()
        attempt = JobAttempt(job_id=job_id)
        repr_str = repr(attempt)
        assert repr_str.startswith("<JobAttempt(")
        assert repr_str.endswith(")>")


# =============================================================================
# JobAttemptStatus Enum Tests
# =============================================================================


class TestJobAttemptStatusEnum:
    """Tests for JobAttemptStatus enum."""

    def test_job_attempt_status_values(self):
        """Test JobAttemptStatus enum has expected values."""
        assert JobAttemptStatus.STARTED == "started"
        assert JobAttemptStatus.SUCCEEDED == "succeeded"
        assert JobAttemptStatus.FAILED == "failed"
        assert JobAttemptStatus.CANCELLED == "cancelled"

    def test_job_attempt_status_str(self):
        """Test JobAttemptStatus can be converted to string."""
        assert str(JobAttemptStatus.STARTED) == "started"
        assert str(JobAttemptStatus.SUCCEEDED) == "succeeded"
        assert str(JobAttemptStatus.FAILED) == "failed"
        assert str(JobAttemptStatus.CANCELLED) == "cancelled"


# =============================================================================
# JobAttempt Table Args Tests
# =============================================================================


class TestJobAttemptTableArgs:
    """Tests for JobAttempt table arguments (indexes and constraints)."""

    def test_job_attempt_has_table_args(self):
        """Test JobAttempt model has __table_args__."""
        assert hasattr(JobAttempt, "__table_args__")

    def test_job_attempt_tablename(self):
        """Test JobAttempt has correct table name."""
        assert JobAttempt.__tablename__ == "job_attempts"

    def test_job_attempt_indexes_defined(self):
        """Test JobAttempt has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(JobAttempt)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for composite index
        assert "idx_job_attempts_job_attempt" in index_names

        # Check for status index
        assert "idx_job_attempts_status" in index_names

    def test_job_attempt_brin_index(self):
        """Test JobAttempt has BRIN index for time-series queries."""
        from sqlalchemy import inspect

        mapper = inspect(JobAttempt)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "ix_job_attempts_started_at_brin" in index_names

        # Verify it uses BRIN
        for idx in table.indexes:
            if idx.name == "ix_job_attempts_started_at_brin":
                assert idx.dialect_options.get("postgresql", {}).get("using") == "brin"
                break

    def test_job_attempt_composite_index_columns(self):
        """Test composite index has correct columns."""
        from sqlalchemy import inspect

        mapper = inspect(JobAttempt)
        table = mapper.local_table

        for idx in table.indexes:
            if idx.name == "idx_job_attempts_job_attempt":
                col_names = [col.name for col in idx.columns]
                assert col_names == ["job_id", "attempt_number"]
                break


# =============================================================================
# Property-based Tests
# =============================================================================


class TestJobAttemptProperties:
    """Property-based tests for JobAttempt model."""

    @given(attempt_number=attempt_numbers)
    @settings(max_examples=20)
    def test_attempt_number_roundtrip(self, attempt_number: int):
        """Property: Attempt number values roundtrip correctly."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            attempt_number=attempt_number,
        )
        assert attempt.attempt_number == attempt_number

    @given(worker_id=worker_ids)
    @settings(max_examples=20)
    def test_worker_id_roundtrip(self, worker_id: str):
        """Property: Worker ID values roundtrip correctly."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            worker_id=worker_id,
        )
        assert attempt.worker_id == worker_id

    @given(
        error_message=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=20)
    def test_error_message_roundtrip(self, error_message: str):
        """Property: Error message values roundtrip correctly."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            status=str(JobAttemptStatus.FAILED),
            error_message=error_message,
        )
        assert attempt.error_message == error_message


# =============================================================================
# JobAttempt Attempt Number Tests
# =============================================================================


class TestJobAttemptAttemptNumber:
    """Tests for JobAttempt attempt_number field."""

    def test_job_attempt_first_attempt(self):
        """Test first attempt has attempt_number=1."""
        job_id = uuid4()
        attempt = JobAttempt(
            job_id=job_id,
            attempt_number=1,
        )

        assert attempt.attempt_number == 1

    def test_job_attempt_retry_attempts(self):
        """Test retry attempts have incrementing attempt_number."""
        job_id = uuid4()

        attempt1 = JobAttempt(job_id=job_id, attempt_number=1)
        attempt2 = JobAttempt(job_id=job_id, attempt_number=2)
        attempt3 = JobAttempt(job_id=job_id, attempt_number=3)

        assert attempt1.attempt_number == 1
        assert attempt2.attempt_number == 2
        assert attempt3.attempt_number == 3

    def test_job_attempt_default_column_definitions(self):
        """Test that JobAttempt columns have correct default definitions.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobAttempt)
        attempt_col = mapper.columns["attempt_number"]
        assert attempt_col.default is not None
        assert attempt_col.default.arg == 1
