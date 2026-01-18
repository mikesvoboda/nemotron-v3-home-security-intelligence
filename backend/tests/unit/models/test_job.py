"""Unit tests for Job model.

Tests cover:
- Job model initialization and default values
- Job state transitions (queued -> running -> completed/failed/cancelled)
- Job progress tracking and updates
- Job retry logic and attempt handling
- Job properties (is_active, is_finished, can_retry, duration_seconds)
- Job methods (start, complete, fail, cancel, update_progress, prepare_retry)
- String representation (__repr__)
- Model validation and constraints
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.job import Job, JobStatus

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid job types
job_types = st.sampled_from(["export", "cleanup", "backup", "import", "analysis"])

# Strategy for valid priorities (0-4)
priorities = st.integers(min_value=0, max_value=4)

# Strategy for valid progress percentages (0-100)
progress_percentages = st.integers(min_value=0, max_value=100)

# Strategy for queue names
queue_names = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)


# =============================================================================
# Job Model Initialization Tests
# =============================================================================


class TestJobModelInitialization:
    """Tests for Job model initialization."""

    def test_job_creation_minimal(self):
        """Test creating a job with minimal required fields."""
        job = Job(
            id="test-job-1",
            job_type="export",
        )

        assert job.id == "test-job-1"
        assert job.job_type == "export"
        # Note: Defaults apply at database level, not in-memory
        # Test validates the column defaults are defined correctly below

    def test_job_with_all_fields(self):
        """Test job with all fields populated."""
        now = datetime.now(UTC)
        result_data = {"exported_rows": 1000, "file_path": "/data/exports/export.csv"}

        job = Job(
            id="test-job-2",
            job_type="cleanup",
            status=JobStatus.COMPLETED.value,
            queue_name="background",
            priority=1,
            created_at=now,
            started_at=now + timedelta(seconds=5),
            completed_at=now + timedelta(seconds=10),
            progress_percent=100,
            current_step="Completed",
            result=result_data,
            error_message=None,
            error_traceback=None,
            attempt_number=1,
            max_attempts=3,
            next_retry_at=None,
        )

        assert job.id == "test-job-2"
        assert job.job_type == "cleanup"
        assert job.status == JobStatus.COMPLETED.value
        assert job.queue_name == "background"
        assert job.priority == 1
        assert job.progress_percent == 100
        assert job.current_step == "Completed"
        assert job.result == result_data
        assert job.attempt_number == 1
        assert job.max_attempts == 3

    def test_job_default_column_definitions(self):
        """Test that job columns have correct default definitions.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column defaults are correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Job)

        status_col = mapper.columns["status"]
        assert status_col.default is not None
        assert status_col.default.arg == JobStatus.QUEUED.value

        priority_col = mapper.columns["priority"]
        assert priority_col.default is not None
        assert priority_col.default.arg == 2

        progress_col = mapper.columns["progress_percent"]
        assert progress_col.default is not None
        assert progress_col.default.arg == 0

        attempt_col = mapper.columns["attempt_number"]
        assert attempt_col.default is not None
        assert attempt_col.default.arg == 1

        max_attempts_col = mapper.columns["max_attempts"]
        assert max_attempts_col.default is not None
        assert max_attempts_col.default.arg == 3


# =============================================================================
# Job State Transition Tests
# =============================================================================


class TestJobStateTransitions:
    """Tests for Job state transitions."""

    def test_start_job(self):
        """Test starting a queued job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.QUEUED.value)
        assert job.started_at is None

        with patch("backend.models.job.datetime") as mock_dt:
            mock_now = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now

            job.start()

            assert job.status == JobStatus.RUNNING.value
            assert job.started_at == mock_now

    def test_complete_job(self):
        """Test completing a running job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)
        result_data = {"count": 500}

        with patch("backend.models.job.datetime") as mock_dt:
            mock_now = datetime(2025, 1, 15, 10, 5, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now

            job.complete(result=result_data)

            assert job.status == JobStatus.COMPLETED.value
            assert job.progress_percent == 100
            assert job.completed_at == mock_now
            assert job.current_step == "Completed"
            assert job.result == result_data

    def test_complete_job_without_result(self):
        """Test completing a job without result data."""
        job = Job(id="test-job", job_type="cleanup", status=JobStatus.RUNNING.value)

        job.complete()

        assert job.status == JobStatus.COMPLETED.value
        assert job.progress_percent == 100
        assert job.result is None

    def test_fail_job(self):
        """Test failing a running job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)
        error_msg = "Database connection failed"
        traceback = "Traceback (most recent call last):\n  ..."

        with patch("backend.models.job.datetime") as mock_dt:
            mock_now = datetime(2025, 1, 15, 10, 5, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now

            job.fail(error_message=error_msg, error_traceback=traceback)

            assert job.status == JobStatus.FAILED.value
            assert job.completed_at == mock_now
            assert job.error_message == error_msg
            assert job.error_traceback == traceback
            assert job.current_step.startswith("Failed:")

    def test_fail_job_truncates_long_error_in_step(self):
        """Test that fail() truncates long error messages in current_step."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)
        long_error = "A" * 100  # 100 character error message

        job.fail(error_message=long_error)

        assert job.error_message == long_error
        # "Failed: " (8 chars) + 50 chars + "..." (3 chars) = 61 chars total
        assert len(job.current_step) == 61
        assert job.current_step.endswith("...")

    def test_cancel_queued_job(self):
        """Test cancelling a queued job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.QUEUED.value)

        with patch("backend.models.job.datetime") as mock_dt:
            mock_now = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now

            job.cancel()

            assert job.status == JobStatus.CANCELLED.value
            assert job.completed_at == mock_now
            assert job.current_step == "Cancelled by user"
            assert job.error_message == "Job cancelled by user request"

    def test_cancel_running_job(self):
        """Test cancelling a running job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)

        job.cancel()

        assert job.status == JobStatus.CANCELLED.value
        assert job.error_message == "Job cancelled by user request"

    def test_cancel_completed_job_has_no_effect(self):
        """Test that cancelling a completed job has no effect."""
        job = Job(id="test-job", job_type="export", status=JobStatus.COMPLETED.value)

        job.cancel()

        # Job should remain completed (not active, so cancel has no effect)
        assert job.status == JobStatus.COMPLETED.value

    def test_cancel_failed_job_has_no_effect(self):
        """Test that cancelling a failed job has no effect."""
        job = Job(id="test-job", job_type="export", status=JobStatus.FAILED.value)

        job.cancel()

        assert job.status == JobStatus.FAILED.value


# =============================================================================
# Job Progress Tracking Tests
# =============================================================================


class TestJobProgressTracking:
    """Tests for Job progress tracking."""

    def test_update_progress(self):
        """Test updating job progress."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)

        job.update_progress(50, "Processing records...")

        assert job.progress_percent == 50
        assert job.current_step == "Processing records..."

    def test_update_progress_without_step(self):
        """Test updating progress without changing step."""
        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.RUNNING.value,
            current_step="Initial step",
        )

        job.update_progress(75)

        assert job.progress_percent == 75
        assert job.current_step == "Initial step"

    def test_update_progress_clamps_to_0_100(self):
        """Test that update_progress clamps values to 0-100 range."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)

        job.update_progress(-10)
        assert job.progress_percent == 0

        job.update_progress(150)
        assert job.progress_percent == 100

    def test_progress_percent_boundary_zero(self):
        """Test progress at 0%."""
        job = Job(id="test-job", job_type="export", progress_percent=0)
        assert job.progress_percent == 0

    def test_progress_percent_boundary_hundred(self):
        """Test progress at 100%."""
        job = Job(id="test-job", job_type="export", progress_percent=100)
        assert job.progress_percent == 100


# =============================================================================
# Job Retry Logic Tests
# =============================================================================


class TestJobRetryLogic:
    """Tests for Job retry logic."""

    def test_can_retry_failed_job_with_attempts_remaining(self):
        """Test that failed job can retry when attempts remain."""
        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.FAILED.value,
            attempt_number=1,
            max_attempts=3,
        )

        assert job.can_retry is True

    def test_cannot_retry_when_max_attempts_reached(self):
        """Test that job cannot retry when max attempts reached."""
        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.FAILED.value,
            attempt_number=3,
            max_attempts=3,
        )

        assert job.can_retry is False

    def test_cannot_retry_non_failed_job(self):
        """Test that non-failed jobs cannot retry."""
        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.QUEUED.value,
            attempt_number=1,
            max_attempts=3,
        )

        assert job.can_retry is False

    def test_prepare_retry(self):
        """Test preparing a failed job for retry."""
        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.FAILED.value,
            attempt_number=1,
            max_attempts=3,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            error_message="Network error",
            error_traceback="Traceback...",
            progress_percent=50,
            current_step="Failed step",
        )

        job.prepare_retry()

        assert job.attempt_number == 2
        assert job.status == JobStatus.QUEUED.value
        assert job.started_at is None
        assert job.completed_at is None
        assert job.error_message is None
        assert job.error_traceback is None
        assert job.progress_percent == 0
        assert job.current_step is None

    def test_prepare_retry_when_cannot_retry_has_no_effect(self):
        """Test that prepare_retry has no effect when can_retry is False."""
        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.FAILED.value,
            attempt_number=3,
            max_attempts=3,
        )

        original_attempt = job.attempt_number
        job.prepare_retry()

        # Should remain unchanged
        assert job.attempt_number == original_attempt
        assert job.status == JobStatus.FAILED.value


# =============================================================================
# Job Property Tests
# =============================================================================


class TestJobProperties:
    """Tests for Job properties."""

    def test_is_active_queued(self):
        """Test is_active returns True for queued job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.QUEUED.value)
        assert job.is_active is True

    def test_is_active_running(self):
        """Test is_active returns True for running job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)
        assert job.is_active is True

    def test_is_active_completed(self):
        """Test is_active returns False for completed job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.COMPLETED.value)
        assert job.is_active is False

    def test_is_active_failed(self):
        """Test is_active returns False for failed job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.FAILED.value)
        assert job.is_active is False

    def test_is_active_cancelled(self):
        """Test is_active returns False for cancelled job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.CANCELLED.value)
        assert job.is_active is False

    def test_is_finished_completed(self):
        """Test is_finished returns True for completed job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.COMPLETED.value)
        assert job.is_finished is True

    def test_is_finished_failed(self):
        """Test is_finished returns True for failed job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.FAILED.value)
        assert job.is_finished is True

    def test_is_finished_cancelled(self):
        """Test is_finished returns True for cancelled job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.CANCELLED.value)
        assert job.is_finished is True

    def test_is_finished_queued(self):
        """Test is_finished returns False for queued job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.QUEUED.value)
        assert job.is_finished is False

    def test_is_finished_running(self):
        """Test is_finished returns False for running job."""
        job = Job(id="test-job", job_type="export", status=JobStatus.RUNNING.value)
        assert job.is_finished is False

    def test_duration_seconds_with_timestamps(self):
        """Test duration calculation with both timestamps set."""
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 15, 10, 5, 30, tzinfo=UTC)

        job = Job(
            id="test-job",
            job_type="export",
            started_at=started,
            completed_at=completed,
        )

        assert job.duration_seconds == 330.0  # 5 minutes 30 seconds

    def test_duration_seconds_without_started_at(self):
        """Test duration returns None when started_at is None."""
        job = Job(
            id="test-job",
            job_type="export",
            started_at=None,
            completed_at=datetime.now(UTC),
        )

        assert job.duration_seconds is None

    def test_duration_seconds_without_completed_at(self):
        """Test duration returns None when completed_at is None."""
        job = Job(
            id="test-job",
            job_type="export",
            started_at=datetime.now(UTC),
            completed_at=None,
        )

        assert job.duration_seconds is None

    def test_duration_seconds_without_any_timestamps(self):
        """Test duration returns None when both timestamps are None."""
        job = Job(
            id="test-job",
            job_type="export",
            started_at=None,
            completed_at=None,
        )

        assert job.duration_seconds is None


# =============================================================================
# Job Repr Tests
# =============================================================================


class TestJobRepr:
    """Tests for Job string representation."""

    def test_job_repr_contains_class_name(self):
        """Test repr contains class name."""
        job = Job(id="test-job-1", job_type="export")
        repr_str = repr(job)
        assert "Job" in repr_str

    def test_job_repr_contains_id(self):
        """Test repr contains job id."""
        job = Job(id="test-job-1", job_type="export")
        repr_str = repr(job)
        assert "test-job-1" in repr_str

    def test_job_repr_contains_job_type(self):
        """Test repr contains job_type."""
        job = Job(id="test-job-1", job_type="export")
        repr_str = repr(job)
        assert "export" in repr_str

    def test_job_repr_contains_status(self):
        """Test repr contains status."""
        job = Job(id="test-job-1", job_type="export", status=JobStatus.RUNNING.value)
        repr_str = repr(job)
        assert "running" in repr_str

    def test_job_repr_contains_progress(self):
        """Test repr contains progress percentage."""
        job = Job(id="test-job-1", job_type="export", progress_percent=75)
        repr_str = repr(job)
        assert "75" in repr_str
        assert "%" in repr_str

    def test_job_repr_format(self):
        """Test repr has expected format."""
        job = Job(id="test-job-1", job_type="export")
        repr_str = repr(job)
        assert repr_str.startswith("<Job(")
        assert repr_str.endswith(")>")


# =============================================================================
# Job Status Enum Tests
# =============================================================================


class TestJobStatusEnum:
    """Tests for JobStatus enum."""

    def test_job_status_values(self):
        """Test JobStatus enum has expected values."""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_job_status_str(self):
        """Test JobStatus __str__ returns value."""
        assert str(JobStatus.QUEUED) == "queued"
        assert str(JobStatus.RUNNING) == "running"
        assert str(JobStatus.COMPLETED) == "completed"
        assert str(JobStatus.FAILED) == "failed"
        assert str(JobStatus.CANCELLED) == "cancelled"


# =============================================================================
# Job Table Args Tests
# =============================================================================


class TestJobTableArgs:
    """Tests for Job table arguments (indexes and constraints)."""

    def test_job_has_table_args(self):
        """Test Job model has __table_args__."""
        assert hasattr(Job, "__table_args__")

    def test_job_tablename(self):
        """Test Job has correct table name."""
        assert Job.__tablename__ == "jobs"

    def test_job_indexes_defined(self):
        """Test Job has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(Job)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for single-column indexes
        assert "idx_jobs_status" in index_names
        assert "idx_jobs_job_type" in index_names
        assert "idx_jobs_created_at" in index_names
        assert "idx_jobs_queue_name" in index_names
        assert "idx_jobs_priority" in index_names

        # Check for composite indexes
        assert "idx_jobs_status_created_at" in index_names
        assert "idx_jobs_job_type_status" in index_names

    def test_job_brin_index(self):
        """Test Job has BRIN index for time-series queries."""
        from sqlalchemy import inspect

        mapper = inspect(Job)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "ix_jobs_created_at_brin" in index_names

        # Verify it uses BRIN
        for idx in table.indexes:
            if idx.name == "ix_jobs_created_at_brin":
                assert idx.dialect_options.get("postgresql", {}).get("using") == "brin"
                break


# =============================================================================
# Property-based Tests
# =============================================================================


class TestJobPropertiesHypothesis:
    """Property-based tests for Job model using Hypothesis."""

    @given(job_type=job_types, priority=priorities)
    @settings(max_examples=20)
    def test_job_type_and_priority_roundtrip(self, job_type: str, priority: int):
        """Property: Job type and priority values roundtrip correctly."""
        job = Job(
            id="test-job",
            job_type=job_type,
            priority=priority,
        )
        assert job.job_type == job_type
        assert job.priority == priority

    @given(progress=progress_percentages)
    @settings(max_examples=20)
    def test_progress_percent_roundtrip(self, progress: int):
        """Property: Progress percentage values roundtrip correctly."""
        job = Job(
            id="test-job",
            job_type="export",
            progress_percent=progress,
        )
        assert job.progress_percent == progress

    @given(queue_name=queue_names)
    @settings(max_examples=20)
    def test_queue_name_roundtrip(self, queue_name: str):
        """Property: Queue name values roundtrip correctly."""
        job = Job(
            id="test-job",
            job_type="export",
            queue_name=queue_name,
        )
        assert job.queue_name == queue_name

    @given(
        attempt_number=st.integers(min_value=1, max_value=10),
        max_attempts=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=20)
    def test_attempt_numbers_roundtrip(self, attempt_number: int, max_attempts: int):
        """Property: Attempt numbers roundtrip correctly."""
        job = Job(
            id="test-job",
            job_type="export",
            attempt_number=attempt_number,
            max_attempts=max_attempts,
        )
        assert job.attempt_number == attempt_number
        assert job.max_attempts == max_attempts


# =============================================================================
# Job Metadata and Payload Tests
# =============================================================================


class TestJobMetadataAndPayload:
    """Tests for Job result metadata and error handling."""

    def test_job_result_json_storage(self):
        """Test that job result can store complex JSON data."""
        result_data = {
            "status": "success",
            "records_processed": 1500,
            "files": ["export1.csv", "export2.csv"],
            "metadata": {"duration_ms": 5000, "format": "csv"},
        }

        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.COMPLETED.value,
            result=result_data,
        )

        assert job.result == result_data
        assert job.result["records_processed"] == 1500
        assert job.result["files"] == ["export1.csv", "export2.csv"]

    def test_job_error_message_storage(self):
        """Test that job can store error messages."""
        error_msg = "Database connection timeout after 30 seconds"

        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.FAILED.value,
            error_message=error_msg,
        )

        assert job.error_message == error_msg

    def test_job_error_traceback_storage(self):
        """Test that job can store full error tracebacks."""
        traceback = """Traceback (most recent call last):
  File "export.py", line 42, in run
    data = fetch_data()
  File "database.py", line 15, in fetch_data
    conn = connect()
TimeoutError: Connection timeout
"""

        job = Job(
            id="test-job",
            job_type="export",
            status=JobStatus.FAILED.value,
            error_traceback=traceback,
        )

        assert job.error_traceback == traceback
        assert "TimeoutError" in job.error_traceback


# =============================================================================
# Job Priority Tests
# =============================================================================


class TestJobPriority:
    """Tests for Job priority handling."""

    def test_job_priority_highest(self):
        """Test job with highest priority (0)."""
        job = Job(id="test-job", job_type="export", priority=0)
        assert job.priority == 0

    def test_job_priority_lowest(self):
        """Test job with lowest priority (4)."""
        job = Job(id="test-job", job_type="export", priority=4)
        assert job.priority == 4

    def test_job_priority_default_column_definition(self):
        """Test job default priority column definition is 2 (medium).

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Job)
        priority_col = mapper.columns["priority"]
        assert priority_col.default is not None
        assert priority_col.default.arg == 2


# =============================================================================
# Job Timestamp Tests
# =============================================================================


class TestJobTimestamps:
    """Tests for Job timestamp fields."""

    def test_job_created_at_column_has_default(self):
        """Test that created_at column has a default function.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Job)
        created_at_col = mapper.columns["created_at"]
        assert created_at_col.default is not None

    def test_job_started_at_initially_none(self):
        """Test that started_at is None for new jobs."""
        job = Job(id="test-job", job_type="export")
        assert job.started_at is None

    def test_job_completed_at_initially_none(self):
        """Test that completed_at is None for new jobs."""
        job = Job(id="test-job", job_type="export")
        assert job.completed_at is None

    def test_job_next_retry_at_initially_none(self):
        """Test that next_retry_at is None for new jobs."""
        job = Job(id="test-job", job_type="export")
        assert job.next_retry_at is None
