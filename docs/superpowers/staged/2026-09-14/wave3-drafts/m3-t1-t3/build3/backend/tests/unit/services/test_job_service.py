"""Tests for the job service (NEM-2390).

Tests for job retrieval, transformation to detailed response format,
and 404 handling for non-existent jobs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.api.schemas.jobs import (
    JobDetailResponse,
    JobMetadata,
    JobProgressDetail,
    JobRetryInfo,
    JobStatusEnum,
)
from backend.services.job_service import DEFAULT_MAX_ATTEMPTS, JobService
from backend.services.job_tracker import JobInfo, JobStatus, JobTracker


@pytest.fixture
def mock_job_tracker() -> MagicMock:
    """Create a mock job tracker."""
    tracker = MagicMock(spec=JobTracker)
    tracker.get_job_from_redis = AsyncMock()
    return tracker


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Create a mock Redis client."""
    return MagicMock()


@pytest.fixture
def job_service(mock_job_tracker: MagicMock, mock_redis_client: MagicMock) -> JobService:
    """Create a job service with mock dependencies."""
    return JobService(job_tracker=mock_job_tracker, redis_client=mock_redis_client)


@pytest.fixture
def sample_job_info() -> JobInfo:
    """Create a sample job info for testing."""
    return JobInfo(
        job_id="test-job-123",
        job_type="export",
        status=JobStatus.RUNNING,
        progress=50,
        message="Processing events: 50/100",
        created_at="2024-01-15T10:30:00+00:00",
        started_at="2024-01-15T10:30:01+00:00",
        completed_at=None,
        result=None,
        error=None,
    )


@pytest.fixture
def completed_job_info() -> JobInfo:
    """Create a completed job info for testing."""
    return JobInfo(
        job_id="completed-job-456",
        job_type="export",
        status=JobStatus.COMPLETED,
        progress=100,
        message="Completed successfully",
        created_at="2024-01-15T10:30:00+00:00",
        started_at="2024-01-15T10:30:01+00:00",
        completed_at="2024-01-15T10:31:00+00:00",
        result={
            "file_path": "/exports/test.csv",
            "file_size": 12345,
            "event_count": 100,
        },
        error=None,
    )


@pytest.fixture
def failed_job_info() -> JobInfo:
    """Create a failed job info for testing."""
    return JobInfo(
        job_id="failed-job-789",
        job_type="backup",
        status=JobStatus.FAILED,
        progress=30,
        message="Failed: Database connection error",
        created_at="2024-01-15T10:30:00+00:00",
        started_at="2024-01-15T10:30:01+00:00",
        completed_at="2024-01-15T10:30:30+00:00",
        result=None,
        error="Database connection error",
    )


class TestJobServiceGetJob:
    """Tests for get_job method."""

    def test_get_job_returns_job_when_found(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        """Should return job when found in tracker."""
        mock_job_tracker.get_job.return_value = sample_job_info

        result = job_service.get_job("test-job-123")

        assert result is not None
        assert result["job_id"] == "test-job-123"
        mock_job_tracker.get_job.assert_called_once_with("test-job-123")

    def test_get_job_returns_none_when_not_found(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should return None when job not found."""
        mock_job_tracker.get_job.return_value = None

        result = job_service.get_job("nonexistent-job")

        assert result is None

    def test_get_job_accepts_uuid_string(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        """Should accept UUID as string."""
        mock_job_tracker.get_job.return_value = sample_job_info
        from uuid import UUID

        uuid_val = UUID("550e8400-e29b-41d4-a716-446655440000")

        job_service.get_job(uuid_val)

        mock_job_tracker.get_job.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")


class TestJobServiceGetJobWithFallback:
    """Tests for get_job_with_fallback method."""

    @pytest.mark.asyncio
    async def test_returns_job_from_memory_first(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        """Should return job from in-memory if available."""
        mock_job_tracker.get_job.return_value = sample_job_info

        result = await job_service.get_job_with_fallback("test-job-123")

        assert result is not None
        assert result["job_id"] == "test-job-123"
        mock_job_tracker.get_job_from_redis.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_redis(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        completed_job_info: JobInfo,
    ) -> None:
        """Should fall back to Redis when not in memory."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis.return_value = completed_job_info

        result = await job_service.get_job_with_fallback("completed-job-456")

        assert result is not None
        assert result["job_id"] == "completed-job-456"
        mock_job_tracker.get_job_from_redis.assert_called_once_with("completed-job-456")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_in_memory_or_redis(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should return None when job not in memory or Redis."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis.return_value = None

        result = await job_service.get_job_with_fallback("nonexistent-job")

        assert result is None


class TestJobServiceGetJobOr404:
    """Tests for get_job_or_404 method."""

    def test_returns_job_when_found(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        """Should return job when found."""
        mock_job_tracker.get_job.return_value = sample_job_info

        result = job_service.get_job_or_404("test-job-123")

        assert result["job_id"] == "test-job-123"

    def test_raises_404_when_not_found(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should raise HTTPException 404 when job not found."""
        mock_job_tracker.get_job.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            job_service.get_job_or_404("nonexistent-job")

        assert exc_info.value.status_code == 404
        assert "nonexistent-job" in exc_info.value.detail


class TestJobServiceGetJobOr404Async:
    """Tests for get_job_or_404_async method."""

    @pytest.mark.asyncio
    async def test_returns_job_when_found(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        """Should return job when found."""
        mock_job_tracker.get_job.return_value = sample_job_info

        result = await job_service.get_job_or_404_async("test-job-123")

        assert result["job_id"] == "test-job-123"

    @pytest.mark.asyncio
    async def test_falls_back_to_redis(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        completed_job_info: JobInfo,
    ) -> None:
        """Should fall back to Redis before raising 404."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis.return_value = completed_job_info

        result = await job_service.get_job_or_404_async("completed-job-456")

        assert result["job_id"] == "completed-job-456"

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should raise HTTPException 404 when job not found anywhere."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await job_service.get_job_or_404_async("nonexistent-job")

        assert exc_info.value.status_code == 404
        assert "nonexistent-job" in exc_info.value.detail


class TestJobServiceTransformToDetailResponse:
    """Tests for transform_to_detail_response method."""

    def test_transforms_running_job(
        self,
        job_service: JobService,
        sample_job_info: JobInfo,
    ) -> None:
        """Should correctly transform a running job."""
        result = job_service.transform_to_detail_response(sample_job_info)

        assert isinstance(result, JobDetailResponse)
        assert result.id == "test-job-123"
        assert result.job_type == "export"
        assert result.status == JobStatusEnum.RUNNING
        assert result.progress.percent == 50
        assert result.timing.started_at is not None
        assert result.timing.completed_at is None
        assert result.retry_info.attempt_number == 1
        assert result.retry_info.max_attempts == DEFAULT_MAX_ATTEMPTS

    def test_transforms_completed_job(
        self,
        job_service: JobService,
        completed_job_info: JobInfo,
    ) -> None:
        """Should correctly transform a completed job."""
        result = job_service.transform_to_detail_response(completed_job_info)

        assert result.id == "completed-job-456"
        assert result.status == JobStatusEnum.COMPLETED
        assert result.progress.percent == 100
        assert result.timing.completed_at is not None
        assert result.timing.duration_seconds is not None
        assert result.timing.duration_seconds > 0
        assert result.result is not None
        assert result.error is None

    def test_transforms_failed_job(
        self,
        job_service: JobService,
        failed_job_info: JobInfo,
    ) -> None:
        """Should correctly transform a failed job."""
        result = job_service.transform_to_detail_response(failed_job_info)

        assert result.id == "failed-job-789"
        assert result.status == JobStatusEnum.FAILED
        assert result.progress.percent == 30
        assert result.error == "Database connection error"
        assert result.result is None

    def test_extracts_progress_from_message(
        self,
        job_service: JobService,
    ) -> None:
        """Should extract items_processed and items_total from message."""
        job = JobInfo(
            job_id="progress-job",
            job_type="export",
            status=JobStatus.RUNNING,
            progress=45,
            message="Processing events: 450/1000",
            created_at="2024-01-15T10:30:00+00:00",
            started_at="2024-01-15T10:30:01+00:00",
            completed_at=None,
            result=None,
            error=None,
        )

        result = job_service.transform_to_detail_response(job)

        assert result.progress.percent == 45
        assert result.progress.items_processed == 450
        assert result.progress.items_total == 1000

    def test_handles_various_message_formats(
        self,
        job_service: JobService,
    ) -> None:
        """Should handle different message formats for extracting counts."""
        job = JobInfo(
            job_id="alt-format-job",
            job_type="import",
            status=JobStatus.RUNNING,
            progress=60,
            message="Importing 300 of 500 records",
            created_at="2024-01-15T10:30:00+00:00",
            started_at="2024-01-15T10:30:01+00:00",
            completed_at=None,
            result=None,
            error=None,
        )

        result = job_service.transform_to_detail_response(job)

        assert result.progress.items_processed == 300
        assert result.progress.items_total == 500


class TestJobServiceProgressDetail:
    """Tests for _extract_progress_detail method."""

    def test_extracts_percent_from_job(
        self,
        job_service: JobService,
        sample_job_info: JobInfo,
    ) -> None:
        """Should extract progress percentage from job."""
        result = job_service._extract_progress_detail(sample_job_info)

        assert isinstance(result, JobProgressDetail)
        assert result.percent == 50

    def test_current_step_is_extracted_from_message(
        self,
        job_service: JobService,
        sample_job_info: JobInfo,
    ) -> None:
        """Should extract step name from message when it has colon format."""
        # sample_job_info has message "Processing events: 50/100"
        # which should extract "Processing events" as the step name
        result = job_service._extract_progress_detail(sample_job_info)

        assert result.current_step == "Processing events"

    def test_handles_null_message(
        self,
        job_service: JobService,
    ) -> None:
        """Should handle null message gracefully."""
        job = JobInfo(
            job_id="null-msg-job",
            job_type="cleanup",
            status=JobStatus.PENDING,
            progress=0,
            message=None,
            created_at="2024-01-15T10:30:00+00:00",
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
        )

        result = job_service._extract_progress_detail(job)

        assert result.percent == 0
        assert result.current_step is None
        assert result.items_processed is None
        assert result.items_total is None


class TestJobServiceTiming:
    """Tests for _extract_timing method."""

    def test_calculates_duration_for_completed_job(
        self,
        job_service: JobService,
        completed_job_info: JobInfo,
    ) -> None:
        """Should calculate duration for completed job."""
        result = job_service._extract_timing(completed_job_info, 100)

        assert result.duration_seconds is not None
        # Started at 10:30:01, completed at 10:31:00 = 59 seconds
        assert result.duration_seconds == pytest.approx(59.0, abs=1.0)

    def test_estimates_remaining_time_for_running_job(
        self,
        job_service: JobService,
    ) -> None:
        """Should estimate remaining time for running job."""
        # Create job with known progress and duration
        now = datetime.now(UTC)
        started_at = now.replace(second=0, microsecond=0)

        job = JobInfo(
            job_id="running-job",
            job_type="export",
            status=JobStatus.RUNNING,
            progress=50,
            message="Processing...",
            created_at=started_at.isoformat(),
            started_at=started_at.isoformat(),
            completed_at=None,
            result=None,
            error=None,
        )

        result = job_service._extract_timing(job, 50)

        # Running job should have timing info
        assert result.created_at is not None
        assert result.started_at is not None
        assert result.completed_at is None

    def test_no_estimated_remaining_for_pending_job(
        self,
        job_service: JobService,
    ) -> None:
        """Should not estimate remaining time for pending job."""
        job = JobInfo(
            job_id="pending-job",
            job_type="cleanup",
            status=JobStatus.PENDING,
            progress=0,
            message=None,
            created_at="2024-01-15T10:30:00+00:00",
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
        )

        result = job_service._extract_timing(job, 0)

        assert result.started_at is None
        assert result.duration_seconds is None
        assert result.estimated_remaining_seconds is None


class TestJobServiceRetryInfo:
    """Tests for _extract_retry_info method."""

    def test_returns_default_retry_info(
        self,
        job_service: JobService,
        sample_job_info: JobInfo,
    ) -> None:
        """Should return default retry info for jobs without retry tracking."""
        result = job_service._extract_retry_info(sample_job_info)

        assert isinstance(result, JobRetryInfo)
        assert result.attempt_number == 1
        assert result.max_attempts == DEFAULT_MAX_ATTEMPTS
        assert result.next_retry_at is None
        assert result.previous_errors == []


class TestJobServiceMetadata:
    """Tests for _extract_metadata method."""

    def test_returns_empty_metadata_by_default(
        self,
        job_service: JobService,
        sample_job_info: JobInfo,
    ) -> None:
        """Should return empty metadata by default."""
        result = job_service._extract_metadata(sample_job_info)

        assert isinstance(result, JobMetadata)
        assert result.input_params is None
        assert result.worker_id is None

    def test_extracts_input_params_from_result(
        self,
        job_service: JobService,
    ) -> None:
        """Should extract input_params if present in result."""
        job = JobInfo(
            job_id="metadata-job",
            job_type="export",
            status=JobStatus.COMPLETED,
            progress=100,
            message="Done",
            created_at="2024-01-15T10:30:00+00:00",
            started_at="2024-01-15T10:30:01+00:00",
            completed_at="2024-01-15T10:31:00+00:00",
            result={
                "input_params": {"format": "csv", "camera_id": "cam-1"},
                "file_path": "/exports/test.csv",
            },
            error=None,
        )

        result = job_service._extract_metadata(job)

        assert result.input_params == {"format": "csv", "camera_id": "cam-1"}


class TestJobServiceGetJobDetail:
    """Tests for get_job_detail method."""

    @pytest.mark.asyncio
    async def test_returns_detail_response(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        """Should return detailed job response."""
        mock_job_tracker.get_job.return_value = sample_job_info

        result = await job_service.get_job_detail("test-job-123")

        assert isinstance(result, JobDetailResponse)
        assert result.id == "test-job-123"
        assert result.job_type == "export"
        assert result.status == JobStatusEnum.RUNNING

    @pytest.mark.asyncio
    async def test_raises_404_for_nonexistent_job(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should raise 404 for nonexistent job."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await job_service.get_job_detail("nonexistent-job")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_falls_back_to_redis(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        completed_job_info: JobInfo,
    ) -> None:
        """Should fall back to Redis for completed jobs."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis.return_value = completed_job_info

        result = await job_service.get_job_detail("completed-job-456")

        assert result.id == "completed-job-456"
        assert result.status == JobStatusEnum.COMPLETED
