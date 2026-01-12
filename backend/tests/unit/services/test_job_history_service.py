"""Tests for the job history service.

This module tests the JobHistoryService which provides database-backed
job history, transitions, attempts, and logs retrieval.

NEM-2396: Job history and audit trail API.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.job import Job, JobStatus
from backend.models.job_attempt import JobAttempt
from backend.models.job_log import JobLog
from backend.models.job_transition import JobTransition
from backend.services.job_history_service import (
    AttemptRecord,
    JobHistory,
    JobHistoryService,
    JobLogEntry,
    TransitionRecord,
    get_job_history_service,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def job_history_service(mock_session: AsyncMock) -> JobHistoryService:
    """Create a job history service with mock session."""
    return JobHistoryService(session=mock_session)


@pytest.fixture
def sample_job() -> Job:
    """Create a sample Job instance."""
    job = Job(
        id=str(uuid4()),
        job_type="export",
        status=JobStatus.COMPLETED.value,
        created_at=datetime.now(UTC) - timedelta(minutes=10),
        started_at=datetime.now(UTC) - timedelta(minutes=9),
        completed_at=datetime.now(UTC) - timedelta(minutes=5),
        progress_percent=100,
        current_step="Completed",
    )
    return job


@pytest.fixture
def sample_job_uuid() -> UUID:
    """Return a sample UUID for testing."""
    return uuid4()


class TestTransitionRecord:
    """Tests for TransitionRecord dataclass."""

    def test_transition_record_creation(self) -> None:
        """Should create transition record with all fields."""
        now = datetime.now(UTC)
        record = TransitionRecord(
            from_status=None,
            to_status="queued",
            at=now,
            triggered_by="api",
            details={"user": "system"},
        )
        assert record.from_status is None
        assert record.to_status == "queued"
        assert record.at == now
        assert record.triggered_by == "api"
        assert record.details == {"user": "system"}

    def test_transition_record_with_from_status(self) -> None:
        """Should create transition record with from status."""
        now = datetime.now(UTC)
        record = TransitionRecord(
            from_status="queued",
            to_status="running",
            at=now,
            triggered_by="worker",
            details=None,
        )
        assert record.from_status == "queued"
        assert record.to_status == "running"


class TestAttemptRecord:
    """Tests for AttemptRecord dataclass."""

    def test_attempt_record_creation(self) -> None:
        """Should create attempt record with all fields."""
        now = datetime.now(UTC)
        later = now + timedelta(minutes=5)
        record = AttemptRecord(
            attempt_number=1,
            started_at=now,
            ended_at=later,
            status="succeeded",
            error=None,
            worker_id="worker-1",
            duration_seconds=300.0,
            result={"processed": 100},
        )
        assert record.attempt_number == 1
        assert record.started_at == now
        assert record.ended_at == later
        assert record.status == "succeeded"
        assert record.error is None
        assert record.worker_id == "worker-1"
        assert record.duration_seconds == 300.0
        assert record.result == {"processed": 100}

    def test_attempt_record_with_error(self) -> None:
        """Should create attempt record with error details."""
        now = datetime.now(UTC)
        record = AttemptRecord(
            attempt_number=2,
            started_at=now,
            ended_at=now + timedelta(seconds=30),
            status="failed",
            error="Connection timeout",
            worker_id="worker-2",
            duration_seconds=30.0,
            result=None,
        )
        assert record.status == "failed"
        assert record.error == "Connection timeout"


class TestJobHistory:
    """Tests for JobHistory dataclass."""

    def test_job_history_to_dict(self) -> None:
        """Should serialize to dictionary correctly."""
        now = datetime.now(UTC)
        history = JobHistory(
            job_id="job-123",
            job_type="export",
            status="completed",
            created_at=now,
            started_at=now + timedelta(seconds=1),
            completed_at=now + timedelta(minutes=5),
            transitions=[
                TransitionRecord(
                    from_status=None,
                    to_status="queued",
                    at=now,
                    triggered_by="api",
                    details=None,
                ),
            ],
            attempts=[
                AttemptRecord(
                    attempt_number=1,
                    started_at=now + timedelta(seconds=1),
                    ended_at=now + timedelta(minutes=5),
                    status="succeeded",
                    error=None,
                    worker_id="worker-1",
                    duration_seconds=299.0,
                    result=None,
                ),
            ],
        )

        result = history.to_dict()

        assert result["job_id"] == "job-123"
        assert result["job_type"] == "export"
        assert result["status"] == "completed"
        assert len(result["transitions"]) == 1
        assert result["transitions"][0]["from"] is None
        assert result["transitions"][0]["to"] == "queued"
        assert len(result["attempts"]) == 1
        assert result["attempts"][0]["attempt_number"] == 1


class TestJobLogEntry:
    """Tests for JobLogEntry dataclass."""

    def test_job_log_entry_creation(self) -> None:
        """Should create log entry with all fields."""
        now = datetime.now(UTC)
        entry = JobLogEntry(
            timestamp=now,
            level="info",
            message="Processing started",
            context={"item_count": 100},
            attempt_number=1,
        )
        assert entry.timestamp == now
        assert entry.level == "info"
        assert entry.message == "Processing started"
        assert entry.context == {"item_count": 100}
        assert entry.attempt_number == 1

    def test_job_log_entry_to_dict(self) -> None:
        """Should serialize to dictionary correctly."""
        now = datetime.now(UTC)
        entry = JobLogEntry(
            timestamp=now,
            level="error",
            message="Connection failed",
            context=None,
            attempt_number=2,
        )

        result = entry.to_dict()

        assert result["timestamp"] == now.isoformat()
        assert result["level"] == "ERROR"
        assert result["message"] == "Connection failed"
        assert result["context"] is None
        assert result["attempt_number"] == 2


class TestJobHistoryServiceGetHistory:
    """Tests for getting job history."""

    @pytest.mark.asyncio
    async def test_get_job_history_returns_none_for_nonexistent_job(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
    ) -> None:
        """Should return None if job not found."""
        # Setup: job not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await job_history_service.get_job_history("nonexistent-job")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_job_history_returns_history_for_existing_job(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job: Job,
    ) -> None:
        """Should return job history for existing job."""
        # Setup: job found, no transitions or attempts
        job_result = MagicMock()
        job_result.scalar_one_or_none.return_value = sample_job

        transitions_result = MagicMock()
        transitions_result.scalars.return_value.all.return_value = []

        attempts_result = MagicMock()
        attempts_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [job_result, transitions_result, attempts_result]

        result = await job_history_service.get_job_history(sample_job.id)

        assert result is not None
        assert result.job_id == sample_job.id
        assert result.job_type == "export"
        assert result.status == JobStatus.COMPLETED.value
        assert result.transitions == []
        assert result.attempts == []

    @pytest.mark.asyncio
    async def test_get_job_history_includes_transitions(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job: Job,
        sample_job_uuid: UUID,
    ) -> None:
        """Should include transitions in history."""
        now = datetime.now(UTC)

        # Create mock transition
        transition = MagicMock(spec=JobTransition)
        transition.from_status = "initial"
        transition.to_status = "queued"
        transition.transitioned_at = now
        transition.triggered_by = "api"
        transition.metadata_json = None

        job_result = MagicMock()
        job_result.scalar_one_or_none.return_value = sample_job

        transitions_result = MagicMock()
        transitions_result.scalars.return_value.all.return_value = [transition]

        attempts_result = MagicMock()
        attempts_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [job_result, transitions_result, attempts_result]

        # Use valid UUID string
        sample_job.id = str(sample_job_uuid)
        result = await job_history_service.get_job_history(sample_job.id)

        assert result is not None
        assert len(result.transitions) == 1
        assert result.transitions[0].to_status == "queued"
        assert result.transitions[0].from_status is None  # "initial" should be converted to None

    @pytest.mark.asyncio
    async def test_get_job_history_includes_attempts(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job: Job,
        sample_job_uuid: UUID,
    ) -> None:
        """Should include attempts in history."""
        now = datetime.now(UTC)

        # Create mock attempt
        attempt = MagicMock(spec=JobAttempt)
        attempt.attempt_number = 1
        attempt.started_at = now
        attempt.ended_at = now + timedelta(minutes=5)
        attempt.status = "succeeded"
        attempt.error_message = None
        attempt.worker_id = "worker-1"
        attempt.duration_seconds = 300.0
        attempt.result = {"items": 100}

        job_result = MagicMock()
        job_result.scalar_one_or_none.return_value = sample_job

        transitions_result = MagicMock()
        transitions_result.scalars.return_value.all.return_value = []

        attempts_result = MagicMock()
        attempts_result.scalars.return_value.all.return_value = [attempt]

        mock_session.execute.side_effect = [job_result, transitions_result, attempts_result]

        # Use valid UUID string
        sample_job.id = str(sample_job_uuid)
        result = await job_history_service.get_job_history(sample_job.id)

        assert result is not None
        assert len(result.attempts) == 1
        assert result.attempts[0].attempt_number == 1
        assert result.attempts[0].status == "succeeded"
        assert result.attempts[0].worker_id == "worker-1"


class TestJobHistoryServiceGetLogs:
    """Tests for getting job logs."""

    @pytest.mark.asyncio
    async def test_get_job_logs_returns_empty_for_invalid_uuid(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
    ) -> None:
        """Should return empty list for invalid job UUID."""
        result = await job_history_service.get_job_logs("not-a-valid-uuid")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_job_logs_returns_logs(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should return logs for job."""
        now = datetime.now(UTC)

        # Create mock log
        log = MagicMock(spec=JobLog)
        log.timestamp = now
        log.level = "info"
        log.message = "Processing started"
        log.context = {"item_count": 100}
        log.attempt_number = 1

        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = [log]
        mock_session.execute.return_value = logs_result

        result = await job_history_service.get_job_logs(str(sample_job_uuid))

        assert len(result) == 1
        assert result[0].message == "Processing started"
        assert result[0].level == "info"

    @pytest.mark.asyncio
    async def test_get_job_logs_respects_limit(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should respect the limit parameter."""
        now = datetime.now(UTC)

        # Create multiple mock logs
        logs = []
        for i in range(5):
            log = MagicMock(spec=JobLog)
            log.timestamp = now + timedelta(seconds=i)
            log.level = "info"
            log.message = f"Log entry {i}"
            log.context = None
            log.attempt_number = 1
            logs.append(log)

        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = logs[:3]
        mock_session.execute.return_value = logs_result

        result = await job_history_service.get_job_logs(
            str(sample_job_uuid),
            limit=3,
        )

        assert len(result) == 3


class TestJobHistoryServiceRecordAttempt:
    """Tests for recording job attempts."""

    @pytest.mark.asyncio
    async def test_record_attempt_start_creates_attempt(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should create attempt record on start."""
        result = await job_history_service.record_attempt_start(
            job_id=str(sample_job_uuid),
            attempt_number=1,
            worker_id="worker-1",
        )

        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_attempt_start_returns_none_for_invalid_uuid(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
    ) -> None:
        """Should return None for invalid job UUID."""
        result = await job_history_service.record_attempt_start(
            job_id="not-a-valid-uuid",
            attempt_number=1,
            worker_id="worker-1",
        )

        assert result is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_attempt_end_updates_attempt(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should update attempt record on end."""
        # Create mock attempt
        attempt = MagicMock(spec=JobAttempt)
        attempt.ended_at = None

        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = attempt
        mock_session.execute.return_value = attempt_result

        result = await job_history_service.record_attempt_end(
            job_id=str(sample_job_uuid),
            attempt_number=1,
            status="succeeded",
            error_message=None,
            result={"items": 100},
        )

        assert result is not None
        assert result.status == "succeeded"
        assert result.result == {"items": 100}

    @pytest.mark.asyncio
    async def test_record_attempt_end_returns_none_if_not_found(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should return None if attempt not found."""
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = attempt_result

        result = await job_history_service.record_attempt_end(
            job_id=str(sample_job_uuid),
            attempt_number=99,
            status="failed",
        )

        assert result is None


class TestJobHistoryServiceAddLog:
    """Tests for adding job logs."""

    @pytest.mark.asyncio
    async def test_add_job_log_creates_entry(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should create log entry."""
        result = await job_history_service.add_job_log(
            job_id=str(sample_job_uuid),
            level="INFO",
            message="Processing started",
            context={"item_count": 100},
            attempt_number=1,
        )

        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_job_log_returns_none_for_invalid_uuid(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
    ) -> None:
        """Should return None for invalid job UUID."""
        result = await job_history_service.add_job_log(
            job_id="not-a-valid-uuid",
            level="INFO",
            message="Test",
        )

        assert result is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_job_log_normalizes_level(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should normalize log level to lowercase."""
        result = await job_history_service.add_job_log(
            job_id=str(sample_job_uuid),
            level="ERROR",
            message="Something went wrong",
        )

        assert result is not None
        # Verify the log was added with lowercase level
        add_call = mock_session.add.call_args
        added_log = add_call[0][0]
        assert added_log.level == "error"


class TestGetJobHistoryServiceFactory:
    """Tests for the service factory function."""

    def test_get_job_history_service_creates_instance(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Should create service instance with session."""
        service = get_job_history_service(mock_session)

        assert isinstance(service, JobHistoryService)
        assert service._session is mock_session


class TestLogLevelFiltering:
    """Tests for log level filtering logic."""

    @pytest.mark.asyncio
    async def test_get_logs_filters_by_level(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should filter logs by level."""
        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = logs_result

        # Request only ERROR level logs
        await job_history_service.get_job_logs(
            str(sample_job_uuid),
            level="ERROR",
        )

        # Verify execute was called (filtering happens in query)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_logs_filters_by_since(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should filter logs by timestamp."""
        since = datetime.now(UTC) - timedelta(hours=1)

        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = logs_result

        await job_history_service.get_job_logs(
            str(sample_job_uuid),
            since=since,
        )

        # Verify execute was called (filtering happens in query)
        mock_session.execute.assert_called_once()
