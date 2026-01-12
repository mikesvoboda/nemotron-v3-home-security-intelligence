"""Unit tests for DatabaseJobService (NEM-2389).

Tests for the database-backed job service including:
1. Job creation with various parameters
2. Job listing with filtering, pagination, and sorting
3. Job lifecycle operations (start, complete, fail, cancel)
4. Job statistics and aggregation
5. Job retry functionality
6. Old job cleanup
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.job import Job, JobStatus
from backend.services.job_service import (
    VALID_SORT_FIELDS,
    DatabaseJobService,
    create_database_job_service,
)


class TestDatabaseJobServiceCreation:
    """Tests for DatabaseJobService initialization."""

    def test_create_database_job_service_factory(self, mock_db_session: AsyncMock) -> None:
        """Test factory function creates service instance."""
        service = create_database_job_service(mock_db_session)

        assert isinstance(service, DatabaseJobService)
        assert service._db is mock_db_session

    def test_database_job_service_init(self, mock_db_session: AsyncMock) -> None:
        """Test direct initialization of service."""
        service = DatabaseJobService(mock_db_session)

        assert service._db is mock_db_session


class TestCreateJob:
    """Tests for job creation."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_create_job_with_defaults(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a job with default parameters."""
        job = await service.create_job("export")

        # Verify job was added to session
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()

        # Verify job properties
        assert job.job_type == "export"
        assert job.status == JobStatus.QUEUED.value
        assert job.priority == 2  # Default priority
        assert job.max_attempts == 3  # Default max attempts
        assert job.id is not None  # UUID should be generated

    @pytest.mark.asyncio
    async def test_create_job_with_custom_id(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a job with a custom ID."""
        custom_id = "custom-job-id-123"
        job = await service.create_job("cleanup", job_id=custom_id)

        assert job.id == custom_id

    @pytest.mark.asyncio
    async def test_create_job_with_queue_name(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a job with a queue name."""
        job = await service.create_job("backup", queue_name="high_priority")

        assert job.queue_name == "high_priority"

    @pytest.mark.asyncio
    async def test_create_job_with_custom_priority(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a job with custom priority."""
        job = await service.create_job("import", priority=0)  # Highest priority

        assert job.priority == 0

    @pytest.mark.asyncio
    async def test_create_job_with_custom_max_attempts(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test creating a job with custom max attempts."""
        job = await service.create_job("ai_analysis", max_attempts=5)

        assert job.max_attempts == 5


class TestGetJobById:
    """Tests for retrieving jobs by ID."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_get_job_by_id_found(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test getting a job that exists."""
        expected_job = Job(
            id="test-job-123",
            job_type="export",
            status=JobStatus.QUEUED.value,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = expected_job

        job = await service.get_job_by_id("test-job-123")

        assert job is expected_job
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_by_id_not_found(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test getting a job that doesn't exist."""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        job = await service.get_job_by_id("nonexistent-id")

        assert job is None


class TestListJobs:
    """Tests for job listing with filters and pagination."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_list_jobs_default_params(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test listing jobs with default parameters."""
        mock_jobs = [
            Job(id="job-1", job_type="export", status=JobStatus.COMPLETED.value),
            Job(id="job-2", job_type="cleanup", status=JobStatus.QUEUED.value),
        ]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
        mock_db_session.execute.return_value.scalar.return_value = 2

        jobs, total = await service.list_jobs()

        assert len(jobs) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering jobs by status."""
        mock_jobs = [Job(id="job-1", job_type="export", status=JobStatus.RUNNING.value)]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
        mock_db_session.execute.return_value.scalar.return_value = 1

        jobs, _total = await service.list_jobs(status="running")

        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.RUNNING.value

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_job_type(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering jobs by job type."""
        mock_jobs = [Job(id="job-1", job_type="export", status=JobStatus.QUEUED.value)]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
        mock_db_session.execute.return_value.scalar.return_value = 1

        jobs, _total = await service.list_jobs(job_type="export")

        assert len(jobs) == 1
        assert jobs[0].job_type == "export"

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_since(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering jobs created since a timestamp."""
        since_time = datetime.now(UTC) - timedelta(hours=1)
        mock_jobs = []
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
        mock_db_session.execute.return_value.scalar.return_value = 0

        jobs, total = await service.list_jobs(since=since_time)

        assert len(jobs) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_jobs_pagination(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test pagination with limit and offset."""
        mock_jobs = [Job(id="job-3", job_type="backup", status=JobStatus.COMPLETED.value)]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
        mock_db_session.execute.return_value.scalar.return_value = 10  # Total of 10 jobs

        jobs, total = await service.list_jobs(limit=5, offset=5)

        assert len(jobs) == 1  # Mocked to return 1
        assert total == 10  # Total count is 10

    @pytest.mark.asyncio
    async def test_list_jobs_sort_ascending(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test sorting jobs in ascending order."""
        mock_jobs = []
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
        mock_db_session.execute.return_value.scalar.return_value = 0

        await service.list_jobs(sort="created_at", order="asc")

        # Just verify the query was executed
        mock_db_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_list_jobs_invalid_sort_field_uses_default(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test that invalid sort field falls back to created_at."""
        mock_jobs = []
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
        mock_db_session.execute.return_value.scalar.return_value = 0

        # Should not raise an error, just use default
        _jobs, total = await service.list_jobs(sort="invalid_field")

        assert total == 0


class TestValidSortFields:
    """Tests for sort field validation."""

    def test_valid_sort_fields_defined(self) -> None:
        """Test that valid sort fields are properly defined."""
        expected_fields = {
            "created_at",
            "started_at",
            "completed_at",
            "job_type",
            "status",
            "priority",
        }
        assert expected_fields == VALID_SORT_FIELDS


class TestStartJob:
    """Tests for starting jobs."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_start_job_success(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test starting a queued job."""
        job = Job(id="job-1", job_type="export", status=JobStatus.QUEUED.value)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.start_job("job-1", current_step="Initializing export")

        assert result is not None
        assert result.status == JobStatus.RUNNING.value
        assert result.current_step == "Initializing export"
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_job_not_found(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test starting a job that doesn't exist."""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        result = await service.start_job("nonexistent")

        assert result is None


class TestUpdateProgress:
    """Tests for progress updates."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_update_progress_success(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test updating job progress."""
        job = Job(
            id="job-1",
            job_type="export",
            status=JobStatus.RUNNING.value,
            progress_percent=0,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.update_progress("job-1", 50, current_step="Processing items")

        assert result is not None
        assert result.progress_percent == 50
        assert result.current_step == "Processing items"

    @pytest.mark.asyncio
    async def test_update_progress_clamps_to_100(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test that progress is clamped to 100."""
        job = Job(
            id="job-1",
            job_type="export",
            status=JobStatus.RUNNING.value,
            progress_percent=90,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.update_progress("job-1", 150)

        assert result is not None
        assert result.progress_percent == 100

    @pytest.mark.asyncio
    async def test_update_progress_clamps_to_0(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test that progress is clamped to 0."""
        job = Job(
            id="job-1",
            job_type="export",
            status=JobStatus.RUNNING.value,
            progress_percent=50,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.update_progress("job-1", -10)

        assert result is not None
        assert result.progress_percent == 0


class TestCompleteJob:
    """Tests for completing jobs."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_complete_job_success(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test completing a running job."""
        job = Job(
            id="job-1",
            job_type="export",
            status=JobStatus.RUNNING.value,
            progress_percent=90,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.complete_job(
            "job-1",
            result={"file_path": "/exports/data.csv", "row_count": 100},
        )

        assert result is not None
        assert result.status == JobStatus.COMPLETED.value
        assert result.progress_percent == 100
        assert result.result == {"file_path": "/exports/data.csv", "row_count": 100}
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_job_without_result(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test completing a job without result data."""
        job = Job(id="job-1", job_type="cleanup", status=JobStatus.RUNNING.value)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.complete_job("job-1")

        assert result is not None
        assert result.status == JobStatus.COMPLETED.value


class TestFailJob:
    """Tests for failing jobs."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_fail_job_success(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test failing a running job."""
        job = Job(id="job-1", job_type="export", status=JobStatus.RUNNING.value)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.fail_job(
            "job-1",
            error_message="Database connection failed",
            error_traceback="Traceback: ...",
        )

        assert result is not None
        assert result.status == JobStatus.FAILED.value
        assert result.error_message == "Database connection failed"
        assert result.error_traceback == "Traceback: ..."
        assert result.completed_at is not None


class TestCancelJob:
    """Tests for cancelling jobs."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_cancel_queued_job(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test cancelling a queued job."""
        job = Job(id="job-1", job_type="export", status=JobStatus.QUEUED.value)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.cancel_job("job-1")

        assert result is not None
        assert result.status == JobStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_running_job(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test cancelling a running job."""
        job = Job(id="job-1", job_type="export", status=JobStatus.RUNNING.value)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.cancel_job("job-1")

        assert result is not None
        assert result.status == JobStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test that cancelling a completed job returns None."""
        job = Job(id="job-1", job_type="export", status=JobStatus.COMPLETED.value)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.cancel_job("job-1")

        assert result is None  # Cannot cancel completed jobs


class TestGetActiveJobs:
    """Tests for retrieving active jobs."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_get_active_jobs(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test getting all active jobs."""
        mock_jobs = [
            Job(id="job-1", job_type="export", status=JobStatus.QUEUED.value),
            Job(id="job-2", job_type="cleanup", status=JobStatus.RUNNING.value),
        ]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs

        jobs = await service.get_active_jobs()

        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_get_active_jobs_by_type(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test getting active jobs filtered by type."""
        mock_jobs = [Job(id="job-1", job_type="export", status=JobStatus.QUEUED.value)]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs

        jobs = await service.get_active_jobs(job_type="export")

        assert len(jobs) == 1
        assert jobs[0].job_type == "export"


class TestGetJobStats:
    """Tests for job statistics."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        # Configure mock to return multiple results for multiple queries
        mock_db_session.execute = AsyncMock()
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_get_job_stats_returns_correct_structure(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test that job stats returns the expected structure."""
        # Mock the execute calls for different queries
        mock_status_result = MagicMock()
        mock_status_result.all.return_value = [
            ("completed", 50),
            ("running", 5),
            ("queued", 10),
        ]

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [
            ("export", 30),
            ("cleanup", 20),
            ("backup", 15),
        ]

        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 65

        mock_duration_result = MagicMock()
        mock_duration_result.scalar.return_value = 45.5

        mock_oldest_result = MagicMock()
        mock_oldest_result.scalar.return_value = None

        # Set up execute to return different results for each call
        mock_db_session.execute.side_effect = [
            mock_status_result,
            mock_type_result,
            mock_total_result,
            mock_duration_result,
            mock_oldest_result,
        ]

        stats = await service.get_job_stats()

        assert "total_jobs" in stats
        assert "by_status" in stats
        assert "by_type" in stats
        assert "average_duration_seconds" in stats
        assert "oldest_pending_job_age_seconds" in stats


class TestRetryJob:
    """Tests for job retry functionality."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_retry_job_success(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test retrying a failed job that has remaining attempts."""
        job = Job(
            id="job-1",
            job_type="export",
            status=JobStatus.FAILED.value,
            attempt_number=1,
            max_attempts=3,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.retry_job("job-1")

        assert result is not None
        assert result.status == JobStatus.QUEUED.value
        assert result.attempt_number == 2

    @pytest.mark.asyncio
    async def test_retry_job_no_remaining_attempts(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test that retry fails when no attempts remain."""
        job = Job(
            id="job-1",
            job_type="export",
            status=JobStatus.FAILED.value,
            attempt_number=3,
            max_attempts=3,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.retry_job("job-1")

        assert result is None  # Cannot retry - max attempts reached

    @pytest.mark.asyncio
    async def test_retry_non_failed_job_returns_none(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test that retrying a non-failed job returns None."""
        job = Job(
            id="job-1",
            job_type="export",
            status=JobStatus.COMPLETED.value,
            attempt_number=1,
            max_attempts=3,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = job

        result = await service.retry_job("job-1")

        assert result is None  # Cannot retry completed jobs


class TestCleanupOldJobs:
    """Tests for old job cleanup."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        """Create service instance for tests."""
        return DatabaseJobService(mock_db_session)

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs_deletes_finished_jobs(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test cleanup deletes old completed/failed/cancelled jobs."""
        mock_result = MagicMock()
        mock_result.rowcount = 25
        mock_db_session.execute.return_value = mock_result

        deleted = await service.cleanup_old_jobs(days=30)

        assert deleted == 25
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs_with_custom_days(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Test cleanup with custom retention period."""
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_db_session.execute.return_value = mock_result

        deleted = await service.cleanup_old_jobs(days=7)

        assert deleted == 10
