"""Tests for the job state transition service.

This module tests the JobStateService which provides state machine validation
for job lifecycle transitions, including transition history recording.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.exceptions import InvalidStateTransition
from backend.models.job_transition import JobTransition, JobTransitionTrigger
from backend.services.job_state_service import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    JobData,
    JobState,
    JobStateService,
    get_valid_target_states,
    validate_transition,
)


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def job_state_service(mock_db: AsyncMock) -> JobStateService:
    """Create a job state service with mock database."""
    return JobStateService(db=mock_db)


@pytest.fixture
def queued_job() -> JobData:
    """Create a job in queued state."""
    return JobData(
        id=str(uuid.uuid4()),
        job_type="export",
        status="queued",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def running_job() -> JobData:
    """Create a job in running state."""
    return JobData(
        id=str(uuid.uuid4()),
        job_type="export",
        status="running",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
    )


@pytest.fixture
def failed_job() -> JobData:
    """Create a job in failed state."""
    return JobData(
        id=str(uuid.uuid4()),
        job_type="export",
        status="failed",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        error="Test error",
    )


@pytest.fixture
def aborting_job() -> JobData:
    """Create a job in aborting state."""
    return JobData(
        id=str(uuid.uuid4()),
        job_type="export",
        status="aborting",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
    )


class TestJobState:
    """Tests for JobState enum."""

    def test_state_values(self) -> None:
        """Should have expected state values."""
        assert JobState.QUEUED == "queued"
        assert JobState.RUNNING == "running"
        assert JobState.COMPLETED == "completed"
        assert JobState.FAILED == "failed"
        assert JobState.CANCELLED == "cancelled"
        assert JobState.ABORTING == "aborting"
        assert JobState.ABORTED == "aborted"

    def test_all_states_exist(self) -> None:
        """Should have all required states."""
        states = [s.value for s in JobState]
        assert "queued" in states
        assert "running" in states
        assert "completed" in states
        assert "failed" in states
        assert "cancelled" in states
        assert "aborting" in states
        assert "aborted" in states


class TestValidTransitions:
    """Tests for VALID_TRANSITIONS state machine definition."""

    def test_queued_transitions(self) -> None:
        """Queued jobs can transition to running or cancelled."""
        assert "running" in VALID_TRANSITIONS["queued"]
        assert "cancelled" in VALID_TRANSITIONS["queued"]
        assert len(VALID_TRANSITIONS["queued"]) == 2

    def test_running_transitions(self) -> None:
        """Running jobs can transition to completed, failed, or aborting."""
        assert "completed" in VALID_TRANSITIONS["running"]
        assert "failed" in VALID_TRANSITIONS["running"]
        assert "aborting" in VALID_TRANSITIONS["running"]
        assert len(VALID_TRANSITIONS["running"]) == 3

    def test_aborting_transitions(self) -> None:
        """Aborting jobs can transition to aborted or failed."""
        assert "aborted" in VALID_TRANSITIONS["aborting"]
        assert "failed" in VALID_TRANSITIONS["aborting"]
        assert len(VALID_TRANSITIONS["aborting"]) == 2

    def test_failed_can_retry(self) -> None:
        """Failed jobs can transition back to queued for retry."""
        assert "queued" in VALID_TRANSITIONS["failed"]
        assert len(VALID_TRANSITIONS["failed"]) == 1

    def test_completed_is_terminal(self) -> None:
        """Completed is a terminal state with no transitions."""
        assert VALID_TRANSITIONS["completed"] == []

    def test_cancelled_is_terminal(self) -> None:
        """Cancelled is a terminal state with no transitions."""
        assert VALID_TRANSITIONS["cancelled"] == []

    def test_aborted_is_terminal(self) -> None:
        """Aborted is a terminal state with no transitions."""
        assert VALID_TRANSITIONS["aborted"] == []


class TestTerminalStates:
    """Tests for TERMINAL_STATES definition."""

    def test_terminal_states_complete(self) -> None:
        """Should include all terminal states."""
        assert "completed" in TERMINAL_STATES
        assert "cancelled" in TERMINAL_STATES
        assert "aborted" in TERMINAL_STATES

    def test_non_terminal_states_not_included(self) -> None:
        """Should not include non-terminal states."""
        assert "queued" not in TERMINAL_STATES
        assert "running" not in TERMINAL_STATES
        assert "failed" not in TERMINAL_STATES
        assert "aborting" not in TERMINAL_STATES


class TestJobData:
    """Tests for JobData dataclass."""

    def test_job_creation(self) -> None:
        """Should create job with all fields."""
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        job = JobData(
            id=job_id,
            job_type="export",
            status="queued",
            created_at=now,
            metadata={"format": "csv"},
        )
        assert job.id == job_id
        assert job.job_type == "export"
        assert job.status == "queued"
        assert job.created_at == now
        assert job.started_at is None
        assert job.completed_at is None
        assert job.error is None
        assert job.metadata == {"format": "csv"}

    def test_job_to_dict(self) -> None:
        """Should serialize job to dictionary."""
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        job = JobData(
            id=job_id,
            job_type="cleanup",
            status="running",
            created_at=now,
            started_at=now,
        )
        data = job.to_dict()
        assert data["id"] == job_id
        assert data["job_type"] == "cleanup"
        assert data["status"] == "running"
        assert data["created_at"] == now.isoformat()
        assert data["started_at"] == now.isoformat()
        assert data["completed_at"] is None


class TestJobStateServiceValidation:
    """Tests for validation methods."""

    def test_is_valid_transition_valid(self, job_state_service: JobStateService) -> None:
        """Should return True for valid transitions."""
        assert job_state_service.is_valid_transition("queued", "running") is True
        assert job_state_service.is_valid_transition("queued", "cancelled") is True
        assert job_state_service.is_valid_transition("running", "completed") is True
        assert job_state_service.is_valid_transition("running", "failed") is True
        assert job_state_service.is_valid_transition("running", "aborting") is True
        assert job_state_service.is_valid_transition("aborting", "aborted") is True
        assert job_state_service.is_valid_transition("aborting", "failed") is True
        assert job_state_service.is_valid_transition("failed", "queued") is True

    def test_is_valid_transition_invalid(self, job_state_service: JobStateService) -> None:
        """Should return False for invalid transitions."""
        assert job_state_service.is_valid_transition("queued", "completed") is False
        assert job_state_service.is_valid_transition("completed", "running") is False
        assert job_state_service.is_valid_transition("cancelled", "running") is False
        assert job_state_service.is_valid_transition("aborted", "queued") is False
        assert job_state_service.is_valid_transition("running", "queued") is False

    def test_is_valid_transition_unknown_status(self, job_state_service: JobStateService) -> None:
        """Should return False for unknown status."""
        assert job_state_service.is_valid_transition("unknown", "running") is False
        assert job_state_service.is_valid_transition("queued", "unknown") is False

    def test_get_valid_transitions(self, job_state_service: JobStateService) -> None:
        """Should return list of valid target states."""
        assert job_state_service.get_valid_transitions("queued") == ["running", "cancelled"]
        assert job_state_service.get_valid_transitions("running") == [
            "completed",
            "failed",
            "aborting",
        ]
        assert job_state_service.get_valid_transitions("completed") == []

    def test_get_valid_transitions_unknown_status(self, job_state_service: JobStateService) -> None:
        """Should return empty list for unknown status."""
        assert job_state_service.get_valid_transitions("unknown") == []

    def test_is_terminal_state(self, job_state_service: JobStateService) -> None:
        """Should correctly identify terminal states."""
        assert job_state_service.is_terminal_state("completed") is True
        assert job_state_service.is_terminal_state("cancelled") is True
        assert job_state_service.is_terminal_state("aborted") is True
        assert job_state_service.is_terminal_state("queued") is False
        assert job_state_service.is_terminal_state("running") is False
        assert job_state_service.is_terminal_state("failed") is False


class TestJobStateServiceTransitions:
    """Tests for state transition methods."""

    @pytest.mark.asyncio
    async def test_queued_to_running(
        self, job_state_service: JobStateService, queued_job: JobData
    ) -> None:
        """Should transition from queued to running."""
        result = await job_state_service.transition(queued_job, "running")
        assert result.status == "running"
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_running_to_completed(
        self, job_state_service: JobStateService, running_job: JobData
    ) -> None:
        """Should transition from running to completed."""
        result = await job_state_service.transition(running_job, "completed")
        assert result.status == "completed"
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_running_to_failed(
        self, job_state_service: JobStateService, running_job: JobData
    ) -> None:
        """Should transition from running to failed with error."""
        result = await job_state_service.transition(
            running_job, "failed", error_message="Connection timeout"
        )
        assert result.status == "failed"
        assert result.completed_at is not None
        assert result.error == "Connection timeout"

    @pytest.mark.asyncio
    async def test_running_to_aborting(
        self, job_state_service: JobStateService, running_job: JobData
    ) -> None:
        """Should transition from running to aborting."""
        result = await job_state_service.transition(running_job, "aborting")
        assert result.status == "aborting"

    @pytest.mark.asyncio
    async def test_aborting_to_aborted(
        self, job_state_service: JobStateService, aborting_job: JobData
    ) -> None:
        """Should transition from aborting to aborted."""
        result = await job_state_service.transition(aborting_job, "aborted")
        assert result.status == "aborted"
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_aborting_to_failed(
        self, job_state_service: JobStateService, aborting_job: JobData
    ) -> None:
        """Should transition from aborting to failed."""
        result = await job_state_service.transition(
            aborting_job, "failed", error_message="Abort failed"
        )
        assert result.status == "failed"
        assert result.error == "Abort failed"

    @pytest.mark.asyncio
    async def test_failed_to_queued_retry(
        self, job_state_service: JobStateService, failed_job: JobData
    ) -> None:
        """Should transition from failed to queued for retry."""
        result = await job_state_service.transition(
            failed_job, "queued", triggered_by=str(JobTransitionTrigger.RETRY)
        )
        assert result.status == "queued"

    @pytest.mark.asyncio
    async def test_queued_to_cancelled(
        self, job_state_service: JobStateService, queued_job: JobData
    ) -> None:
        """Should transition from queued to cancelled."""
        result = await job_state_service.transition(
            queued_job, "cancelled", triggered_by=str(JobTransitionTrigger.USER)
        )
        assert result.status == "cancelled"
        assert result.completed_at is not None


class TestInvalidTransitions:
    """Tests for invalid state transitions."""

    @pytest.mark.asyncio
    async def test_invalid_completed_to_running(self, job_state_service: JobStateService) -> None:
        """Should reject transition from completed to running."""
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="export",
            status="completed",
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(job, "running")
        assert exc_info.value.from_status == "completed"
        assert exc_info.value.to_status == "running"

    @pytest.mark.asyncio
    async def test_invalid_cancelled_to_running(self, job_state_service: JobStateService) -> None:
        """Should reject transition from cancelled to running."""
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="export",
            status="cancelled",
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(job, "running")
        assert exc_info.value.from_status == "cancelled"
        assert exc_info.value.to_status == "running"

    @pytest.mark.asyncio
    async def test_invalid_aborted_to_queued(self, job_state_service: JobStateService) -> None:
        """Should reject transition from aborted to queued."""
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="export",
            status="aborted",
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(job, "queued")
        assert exc_info.value.from_status == "aborted"
        assert exc_info.value.to_status == "queued"

    @pytest.mark.asyncio
    async def test_invalid_queued_to_completed(
        self, job_state_service: JobStateService, queued_job: JobData
    ) -> None:
        """Should reject direct transition from queued to completed."""
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(queued_job, "completed")
        assert exc_info.value.from_status == "queued"
        assert exc_info.value.to_status == "completed"

    @pytest.mark.asyncio
    async def test_invalid_running_to_queued(
        self, job_state_service: JobStateService, running_job: JobData
    ) -> None:
        """Should reject transition from running to queued."""
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(running_job, "queued")
        assert exc_info.value.from_status == "running"
        assert exc_info.value.to_status == "queued"


class TestTransitionHistory:
    """Tests for transition history recording."""

    @pytest.mark.asyncio
    async def test_transition_records_history(
        self, job_state_service: JobStateService, mock_db: AsyncMock, queued_job: JobData
    ) -> None:
        """Should record transition in database."""
        await job_state_service.transition(queued_job, "running")

        # Verify add was called with a JobTransition
        assert mock_db.add.called
        transition = mock_db.add.call_args[0][0]
        assert isinstance(transition, JobTransition)
        assert transition.job_id == queued_job.id
        assert transition.from_status == "queued"
        assert transition.to_status == "running"

    @pytest.mark.asyncio
    async def test_transition_records_trigger(
        self, job_state_service: JobStateService, mock_db: AsyncMock, queued_job: JobData
    ) -> None:
        """Should record trigger type in transition."""
        await job_state_service.transition(
            queued_job, "cancelled", triggered_by=str(JobTransitionTrigger.USER)
        )

        transition = mock_db.add.call_args[0][0]
        assert transition.triggered_by == str(JobTransitionTrigger.USER)

    @pytest.mark.asyncio
    async def test_transition_records_metadata(
        self, job_state_service: JobStateService, mock_db: AsyncMock, queued_job: JobData
    ) -> None:
        """Should record metadata in transition."""
        await job_state_service.transition(
            queued_job, "running", metadata={"worker_id": "worker-1"}
        )

        transition = mock_db.add.call_args[0][0]
        assert transition.metadata_json is not None
        assert "worker_id" in transition.metadata_json


class TestCreateJob:
    """Tests for job creation."""

    def test_create_job_with_defaults(self, job_state_service: JobStateService) -> None:
        """Should create job with generated ID and queued status."""
        job = job_state_service.create_job("export")
        assert job.id is not None
        assert len(job.id) == 36  # UUID format
        assert job.job_type == "export"
        assert job.status == "queued"
        assert job.created_at is not None

    def test_create_job_with_custom_id(self, job_state_service: JobStateService) -> None:
        """Should create job with custom ID."""
        custom_id = str(uuid.uuid4())
        job = job_state_service.create_job("backup", job_id=custom_id)
        assert job.id == custom_id

    def test_create_job_with_metadata(self, job_state_service: JobStateService) -> None:
        """Should create job with metadata."""
        job = job_state_service.create_job(
            "export", metadata={"format": "json", "camera_ids": ["cam1"]}
        )
        assert job.metadata == {"format": "json", "camera_ids": ["cam1"]}


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_validate_transition_valid(self) -> None:
        """Should return True for valid transitions."""
        assert validate_transition("queued", "running") is True
        assert validate_transition("running", "completed") is True
        assert validate_transition("failed", "queued") is True

    def test_validate_transition_invalid(self) -> None:
        """Should return False for invalid transitions."""
        assert validate_transition("completed", "running") is False
        assert validate_transition("cancelled", "queued") is False

    def test_get_valid_target_states(self) -> None:
        """Should return valid target states."""
        assert get_valid_target_states("queued") == ["running", "cancelled"]
        assert get_valid_target_states("running") == ["completed", "failed", "aborting"]
        assert get_valid_target_states("completed") == []


class TestTimestampUpdates:
    """Tests for automatic timestamp updates."""

    @pytest.mark.asyncio
    async def test_running_sets_started_at(
        self, job_state_service: JobStateService, queued_job: JobData
    ) -> None:
        """Transitioning to running should set started_at."""
        assert queued_job.started_at is None
        result = await job_state_service.transition(queued_job, "running")
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_completed_sets_completed_at(
        self, job_state_service: JobStateService, running_job: JobData
    ) -> None:
        """Transitioning to completed should set completed_at."""
        assert running_job.completed_at is None
        result = await job_state_service.transition(running_job, "completed")
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_failed_sets_completed_at(
        self, job_state_service: JobStateService, running_job: JobData
    ) -> None:
        """Transitioning to failed should set completed_at."""
        assert running_job.completed_at is None
        result = await job_state_service.transition(running_job, "failed")
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancelled_sets_completed_at(
        self, job_state_service: JobStateService, queued_job: JobData
    ) -> None:
        """Transitioning to cancelled should set completed_at."""
        result = await job_state_service.transition(queued_job, "cancelled")
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_aborted_sets_completed_at(
        self, job_state_service: JobStateService, aborting_job: JobData
    ) -> None:
        """Transitioning to aborted should set completed_at."""
        result = await job_state_service.transition(aborting_job, "aborted")
        assert result.completed_at is not None


class TestExceptionDetails:
    """Tests for InvalidStateTransition exception details."""

    @pytest.mark.asyncio
    async def test_exception_includes_job_id(self, job_state_service: JobStateService) -> None:
        """Exception should include job ID."""
        job = JobData(
            id="test-job-123",
            job_type="export",
            status="completed",
            created_at=datetime.now(UTC),
        )
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(job, "running")
        assert exc_info.value.job_id == "test-job-123"

    @pytest.mark.asyncio
    async def test_exception_status_code(self, job_state_service: JobStateService) -> None:
        """Exception should have 409 status code."""
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="export",
            status="completed",
            created_at=datetime.now(UTC),
        )
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(job, "running")
        # ConflictError has default status code 409
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_exception_error_code(self, job_state_service: JobStateService) -> None:
        """Exception should have correct error code."""
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="export",
            status="completed",
            created_at=datetime.now(UTC),
        )
        with pytest.raises(InvalidStateTransition) as exc_info:
            await job_state_service.transition(job, "running")
        assert exc_info.value.error_code == "INVALID_STATE_TRANSITION"
