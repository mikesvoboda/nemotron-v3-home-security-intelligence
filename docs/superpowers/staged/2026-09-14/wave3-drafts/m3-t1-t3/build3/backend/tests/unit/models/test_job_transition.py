"""Unit tests for JobTransition model.

Tests cover:
- JobTransition model initialization and default values
- JobTransition state tracking (from_status, to_status)
- JobTransition trigger types (WORKER, USER, TIMEOUT, RETRY, SYSTEM)
- JobTransition metadata handling
- JobTransition timestamp handling
- String representation (__repr__)
- Model validation and constraints
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.job_transition import JobTransition, JobTransitionTrigger

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid job statuses
job_statuses = st.sampled_from(["queued", "running", "completed", "failed", "cancelled"])

# Strategy for valid transition triggers
transition_triggers = st.sampled_from(["worker", "user", "timeout", "retry", "system"])


# =============================================================================
# JobTransition Model Initialization Tests
# =============================================================================


class TestJobTransitionModelInitialization:
    """Tests for JobTransition model initialization."""

    def test_job_transition_creation_minimal(self):
        """Test creating a job transition with minimal required fields."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )

        assert transition.job_id == job_id
        assert transition.from_status == "queued"
        assert transition.to_status == "running"
        # Note: Defaults apply at database level, not in-memory
        assert transition.metadata_json is None

    def test_job_transition_with_all_fields(self):
        """Test job transition with all fields populated."""
        job_id = str(uuid4())
        transition_id = uuid4()
        timestamp = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        metadata = '{"reason": "user_cancelled", "user_id": "admin"}'

        transition = JobTransition(
            id=transition_id,
            job_id=job_id,
            from_status="running",
            to_status="cancelled",
            transitioned_at=timestamp,
            triggered_by=str(JobTransitionTrigger.USER),
            metadata_json=metadata,
        )

        assert transition.id == transition_id
        assert transition.job_id == job_id
        assert transition.from_status == "running"
        assert transition.to_status == "cancelled"
        assert transition.transitioned_at == timestamp
        assert transition.triggered_by == str(JobTransitionTrigger.USER)
        assert transition.metadata_json == metadata

    def test_job_transition_default_column_definitions(self):
        """Test that job transition columns have correct default definitions.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobTransition)

        transitioned_at_col = mapper.columns["transitioned_at"]
        assert transitioned_at_col.default is not None

        triggered_by_col = mapper.columns["triggered_by"]
        assert triggered_by_col.default is not None
        assert triggered_by_col.default.arg == str(JobTransitionTrigger.WORKER)

    def test_job_transition_auto_generates_id(self):
        """Test that job transition auto-generates UUID if not provided.

        Note: UUID defaults apply at database level, not in-memory.
        This would be tested in integration tests.
        """
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )

        # In-memory model won't have UUID generated yet
        # This is verified in integration tests


# =============================================================================
# JobTransition State Tests
# =============================================================================


class TestJobTransitionStates:
    """Tests for JobTransition state tracking."""

    def test_job_transition_queued_to_running(self):
        """Test transition from queued to running."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )

        assert transition.from_status == "queued"
        assert transition.to_status == "running"

    def test_job_transition_running_to_completed(self):
        """Test transition from running to completed."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="completed",
        )

        assert transition.from_status == "running"
        assert transition.to_status == "completed"

    def test_job_transition_running_to_failed(self):
        """Test transition from running to failed."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="failed",
        )

        assert transition.from_status == "running"
        assert transition.to_status == "failed"

    def test_job_transition_queued_to_cancelled(self):
        """Test transition from queued to cancelled."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="cancelled",
        )

        assert transition.from_status == "queued"
        assert transition.to_status == "cancelled"

    def test_job_transition_failed_to_queued_retry(self):
        """Test transition from failed back to queued for retry."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="failed",
            to_status="queued",
            triggered_by=str(JobTransitionTrigger.RETRY),
        )

        assert transition.from_status == "failed"
        assert transition.to_status == "queued"
        assert transition.triggered_by == str(JobTransitionTrigger.RETRY)


# =============================================================================
# JobTransition Trigger Tests
# =============================================================================


class TestJobTransitionTriggers:
    """Tests for JobTransition trigger types."""

    def test_job_transition_worker_trigger(self):
        """Test transition triggered by worker."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
            triggered_by=str(JobTransitionTrigger.WORKER),
        )

        assert transition.triggered_by == str(JobTransitionTrigger.WORKER)

    def test_job_transition_user_trigger(self):
        """Test transition triggered by user action."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="cancelled",
            triggered_by=str(JobTransitionTrigger.USER),
        )

        assert transition.triggered_by == str(JobTransitionTrigger.USER)

    def test_job_transition_timeout_trigger(self):
        """Test transition triggered by timeout."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="failed",
            triggered_by=str(JobTransitionTrigger.TIMEOUT),
        )

        assert transition.triggered_by == str(JobTransitionTrigger.TIMEOUT)

    def test_job_transition_retry_trigger(self):
        """Test transition triggered by retry mechanism."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="failed",
            to_status="queued",
            triggered_by=str(JobTransitionTrigger.RETRY),
        )

        assert transition.triggered_by == str(JobTransitionTrigger.RETRY)

    def test_job_transition_system_trigger(self):
        """Test transition triggered by system action."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="failed",
            triggered_by=str(JobTransitionTrigger.SYSTEM),
        )

        assert transition.triggered_by == str(JobTransitionTrigger.SYSTEM)

    def test_job_transition_default_trigger_column_definition(self):
        """Test that default trigger column definition is WORKER.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobTransition)
        triggered_by_col = mapper.columns["triggered_by"]
        assert triggered_by_col.default is not None
        assert triggered_by_col.default.arg == str(JobTransitionTrigger.WORKER)


# =============================================================================
# JobTransition Metadata Tests
# =============================================================================


class TestJobTransitionMetadata:
    """Tests for JobTransition metadata handling."""

    def test_job_transition_with_metadata(self):
        """Test job transition with metadata."""
        job_id = str(uuid4())
        metadata = '{"reason": "user_requested", "user_id": "admin", "ip": "192.168.1.1"}'

        transition = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="cancelled",
            triggered_by=str(JobTransitionTrigger.USER),
            metadata_json=metadata,
        )

        assert transition.metadata_json == metadata
        assert "user_requested" in transition.metadata_json

    def test_job_transition_without_metadata(self):
        """Test job transition without metadata."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )

        assert transition.metadata_json is None

    def test_job_transition_timeout_metadata(self):
        """Test transition with timeout metadata."""
        job_id = str(uuid4())
        metadata = (
            '{"timeout_seconds": 300, "last_progress": 75, "stuck_at_step": "database_query"}'
        )

        transition = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="failed",
            triggered_by=str(JobTransitionTrigger.TIMEOUT),
            metadata_json=metadata,
        )

        assert transition.metadata_json == metadata
        assert "timeout_seconds" in transition.metadata_json

    def test_job_transition_retry_metadata(self):
        """Test transition with retry metadata."""
        job_id = str(uuid4())
        metadata = '{"attempt_number": 2, "max_attempts": 3, "retry_delay_seconds": 60}'

        transition = JobTransition(
            job_id=job_id,
            from_status="failed",
            to_status="queued",
            triggered_by=str(JobTransitionTrigger.RETRY),
            metadata_json=metadata,
        )

        assert transition.metadata_json == metadata
        assert "attempt_number" in transition.metadata_json


# =============================================================================
# JobTransition Timestamp Tests
# =============================================================================


class TestJobTransitionTimestamp:
    """Tests for JobTransition timestamp field."""

    def test_job_transition_timestamp_column_has_default(self):
        """Test that transitioned_at column has a default function.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        """
        from sqlalchemy import inspect

        mapper = inspect(JobTransition)
        timestamp_col = mapper.columns["transitioned_at"]
        assert timestamp_col.default is not None

    def test_job_transition_timestamp_with_explicit_value(self):
        """Test job transition with explicitly set timestamp."""
        job_id = str(uuid4())
        custom_timestamp = datetime(2025, 1, 15, 12, 30, 45, tzinfo=UTC)

        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
            transitioned_at=custom_timestamp,
        )

        assert transition.transitioned_at == custom_timestamp


# =============================================================================
# JobTransition Repr Tests
# =============================================================================


class TestJobTransitionRepr:
    """Tests for JobTransition string representation."""

    def test_job_transition_repr_contains_class_name(self):
        """Test repr contains class name."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )
        repr_str = repr(transition)
        assert "JobTransition" in repr_str

    def test_job_transition_repr_contains_id(self):
        """Test repr contains transition id."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )
        repr_str = repr(transition)
        assert str(transition.id) in repr_str

    def test_job_transition_repr_contains_job_id(self):
        """Test repr contains job_id."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )
        repr_str = repr(transition)
        assert job_id in repr_str

    def test_job_transition_repr_contains_from_status(self):
        """Test repr contains from_status."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )
        repr_str = repr(transition)
        assert "queued" in repr_str

    def test_job_transition_repr_contains_to_status(self):
        """Test repr contains to_status."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )
        repr_str = repr(transition)
        assert "running" in repr_str

    def test_job_transition_repr_shows_arrow(self):
        """Test repr shows arrow between states."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )
        repr_str = repr(transition)
        assert "->" in repr_str

    def test_job_transition_repr_format(self):
        """Test repr has expected format."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )
        repr_str = repr(transition)
        assert repr_str.startswith("<JobTransition(")
        assert repr_str.endswith(")>")


# =============================================================================
# JobTransitionTrigger Enum Tests
# =============================================================================


class TestJobTransitionTriggerEnum:
    """Tests for JobTransitionTrigger enum."""

    def test_job_transition_trigger_values(self):
        """Test JobTransitionTrigger enum has expected values."""
        assert JobTransitionTrigger.WORKER == "worker"
        assert JobTransitionTrigger.USER == "user"
        assert JobTransitionTrigger.TIMEOUT == "timeout"
        assert JobTransitionTrigger.RETRY == "retry"
        assert JobTransitionTrigger.SYSTEM == "system"

    def test_job_transition_trigger_str(self):
        """Test JobTransitionTrigger can be converted to string."""
        assert str(JobTransitionTrigger.WORKER) == "worker"
        assert str(JobTransitionTrigger.USER) == "user"
        assert str(JobTransitionTrigger.TIMEOUT) == "timeout"
        assert str(JobTransitionTrigger.RETRY) == "retry"
        assert str(JobTransitionTrigger.SYSTEM) == "system"


# =============================================================================
# JobTransition Table Args Tests
# =============================================================================


class TestJobTransitionTableArgs:
    """Tests for JobTransition table arguments (indexes)."""

    def test_job_transition_has_table_args(self):
        """Test JobTransition model has __table_args__."""
        assert hasattr(JobTransition, "__table_args__")

    def test_job_transition_tablename(self):
        """Test JobTransition has correct table name."""
        assert JobTransition.__tablename__ == "job_transitions"

    def test_job_transition_indexes_defined(self):
        """Test JobTransition has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(JobTransition)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for indexes
        assert "idx_job_transitions_job_id" in index_names
        assert "idx_job_transitions_transitioned_at" in index_names
        assert "idx_job_transitions_job_id_transitioned_at" in index_names

    def test_job_transition_composite_index_columns(self):
        """Test composite index has correct columns."""
        from sqlalchemy import inspect

        mapper = inspect(JobTransition)
        table = mapper.local_table

        for idx in table.indexes:
            if idx.name == "idx_job_transitions_job_id_transitioned_at":
                col_names = [col.name for col in idx.columns]
                assert col_names == ["job_id", "transitioned_at"]
                break


# =============================================================================
# Property-based Tests
# =============================================================================


class TestJobTransitionProperties:
    """Property-based tests for JobTransition model."""

    @given(from_status=job_statuses, to_status=job_statuses)
    @settings(max_examples=20)
    def test_status_transition_roundtrip(self, from_status: str, to_status: str):
        """Property: Status transition values roundtrip correctly."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status=from_status,
            to_status=to_status,
        )
        assert transition.from_status == from_status
        assert transition.to_status == to_status

    @given(trigger=transition_triggers)
    @settings(max_examples=20)
    def test_trigger_roundtrip(self, trigger: str):
        """Property: Trigger values roundtrip correctly."""
        job_id = str(uuid4())
        transition = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
            triggered_by=trigger,
        )
        assert transition.triggered_by == trigger


# =============================================================================
# JobTransition Use Case Tests
# =============================================================================


class TestJobTransitionUseCases:
    """Tests for common JobTransition use cases."""

    def test_job_transition_complete_lifecycle(self):
        """Test transitions for complete job lifecycle."""
        job_id = str(uuid4())

        # Transition 1: Queued -> Running
        t1 = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
            triggered_by=str(JobTransitionTrigger.WORKER),
        )

        # Transition 2: Running -> Completed
        t2 = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="completed",
            triggered_by=str(JobTransitionTrigger.WORKER),
        )

        assert t1.from_status == "queued"
        assert t1.to_status == "running"
        assert t2.from_status == "running"
        assert t2.to_status == "completed"
        assert t1.job_id == t2.job_id

    def test_job_transition_with_retry(self):
        """Test transitions for job with retry."""
        job_id = str(uuid4())

        # Transition 1: Queued -> Running
        t1 = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )

        # Transition 2: Running -> Failed
        t2 = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="failed",
            metadata_json='{"error": "Connection timeout"}',
        )

        # Transition 3: Failed -> Queued (retry)
        t3 = JobTransition(
            job_id=job_id,
            from_status="failed",
            to_status="queued",
            triggered_by=str(JobTransitionTrigger.RETRY),
            metadata_json='{"attempt_number": 2}',
        )

        # Transition 4: Queued -> Running (retry attempt)
        t4 = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )

        # Transition 5: Running -> Completed (successful retry)
        t5 = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="completed",
        )

        assert t2.to_status == "failed"
        assert t3.triggered_by == str(JobTransitionTrigger.RETRY)
        assert t5.to_status == "completed"

    def test_job_transition_user_cancellation(self):
        """Test transitions for user-cancelled job."""
        job_id = str(uuid4())

        # Transition 1: Queued -> Running
        t1 = JobTransition(
            job_id=job_id,
            from_status="queued",
            to_status="running",
        )

        # Transition 2: Running -> Cancelled (user action)
        t2 = JobTransition(
            job_id=job_id,
            from_status="running",
            to_status="cancelled",
            triggered_by=str(JobTransitionTrigger.USER),
            metadata_json='{"user_id": "admin", "reason": "no longer needed"}',
        )

        assert t2.triggered_by == str(JobTransitionTrigger.USER)
        assert t2.to_status == "cancelled"
        assert "user_id" in t2.metadata_json
