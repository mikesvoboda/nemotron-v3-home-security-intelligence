"""Integration tests for job state transitions.

These tests verify the JobStateService works correctly with a real PostgreSQL database,
including transition history recording and concurrent transition safety.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import InvalidStateTransition
from backend.models.job_transition import JobTransition, JobTransitionTrigger
from backend.services.job_state_service import (
    JobData,
    JobStateService,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestJobLifecycleIntegration:
    """Integration tests for full job lifecycle transitions."""

    async def test_complete_job_lifecycle_queued_to_completed(
        self, db_session: AsyncSession
    ) -> None:
        """Test a job going through queued -> running -> completed lifecycle."""
        service = JobStateService(db=db_session)

        # Create a new job
        job = service.create_job("export", metadata={"format": "csv"})
        assert job.status == "queued"
        assert job.started_at is None
        assert job.completed_at is None

        # Transition to running
        job = await service.transition(job, "running")
        assert job.status == "running"
        assert job.started_at is not None
        assert job.completed_at is None

        # Transition to completed
        job = await service.transition(job, "completed")
        assert job.status == "completed"
        assert job.completed_at is not None

        # Verify transitions were recorded
        await db_session.commit()
        history = await service.get_transition_history(job.id)
        assert len(history) == 2

        # First transition: queued -> running
        assert history[0].from_status == "queued"
        assert history[0].to_status == "running"

        # Second transition: running -> completed
        assert history[1].from_status == "running"
        assert history[1].to_status == "completed"

    async def test_job_lifecycle_with_failure_and_retry(self, db_session: AsyncSession) -> None:
        """Test a job going through queued -> running -> failed -> queued (retry)."""
        service = JobStateService(db=db_session)

        job = service.create_job("backup")

        # Start job
        job = await service.transition(job, "running")
        assert job.status == "running"

        # Fail the job
        job = await service.transition(job, "failed", error_message="Database connection lost")
        assert job.status == "failed"
        assert job.error == "Database connection lost"
        assert job.completed_at is not None

        # Retry the job
        job = await service.transition(job, "queued", triggered_by=str(JobTransitionTrigger.RETRY))
        assert job.status == "queued"

        await db_session.commit()

        # Verify all transitions recorded
        history = await service.get_transition_history(job.id)
        assert len(history) == 3

    async def test_job_cancellation_from_queued(self, db_session: AsyncSession) -> None:
        """Test job cancellation from queued state."""
        service = JobStateService(db=db_session)

        job = service.create_job("cleanup")
        job = await service.transition(
            job, "cancelled", triggered_by=str(JobTransitionTrigger.USER)
        )

        assert job.status == "cancelled"
        assert job.completed_at is not None

        await db_session.commit()

        history = await service.get_transition_history(job.id)
        assert len(history) == 1
        assert history[0].triggered_by == str(JobTransitionTrigger.USER)


class TestAbortingStateTransitions:
    """Tests for the aborting -> aborted/failed state transitions."""

    async def test_running_to_aborting_to_aborted(self, db_session: AsyncSession) -> None:
        """Test running -> aborting -> aborted transition chain."""
        service = JobStateService(db=db_session)

        job = service.create_job("long_export")

        # Start job
        job = await service.transition(job, "running")
        assert job.status == "running"

        # Request abort
        job = await service.transition(job, "aborting", triggered_by=str(JobTransitionTrigger.USER))
        assert job.status == "aborting"

        # Complete abort
        job = await service.transition(job, "aborted")
        assert job.status == "aborted"
        assert job.completed_at is not None

        await db_session.commit()

    async def test_aborting_to_failed_when_abort_fails(self, db_session: AsyncSession) -> None:
        """Test aborting -> failed when the abort operation itself fails."""
        service = JobStateService(db=db_session)

        job = service.create_job("resource_intensive_job")

        job = await service.transition(job, "running")
        job = await service.transition(job, "aborting", triggered_by=str(JobTransitionTrigger.USER))

        # Abort operation fails
        job = await service.transition(
            job, "failed", error_message="Unable to release resources during abort"
        )
        assert job.status == "failed"
        assert job.error == "Unable to release resources during abort"

        await db_session.commit()


class TestInvalidStateTransitionsIntegration:
    """Integration tests for invalid state transition rejection."""

    async def test_invalid_completed_to_running_rejected(self, db_session: AsyncSession) -> None:
        """Completed jobs cannot transition to running."""
        service = JobStateService(db=db_session)

        job = service.create_job("export")
        job = await service.transition(job, "running")
        job = await service.transition(job, "completed")

        # Attempt invalid transition
        with pytest.raises(InvalidStateTransition) as exc_info:
            await service.transition(job, "running")

        assert exc_info.value.from_status == "completed"
        assert exc_info.value.to_status == "running"
        assert exc_info.value.job_id == job.id

    async def test_invalid_cancelled_to_running_rejected(self, db_session: AsyncSession) -> None:
        """Cancelled jobs cannot transition to running."""
        service = JobStateService(db=db_session)

        job = service.create_job("export")
        job = await service.transition(job, "cancelled")

        with pytest.raises(InvalidStateTransition) as exc_info:
            await service.transition(job, "running")

        assert exc_info.value.from_status == "cancelled"
        assert exc_info.value.to_status == "running"

    async def test_invalid_aborted_to_queued_rejected(self, db_session: AsyncSession) -> None:
        """Aborted jobs cannot be retried (cannot transition to queued)."""
        service = JobStateService(db=db_session)

        job = service.create_job("export")
        job = await service.transition(job, "running")
        job = await service.transition(job, "aborting")
        job = await service.transition(job, "aborted")

        with pytest.raises(InvalidStateTransition) as exc_info:
            await service.transition(job, "queued")

        assert exc_info.value.from_status == "aborted"
        assert exc_info.value.to_status == "queued"

    async def test_invalid_queued_to_completed_rejected(self, db_session: AsyncSession) -> None:
        """Queued jobs cannot skip to completed."""
        service = JobStateService(db=db_session)

        job = service.create_job("export")

        with pytest.raises(InvalidStateTransition) as exc_info:
            await service.transition(job, "completed")

        assert exc_info.value.from_status == "queued"
        assert exc_info.value.to_status == "completed"


class TestTransitionHistoryIntegration:
    """Integration tests for transition history recording."""

    async def test_transition_history_recorded_correctly(self, db_session: AsyncSession) -> None:
        """Verify transition history is recorded with correct data."""
        service = JobStateService(db=db_session)

        job = service.create_job("export")

        # Perform transitions
        job = await service.transition(
            job,
            "running",
            triggered_by=str(JobTransitionTrigger.WORKER),
            metadata={"worker_id": "worker-1"},
        )
        job = await service.transition(
            job,
            "completed",
            triggered_by=str(JobTransitionTrigger.WORKER),
            metadata={"items_processed": 100},
        )

        await db_session.commit()

        # Query history
        history = await service.get_transition_history(job.id)

        assert len(history) == 2

        # First transition
        assert history[0].job_id == job.id
        assert history[0].from_status == "queued"
        assert history[0].to_status == "running"
        assert history[0].triggered_by == str(JobTransitionTrigger.WORKER)
        assert history[0].transitioned_at is not None
        assert "worker_id" in history[0].metadata_json

        # Second transition
        assert history[1].from_status == "running"
        assert history[1].to_status == "completed"
        assert "items_processed" in history[1].metadata_json

    async def test_transition_history_limit(self, db_session: AsyncSession) -> None:
        """Test that history query respects limit parameter."""
        service = JobStateService(db=db_session)

        job = service.create_job("multi_step_job")

        # Create multiple transitions
        job = await service.transition(job, "running")
        job = await service.transition(job, "failed", error_message="Error 1")
        job = await service.transition(job, "queued", triggered_by=str(JobTransitionTrigger.RETRY))
        job = await service.transition(job, "running")
        job = await service.transition(job, "completed")

        await db_session.commit()

        # Get limited history
        limited_history = await service.get_transition_history(job.id, limit=2)
        assert len(limited_history) == 2

        # Full history
        full_history = await service.get_transition_history(job.id)
        assert len(full_history) == 5


class TestConcurrentTransitionSafety:
    """Tests for concurrent transition safety."""

    async def test_sequential_transitions_on_different_jobs(self, db_session: AsyncSession) -> None:
        """Multiple jobs can be transitioned sequentially without interference.

        Note: SQLAlchemy async sessions don't support concurrent operations
        within a single session. This test verifies sequential transitions work.
        """
        service = JobStateService(db=db_session)

        # Create multiple jobs
        jobs = [service.create_job(f"job_{i}") for i in range(5)]
        results = []

        # Transition all jobs to running sequentially
        for job in jobs:
            result = await service.transition(job, "running")
            results.append(result)

        # All jobs should be running
        assert all(job.status == "running" for job in results)

        await db_session.commit()

        # Verify each job has its transition recorded
        for job in results:
            history = await service.get_transition_history(job.id)
            assert len(history) == 1
            assert history[0].to_status == "running"

    async def test_transition_records_persist_after_commit(self, db_session: AsyncSession) -> None:
        """Transition records are persisted correctly after commit."""
        service = JobStateService(db=db_session)

        job = service.create_job("persistence_test")
        job_id = job.id

        job = await service.transition(job, "running")
        job = await service.transition(job, "completed")

        await db_session.commit()

        # Query directly from database
        stmt = select(JobTransition).where(JobTransition.job_id == job_id)
        result = await db_session.execute(stmt)
        transitions = list(result.scalars().all())

        assert len(transitions) == 2
        assert transitions[0].from_status == "queued"
        assert transitions[0].to_status == "running"
        assert transitions[1].from_status == "running"
        assert transitions[1].to_status == "completed"


class TestAllValidTransitions:
    """Tests that verify all valid transitions from the state machine."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("queued", "running"),
            ("queued", "cancelled"),
            ("running", "completed"),
            ("running", "failed"),
            ("running", "aborting"),
            ("aborting", "aborted"),
            ("aborting", "failed"),
            ("failed", "queued"),
        ],
    )
    async def test_valid_transition(
        self, db_session: AsyncSession, from_status: str, to_status: str
    ) -> None:
        """Test each valid state transition defined in the state machine."""
        service = JobStateService(db=db_session)

        # Create a job and set it to the starting state
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="test",
            status=from_status,
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC) if from_status != "queued" else None,
            completed_at=(datetime.now(UTC) if from_status in ("failed", "completed") else None),
        )

        # Transition should succeed
        result = await service.transition(job, to_status)
        assert result.status == to_status

        await db_session.commit()


class TestTerminalStateEnforcement:
    """Tests that verify terminal states cannot have further transitions."""

    @pytest.mark.parametrize("terminal_state", ["completed", "cancelled", "aborted"])
    async def test_terminal_state_blocks_all_transitions(
        self, db_session: AsyncSession, terminal_state: str
    ) -> None:
        """Terminal states should reject all transition attempts."""
        service = JobStateService(db=db_session)

        # Create a job in terminal state
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="test",
            status=terminal_state,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        # Try all possible target states
        for target_status in ["queued", "running", "completed", "failed", "cancelled"]:
            if target_status == terminal_state:
                continue  # Skip same-state transition

            with pytest.raises(InvalidStateTransition):
                await service.transition(job, target_status)


class TestTransitionTriggers:
    """Tests for different transition trigger types."""

    @pytest.mark.parametrize(
        "trigger",
        [
            JobTransitionTrigger.WORKER,
            JobTransitionTrigger.USER,
            JobTransitionTrigger.TIMEOUT,
            JobTransitionTrigger.RETRY,
            JobTransitionTrigger.SYSTEM,
        ],
    )
    async def test_all_trigger_types_recorded(
        self, db_session: AsyncSession, trigger: JobTransitionTrigger
    ) -> None:
        """All trigger types are correctly recorded in transition history."""
        service = JobStateService(db=db_session)

        job = service.create_job("trigger_test")
        job = await service.transition(job, "running", triggered_by=str(trigger))

        await db_session.commit()

        history = await service.get_transition_history(job.id)
        assert len(history) == 1
        assert history[0].triggered_by == str(trigger)


class TestTransitionMetadata:
    """Tests for transition metadata recording."""

    async def test_complex_metadata_recorded(self, db_session: AsyncSession) -> None:
        """Complex metadata structures are correctly recorded."""
        service = JobStateService(db=db_session)

        job = service.create_job("metadata_test")

        complex_metadata = {
            "worker_id": "worker-1",
            "processing_time_ms": 1234,
            "items": ["item1", "item2"],
            "stats": {"processed": 100, "failed": 0},
            "nested": {"level1": {"level2": "value"}},
        }

        job = await service.transition(job, "running", metadata=complex_metadata)

        await db_session.commit()

        history = await service.get_transition_history(job.id)
        assert len(history) == 1

        import json

        recorded_metadata = json.loads(history[0].metadata_json)
        assert recorded_metadata == complex_metadata

    async def test_empty_metadata_handled(self, db_session: AsyncSession) -> None:
        """Transitions without metadata are recorded correctly."""
        service = JobStateService(db=db_session)

        job = service.create_job("no_metadata_test")
        job = await service.transition(job, "running")

        await db_session.commit()

        history = await service.get_transition_history(job.id)
        assert len(history) == 1
        assert history[0].metadata_json is None
