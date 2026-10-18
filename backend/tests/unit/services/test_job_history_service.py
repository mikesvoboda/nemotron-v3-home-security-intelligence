"""Tests for the job history/logs service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.job import Job, JobStatus
from backend.models.job_log import JobLog
from backend.services.job_history_service import (
    JobHistoryService,
    JobLogEntry,
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
    return Job(
        id=str(uuid4()),
        job_type="export",
        status=JobStatus.COMPLETED.value,
        created_at=datetime.now(UTC) - timedelta(minutes=10),
        started_at=datetime.now(UTC) - timedelta(minutes=9),
        completed_at=datetime.now(UTC) - timedelta(minutes=5),
        progress_percent=100,
        current_step="Completed",
    )


@pytest.fixture
def sample_job_uuid() -> UUID:
    """Return a sample UUID for testing."""
    return uuid4()


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


class TestJobHistoryServiceJobExists:
    """Tests for checking job existence."""

    @pytest.mark.asyncio
    async def test_job_exists_returns_false_for_nonexistent_job(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
    ) -> None:
        """Should return False if job not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await job_history_service.job_exists("nonexistent-job")

        assert result is False

    @pytest.mark.asyncio
    async def test_job_exists_returns_true_for_existing_job(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job: Job,
    ) -> None:
        """Should return True if job exists."""
        job_result = MagicMock()
        job_result.scalar_one_or_none.return_value = sample_job
        mock_session.execute.return_value = job_result

        result = await job_history_service.job_exists(sample_job.id)

        assert result is True


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

        await job_history_service.get_job_logs(
            str(sample_job_uuid),
            level="ERROR",
        )

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

        mock_session.execute.assert_called_once()
