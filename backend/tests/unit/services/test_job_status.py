"""Tests for the job status tracking service.

This module tests the JobStatusService which provides Redis-backed
job status tracking for background jobs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from backend.services.job_status import (
    DEFAULT_COMPLETED_JOB_TTL,
    JOB_STATUS_KEY_PREFIX,
    JobMetadata,
    JobState,
    JobStatusService,
    get_job_status_service,
    reset_job_status_service,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)
    redis.zrangebyscore = AsyncMock(return_value=[])
    redis.zcard = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def job_status_service(mock_redis: AsyncMock) -> JobStatusService:
    """Create a job status service with mock Redis."""
    return JobStatusService(redis_client=mock_redis)


@pytest.fixture(autouse=True)
def cleanup_singleton() -> None:
    """Reset the job status service singleton after each test."""
    yield
    reset_job_status_service()


class TestJobState:
    """Tests for JobState enum."""

    def test_state_values(self) -> None:
        """Should have expected state values."""
        assert JobState.PENDING == "pending"
        assert JobState.RUNNING == "running"
        assert JobState.COMPLETED == "completed"
        assert JobState.FAILED == "failed"


class TestJobMetadata:
    """Tests for JobMetadata dataclass."""

    def test_metadata_creation(self) -> None:
        """Should create metadata with all fields."""
        now = datetime.now(UTC)
        metadata = JobMetadata(
            job_id="test-123",
            job_type="export",
            status=JobState.PENDING,
            progress=0,
            message=None,
            created_at=now,
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
            extra={"camera_id": "front_door"},
        )
        assert metadata.job_id == "test-123"
        assert metadata.job_type == "export"
        assert metadata.status == JobState.PENDING
        assert metadata.progress == 0
        assert metadata.extra == {"camera_id": "front_door"}

    def test_metadata_to_dict(self) -> None:
        """Should serialize to dictionary."""
        now = datetime.now(UTC)
        metadata = JobMetadata(
            job_id="test-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message="Processing...",
            created_at=now,
            started_at=now,
            completed_at=None,
            result=None,
            error=None,
            extra=None,
        )
        data = metadata.to_dict()
        assert data["job_id"] == "test-123"
        assert data["job_type"] == "export"
        assert data["status"] == "running"
        assert data["progress"] == 50
        assert data["message"] == "Processing..."
        assert data["created_at"] == now.isoformat()
        assert data["started_at"] == now.isoformat()
        assert data["completed_at"] is None

    def test_metadata_from_dict(self) -> None:
        """Should deserialize from dictionary."""
        now = datetime.now(UTC)
        data = {
            "job_id": "test-456",
            "job_type": "cleanup",
            "status": "completed",
            "progress": 100,
            "message": "Done",
            "created_at": now.isoformat(),
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
            "result": {"count": 10},
            "error": None,
            "extra": {"retention_days": 30},
        }
        metadata = JobMetadata.from_dict(data)
        assert metadata.job_id == "test-456"
        assert metadata.job_type == "cleanup"
        assert metadata.status == JobState.COMPLETED
        assert metadata.progress == 100
        assert metadata.result == {"count": 10}
        assert metadata.extra == {"retention_days": 30}


class TestJobStatusServiceStartJob:
    """Tests for starting jobs."""

    @pytest.mark.asyncio
    async def test_start_job_creates_pending_job(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should create a job with PENDING status."""
        job_id = await job_status_service.start_job(
            job_id="job-123",
            job_type="export",
            metadata={"format": "csv"},
        )

        assert job_id == "job-123"
        mock_redis.set.assert_called()
        mock_redis.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_start_job_generates_uuid_if_none(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should generate UUID if job_id is None."""
        job_id = await job_status_service.start_job(
            job_id=None,
            job_type="backup",
            metadata=None,
        )

        assert job_id is not None
        assert len(job_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_start_job_stores_metadata(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should store job metadata in Redis."""
        await job_status_service.start_job(
            job_id="job-123",
            job_type="export",
            metadata={"format": "json", "camera_ids": ["cam1", "cam2"]},
        )

        # Verify Redis set was called with correct key
        set_call = mock_redis.set.call_args
        assert set_call is not None
        key = set_call[0][0]
        assert key == f"{JOB_STATUS_KEY_PREFIX}job-123"


class TestJobStatusServiceUpdateProgress:
    """Tests for updating job progress."""

    @pytest.mark.asyncio
    async def test_update_progress_success(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should update job progress."""
        # Setup: return existing job data
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 0,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.update_progress(
            job_id="job-123",
            progress=50,
            message="Processing 50/100 items",
        )

        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_update_progress_clamps_to_100(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should clamp progress to 100."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 90,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.update_progress(
            job_id="job-123",
            progress=150,
            message=None,
        )

        set_call = mock_redis.set.call_args
        assert set_call is not None
        # The value should have progress clamped to 100
        stored_data = set_call[0][1]
        assert stored_data["progress"] == 100

    @pytest.mark.asyncio
    async def test_update_progress_clamps_to_0(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should clamp progress to 0."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 10,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.update_progress(
            job_id="job-123",
            progress=-10,
            message=None,
        )

        set_call = mock_redis.set.call_args
        assert set_call is not None
        stored_data = set_call[0][1]
        assert stored_data["progress"] == 0

    @pytest.mark.asyncio
    async def test_update_progress_job_not_found_raises(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should raise KeyError if job not found."""
        mock_redis.get.return_value = None

        with pytest.raises(KeyError, match="Job not found"):
            await job_status_service.update_progress(
                job_id="nonexistent",
                progress=50,
                message=None,
            )

    @pytest.mark.asyncio
    async def test_update_progress_sets_running_status(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should set status to RUNNING if currently PENDING."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "pending",
            "progress": 0,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.update_progress(
            job_id="job-123",
            progress=10,
            message="Starting...",
        )

        set_call = mock_redis.set.call_args
        assert set_call is not None
        stored_data = set_call[0][1]
        assert stored_data["status"] == "running"
        assert stored_data["started_at"] is not None


class TestJobStatusServiceCompleteJob:
    """Tests for completing jobs."""

    @pytest.mark.asyncio
    async def test_complete_job_sets_completed_status(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should set job status to COMPLETED."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 90,
            "message": "Almost done",
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.complete_job(
            job_id="job-123",
            result={"file_path": "/exports/data.csv"},
        )

        set_call = mock_redis.set.call_args
        assert set_call is not None
        stored_data = set_call[0][1]
        assert stored_data["status"] == "completed"
        assert stored_data["progress"] == 100
        assert stored_data["result"] == {"file_path": "/exports/data.csv"}
        assert stored_data["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_complete_job_sets_ttl(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should set TTL for completed job auto-cleanup."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 90,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.complete_job(job_id="job-123", result=None)

        # Verify set was called with expire parameter
        set_call = mock_redis.set.call_args
        assert set_call is not None
        # Check if expire was passed as kwarg
        assert set_call.kwargs.get("expire") == DEFAULT_COMPLETED_JOB_TTL

    @pytest.mark.asyncio
    async def test_complete_job_not_found_raises(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should raise KeyError if job not found."""
        mock_redis.get.return_value = None

        with pytest.raises(KeyError, match="Job not found"):
            await job_status_service.complete_job(job_id="nonexistent", result=None)


class TestJobStatusServiceFailJob:
    """Tests for failing jobs."""

    @pytest.mark.asyncio
    async def test_fail_job_sets_failed_status(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should set job status to FAILED."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 50,
            "message": "Processing...",
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.fail_job(
            job_id="job-123",
            error="Database connection failed",
        )

        set_call = mock_redis.set.call_args
        assert set_call is not None
        stored_data = set_call[0][1]
        assert stored_data["status"] == "failed"
        assert stored_data["error"] == "Database connection failed"
        assert stored_data["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_fail_job_sets_ttl(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should set TTL for failed job auto-cleanup."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 50,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.fail_job(job_id="job-123", error="Error")

        set_call = mock_redis.set.call_args
        assert set_call is not None
        assert set_call.kwargs.get("expire") == DEFAULT_COMPLETED_JOB_TTL

    @pytest.mark.asyncio
    async def test_fail_job_not_found_raises(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should raise KeyError if job not found."""
        mock_redis.get.return_value = None

        with pytest.raises(KeyError, match="Job not found"):
            await job_status_service.fail_job(job_id="nonexistent", error="Error")


class TestJobStatusServiceGetJobStatus:
    """Tests for getting job status."""

    @pytest.mark.asyncio
    async def test_get_job_status_returns_metadata(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return job metadata."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 75,
            "message": "Processing...",
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": {"format": "csv"},
        }
        mock_redis.get.return_value = existing_job

        metadata = await job_status_service.get_job_status(job_id="job-123")

        assert metadata is not None
        assert metadata.job_id == "job-123"
        assert metadata.job_type == "export"
        assert metadata.status == JobState.RUNNING
        assert metadata.progress == 75
        assert metadata.extra == {"format": "csv"}

    @pytest.mark.asyncio
    async def test_get_job_status_returns_none_if_not_found(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return None if job not found."""
        mock_redis.get.return_value = None

        metadata = await job_status_service.get_job_status(job_id="nonexistent")

        assert metadata is None


class TestJobStatusServiceListJobs:
    """Tests for listing jobs."""

    @pytest.mark.asyncio
    async def test_list_jobs_returns_all_jobs(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return all jobs when no filter."""
        mock_redis.zrangebyscore.return_value = ["job-1", "job-2", "job-3"]
        mock_redis.get.side_effect = [
            {
                "job_id": "job-1",
                "job_type": "export",
                "status": "completed",
                "progress": 100,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "result": None,
                "error": None,
                "extra": None,
            },
            {
                "job_id": "job-2",
                "job_type": "cleanup",
                "status": "running",
                "progress": 50,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
                "result": None,
                "error": None,
                "extra": None,
            },
            {
                "job_id": "job-3",
                "job_type": "backup",
                "status": "pending",
                "progress": 0,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "extra": None,
            },
        ]

        jobs = await job_status_service.list_jobs(status_filter=None, limit=50)

        assert len(jobs) == 3
        job_ids = [j.job_id for j in jobs]
        assert "job-1" in job_ids
        assert "job-2" in job_ids
        assert "job-3" in job_ids

    @pytest.mark.asyncio
    async def test_list_jobs_filters_by_status(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should filter jobs by status."""
        mock_redis.zrangebyscore.return_value = ["job-1", "job-2"]
        mock_redis.get.side_effect = [
            {
                "job_id": "job-1",
                "job_type": "export",
                "status": "running",
                "progress": 50,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
                "result": None,
                "error": None,
                "extra": None,
            },
            {
                "job_id": "job-2",
                "job_type": "cleanup",
                "status": "completed",
                "progress": 100,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "result": None,
                "error": None,
                "extra": None,
            },
        ]

        jobs = await job_status_service.list_jobs(status_filter=JobState.RUNNING, limit=50)

        # Should only return running jobs
        assert len(jobs) == 1
        assert jobs[0].job_id == "job-1"
        assert jobs[0].status == JobState.RUNNING

    @pytest.mark.asyncio
    async def test_list_jobs_respects_limit(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should respect the limit parameter."""
        mock_redis.zrangebyscore.return_value = ["job-1", "job-2", "job-3"]
        mock_redis.get.side_effect = [
            {
                "job_id": "job-1",
                "job_type": "export",
                "status": "pending",
                "progress": 0,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "extra": None,
            },
            {
                "job_id": "job-2",
                "job_type": "cleanup",
                "status": "pending",
                "progress": 0,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "extra": None,
            },
            {
                "job_id": "job-3",
                "job_type": "backup",
                "status": "pending",
                "progress": 0,
                "message": None,
                "created_at": datetime.now(UTC).isoformat(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "extra": None,
            },
        ]

        jobs = await job_status_service.list_jobs(status_filter=None, limit=2)

        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_returns_empty_list_when_none(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return empty list when no jobs exist."""
        mock_redis.zrangebyscore.return_value = []

        jobs = await job_status_service.list_jobs(status_filter=None, limit=50)

        assert jobs == []


class TestJobStatusServiceSingleton:
    """Tests for singleton management."""

    def test_get_job_status_service_returns_singleton(self, mock_redis: AsyncMock) -> None:
        """Should return the same instance on repeated calls."""
        service1 = get_job_status_service(mock_redis)
        service2 = get_job_status_service(mock_redis)
        assert service1 is service2

    def test_reset_clears_singleton(self, mock_redis: AsyncMock) -> None:
        """Should clear the singleton on reset."""
        service1 = get_job_status_service(mock_redis)
        reset_job_status_service()
        service2 = get_job_status_service(mock_redis)
        assert service1 is not service2


class TestJobStatusServiceEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_corrupted_redis_data(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should handle corrupted data gracefully."""
        # Return data missing required fields
        mock_redis.get.return_value = {"invalid": "data"}

        metadata = await job_status_service.get_job_status(job_id="job-123")

        # Should return None for corrupted data
        assert metadata is None

    @pytest.mark.asyncio
    async def test_handles_redis_connection_error(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should propagate Redis errors."""
        mock_redis.get.side_effect = ConnectionError("Redis unavailable")

        with pytest.raises(ConnectionError):
            await job_status_service.get_job_status(job_id="job-123")

    @pytest.mark.asyncio
    async def test_job_type_validation(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should accept any string as job_type."""
        await job_status_service.start_job(
            job_id="job-123",
            job_type="custom_job_type_with_underscores",
            metadata=None,
        )

        set_call = mock_redis.set.call_args
        assert set_call is not None
        stored_data = set_call[0][1]
        assert stored_data["job_type"] == "custom_job_type_with_underscores"
