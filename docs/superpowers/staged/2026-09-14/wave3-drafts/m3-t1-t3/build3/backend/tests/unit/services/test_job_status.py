"""Tests for the job status tracking service.

This module tests the JobStatusService which provides Redis-backed
job status tracking for background jobs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from backend.services.job_status import (
    ACTIVE_JOB_STALE_THRESHOLD_SECONDS,
    COMPLETED_JOB_RETENTION_SECONDS,
    DEFAULT_COMPLETED_JOB_TTL,
    DEFAULT_JOB_STATUS_LIST_MAX_ENTRIES,
    JOB_STATUS_KEY_PREFIX,
    JOB_STATUS_LIST_KEY,
    JOB_STATUS_SUFFIX,
    JOBS_ACTIVE_KEY,
    JOBS_COMPLETED_KEY,
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
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.zremrangebyrank = AsyncMock(return_value=0)
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
        assert JobState.QUEUED == "queued"
        assert JobState.PENDING == "pending"
        assert JobState.RUNNING == "running"
        assert JobState.COMPLETED == "completed"
        assert JobState.FAILED == "failed"
        assert JobState.CANCELLED == "cancelled"

    def test_all_states_exist(self) -> None:
        """Should have all required states."""
        states = [s.value for s in JobState]
        assert "queued" in states
        assert "pending" in states
        assert "running" in states
        assert "completed" in states
        assert "failed" in states
        assert "cancelled" in states


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
        assert key == f"{JOB_STATUS_KEY_PREFIX}job-123{JOB_STATUS_SUFFIX}"


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


class TestJobStatusServiceRedisKeyFormat:
    """Tests for Redis key format (NEM-2292)."""

    def test_job_key_format(self, job_status_service: JobStatusService) -> None:
        """Should use job:{job_id}:status key format."""
        key = job_status_service._get_job_key("test-123")
        assert key == f"{JOB_STATUS_KEY_PREFIX}test-123{JOB_STATUS_SUFFIX}"
        assert key == "job:test-123:status"


class TestJobStatusServiceRegistry:
    """Tests for job registry functionality (NEM-2292)."""

    @pytest.mark.asyncio
    async def test_start_job_adds_to_active_registry(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should add job to active registry on creation."""
        await job_status_service.start_job(
            job_id="job-123",
            job_type="export",
            metadata=None,
        )

        # Should have called zadd for both job list and active registry
        zadd_calls = mock_redis.zadd.call_args_list
        keys_added = [call[0][0] for call in zadd_calls]
        assert JOBS_ACTIVE_KEY in keys_added

    @pytest.mark.asyncio
    async def test_complete_job_moves_to_completed_registry(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should move job from active to completed registry on completion."""
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

        await job_status_service.complete_job(job_id="job-123", result={"done": True})

        # Should remove from active registry
        mock_redis.zrem.assert_called_with(JOBS_ACTIVE_KEY, "job-123")

        # Should add to completed registry
        zadd_calls = mock_redis.zadd.call_args_list
        keys_added = [call[0][0] for call in zadd_calls]
        assert JOBS_COMPLETED_KEY in keys_added

    @pytest.mark.asyncio
    async def test_fail_job_moves_to_completed_registry(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should move job from active to completed registry on failure."""
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

        await job_status_service.fail_job(job_id="job-123", error="Something went wrong")

        # Should remove from active registry
        mock_redis.zrem.assert_called_with(JOBS_ACTIVE_KEY, "job-123")

        # Should add to completed registry
        zadd_calls = mock_redis.zadd.call_args_list
        keys_added = [call[0][0] for call in zadd_calls]
        assert JOBS_COMPLETED_KEY in keys_added

    @pytest.mark.asyncio
    async def test_get_active_job_ids(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return active job IDs from registry."""
        mock_redis.zrangebyscore.return_value = ["job-1", "job-2", "job-3"]

        job_ids = await job_status_service.get_active_job_ids(limit=10)

        assert job_ids == ["job-1", "job-2", "job-3"]
        mock_redis.zrangebyscore.assert_called_with(JOBS_ACTIVE_KEY, "-inf", "+inf")

    @pytest.mark.asyncio
    async def test_get_active_job_ids_respects_limit(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should respect limit parameter."""
        mock_redis.zrangebyscore.return_value = ["job-1", "job-2", "job-3", "job-4", "job-5"]

        job_ids = await job_status_service.get_active_job_ids(limit=3)

        assert len(job_ids) == 3
        assert job_ids == ["job-1", "job-2", "job-3"]

    @pytest.mark.asyncio
    async def test_get_completed_job_ids(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return completed job IDs from registry."""
        mock_redis.zrangebyscore.return_value = ["job-a", "job-b"]

        job_ids = await job_status_service.get_completed_job_ids(limit=50)

        assert job_ids == ["job-a", "job-b"]
        mock_redis.zrangebyscore.assert_called_with(JOBS_COMPLETED_KEY, "-inf", "+inf")


class TestJobStatusServiceCancelJob:
    """Tests for job cancellation (NEM-2292)."""

    @pytest.mark.asyncio
    async def test_cancel_job_sets_cancelled_status(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should set job status to CANCELLED."""
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

        result = await job_status_service.cancel_job(job_id="job-123")

        assert result is True
        set_call = mock_redis.set.call_args
        assert set_call is not None
        stored_data = set_call[0][1]
        assert stored_data["status"] == "cancelled"
        assert stored_data["error"] == "Cancelled by user"
        assert stored_data["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_cancel_job_moves_to_completed_registry(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should move cancelled job to completed registry."""
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

        await job_status_service.cancel_job(job_id="job-123")

        # Should remove from active registry
        mock_redis.zrem.assert_called_with(JOBS_ACTIVE_KEY, "job-123")

        # Should add to completed registry
        zadd_calls = mock_redis.zadd.call_args_list
        keys_added = [call[0][0] for call in zadd_calls]
        assert JOBS_COMPLETED_KEY in keys_added

    @pytest.mark.asyncio
    async def test_cancel_job_returns_false_if_already_completed(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return False if job already completed."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "completed",
            "progress": 100,
            "message": "Done",
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        result = await job_status_service.cancel_job(job_id="job-123")

        assert result is False
        # Should not update the job
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_job_returns_false_if_already_failed(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return False if job already failed."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "failed",
            "progress": 50,
            "message": "Error",
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "result": None,
            "error": "Some error",
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        result = await job_status_service.cancel_job(job_id="job-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_job_returns_false_if_already_cancelled(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return False if job already cancelled."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "cancelled",
            "progress": 30,
            "message": "Cancelled",
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "result": None,
            "error": "Cancelled by user",
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        result = await job_status_service.cancel_job(job_id="job-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_job_raises_if_not_found(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should raise KeyError if job not found."""
        mock_redis.get.return_value = None

        with pytest.raises(KeyError, match="Job not found"):
            await job_status_service.cancel_job(job_id="nonexistent")

    @pytest.mark.asyncio
    async def test_cancel_queued_job(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should be able to cancel a queued job."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "queued",
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

        result = await job_status_service.cancel_job(job_id="job-123")

        assert result is True
        set_call = mock_redis.set.call_args
        assert set_call is not None
        stored_data = set_call[0][1]
        assert stored_data["status"] == "cancelled"


class TestJobStatusServiceCleanup:
    """Tests for job registry cleanup methods (NEM-2511)."""

    @pytest.mark.asyncio
    async def test_cleanup_completed_jobs_removes_old_entries(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should remove old completed job entries from sorted set."""
        mock_redis.zremrangebyscore.return_value = 5

        removed = await job_status_service.cleanup_completed_jobs()

        assert removed == 5
        mock_redis.zremrangebyscore.assert_called_once()
        call_args = mock_redis.zremrangebyscore.call_args
        assert call_args[0][0] == JOBS_COMPLETED_KEY
        assert call_args[0][1] == "-inf"
        # The third argument should be a timestamp

    @pytest.mark.asyncio
    async def test_cleanup_completed_jobs_uses_default_retention(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should use default retention period when not specified."""
        import time

        mock_redis.zremrangebyscore.return_value = 0

        before_time = time.time()
        await job_status_service.cleanup_completed_jobs()
        after_time = time.time()

        call_args = mock_redis.zremrangebyscore.call_args
        cutoff = call_args[0][2]

        # Verify the cutoff is approximately (now - COMPLETED_JOB_RETENTION_SECONDS)
        expected_min = before_time - COMPLETED_JOB_RETENTION_SECONDS - 1
        expected_max = after_time - COMPLETED_JOB_RETENTION_SECONDS + 1
        assert expected_min <= cutoff <= expected_max

    @pytest.mark.asyncio
    async def test_cleanup_completed_jobs_with_custom_retention(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should use custom retention period when specified."""
        import time

        mock_redis.zremrangebyscore.return_value = 3
        custom_retention = 1800  # 30 minutes

        before_time = time.time()
        removed = await job_status_service.cleanup_completed_jobs(
            retention_seconds=custom_retention
        )
        after_time = time.time()

        assert removed == 3
        call_args = mock_redis.zremrangebyscore.call_args
        cutoff = call_args[0][2]

        # Verify the cutoff is approximately (now - custom_retention)
        expected_min = before_time - custom_retention - 1
        expected_max = after_time - custom_retention + 1
        assert expected_min <= cutoff <= expected_max

    @pytest.mark.asyncio
    async def test_cleanup_completed_jobs_returns_zero_when_none_removed(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return zero when no entries removed."""
        mock_redis.zremrangebyscore.return_value = 0

        removed = await job_status_service.cleanup_completed_jobs()

        assert removed == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_active_jobs_removes_old_entries(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should remove stale active job entries from sorted set."""
        mock_redis.zremrangebyscore.return_value = 2

        removed = await job_status_service.cleanup_stale_active_jobs()

        assert removed == 2
        mock_redis.zremrangebyscore.assert_called_once()
        call_args = mock_redis.zremrangebyscore.call_args
        assert call_args[0][0] == JOBS_ACTIVE_KEY
        assert call_args[0][1] == "-inf"

    @pytest.mark.asyncio
    async def test_cleanup_stale_active_jobs_uses_default_threshold(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should use default stale threshold when not specified."""
        import time

        mock_redis.zremrangebyscore.return_value = 0

        before_time = time.time()
        await job_status_service.cleanup_stale_active_jobs()
        after_time = time.time()

        call_args = mock_redis.zremrangebyscore.call_args
        cutoff = call_args[0][2]

        # Verify the cutoff is approximately (now - ACTIVE_JOB_STALE_THRESHOLD_SECONDS)
        expected_min = before_time - ACTIVE_JOB_STALE_THRESHOLD_SECONDS - 1
        expected_max = after_time - ACTIVE_JOB_STALE_THRESHOLD_SECONDS + 1
        assert expected_min <= cutoff <= expected_max

    @pytest.mark.asyncio
    async def test_cleanup_stale_active_jobs_with_custom_threshold(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should use custom stale threshold when specified."""
        import time

        mock_redis.zremrangebyscore.return_value = 1
        custom_threshold = 3600  # 1 hour

        before_time = time.time()
        removed = await job_status_service.cleanup_stale_active_jobs(
            stale_threshold_seconds=custom_threshold
        )
        after_time = time.time()

        assert removed == 1
        call_args = mock_redis.zremrangebyscore.call_args
        cutoff = call_args[0][2]

        # Verify the cutoff is approximately (now - custom_threshold)
        expected_min = before_time - custom_threshold - 1
        expected_max = after_time - custom_threshold + 1
        assert expected_min <= cutoff <= expected_max

    @pytest.mark.asyncio
    async def test_cleanup_stale_active_jobs_returns_zero_when_none_removed(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return zero when no entries removed."""
        mock_redis.zremrangebyscore.return_value = 0

        removed = await job_status_service.cleanup_stale_active_jobs()

        assert removed == 0


class TestJobStatusServiceCleanupConstants:
    """Tests for cleanup-related constants (NEM-2511)."""

    def test_completed_job_retention_seconds_value(self) -> None:
        """Should have expected retention period for completed jobs."""
        assert COMPLETED_JOB_RETENTION_SECONDS == 3600  # 1 hour

    def test_active_job_stale_threshold_value(self) -> None:
        """Should have expected stale threshold for active jobs."""
        assert ACTIVE_JOB_STALE_THRESHOLD_SECONDS == 7200  # 2 hours

    def test_completed_job_retention_matches_ttl(self) -> None:
        """Completed job retention should match job TTL for consistency."""
        assert COMPLETED_JOB_RETENTION_SECONDS == DEFAULT_COMPLETED_JOB_TTL

    def test_job_status_list_max_entries_value(self) -> None:
        """Should have expected max entries for job status list (NEM-2510)."""
        assert DEFAULT_JOB_STATUS_LIST_MAX_ENTRIES == 10000


class TestJobStatusListCleanup:
    """Tests for job:status:list sorted set cleanup (NEM-2510)."""

    @pytest.mark.asyncio
    async def test_cleanup_job_status_list_removes_oldest_entries(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should remove oldest entries from job:status:list sorted set."""
        mock_redis.zremrangebyrank.return_value = 100

        removed = await job_status_service.cleanup_job_status_list()

        assert removed == 100
        mock_redis.zremrangebyrank.assert_called_once()
        call_args = mock_redis.zremrangebyrank.call_args
        assert call_args[0][0] == JOB_STATUS_LIST_KEY
        assert call_args[0][1] == 0  # Start from rank 0 (oldest)

    @pytest.mark.asyncio
    async def test_cleanup_job_status_list_uses_default_max_entries(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should use default max entries when not specified."""
        mock_redis.zremrangebyrank.return_value = 0

        await job_status_service.cleanup_job_status_list()

        call_args = mock_redis.zremrangebyrank.call_args
        # stop index should be -(DEFAULT_JOB_STATUS_LIST_MAX_ENTRIES + 1)
        expected_stop = -(DEFAULT_JOB_STATUS_LIST_MAX_ENTRIES + 1)
        assert call_args[0][2] == expected_stop

    @pytest.mark.asyncio
    async def test_cleanup_job_status_list_with_custom_max_entries(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should use custom max entries when specified."""
        mock_redis.zremrangebyrank.return_value = 50
        custom_max = 1000

        removed = await job_status_service.cleanup_job_status_list(max_entries=custom_max)

        assert removed == 50
        call_args = mock_redis.zremrangebyrank.call_args
        # stop index should be -(custom_max + 1)
        expected_stop = -(custom_max + 1)
        assert call_args[0][2] == expected_stop

    @pytest.mark.asyncio
    async def test_cleanup_job_status_list_returns_zero_when_none_removed(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should return zero when no entries removed."""
        mock_redis.zremrangebyrank.return_value = 0

        removed = await job_status_service.cleanup_job_status_list()

        assert removed == 0

    @pytest.mark.asyncio
    async def test_cleanup_job_status_list_called_on_start_job(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Should cleanup job status list automatically when starting a job."""
        mock_redis.zremrangebyrank.return_value = 0

        await job_status_service.start_job(
            job_id="test-job",
            job_type="export",
            metadata=None,
        )

        # Verify cleanup was called
        mock_redis.zremrangebyrank.assert_called_once()
        call_args = mock_redis.zremrangebyrank.call_args
        assert call_args[0][0] == JOB_STATUS_LIST_KEY

    @pytest.mark.asyncio
    async def test_service_init_with_custom_max_entries(self, mock_redis: AsyncMock) -> None:
        """Should accept custom max entries in constructor."""
        custom_max = 5000
        service = JobStatusService(
            redis_client=mock_redis,
            job_status_list_max_entries=custom_max,
        )
        mock_redis.zremrangebyrank.return_value = 0

        await service.cleanup_job_status_list()

        call_args = mock_redis.zremrangebyrank.call_args
        expected_stop = -(custom_max + 1)
        assert call_args[0][2] == expected_stop
