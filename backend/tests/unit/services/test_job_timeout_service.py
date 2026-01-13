"""Tests for the job timeout service.

This module tests the JobTimeoutService which provides timeout detection
and handling for background jobs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from backend.services.job_status import JobMetadata, JobState, JobStatusService
from backend.services.job_timeout_service import (
    ATTEMPT_COUNT_TTL_SECONDS,
    DEFAULT_JOB_TIMEOUT,
    DEFAULT_MAX_RETRY_ATTEMPTS,
    JOB_TIMEOUTS,
    TIMEOUT_CONFIG_TTL_SECONDS,
    JobTimeoutService,
    TimeoutConfig,
    TimeoutResult,
    get_job_timeout_service,
    reset_job_timeout_service,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)
    redis.zrangebyscore = AsyncMock(return_value=[])
    return redis


@pytest.fixture
def mock_job_status_service() -> AsyncMock:
    """Create a mock job status service."""
    service = AsyncMock(spec=JobStatusService)
    service.start_job = AsyncMock(return_value="new-job-id")
    service.fail_job = AsyncMock()
    service.get_job_status = AsyncMock(return_value=None)
    return service


@pytest.fixture
def job_timeout_service(
    mock_redis: AsyncMock,
    mock_job_status_service: AsyncMock,
) -> JobTimeoutService:
    """Create a job timeout service with mocks."""
    return JobTimeoutService(
        redis_client=mock_redis,
        job_status_service=mock_job_status_service,
    )


@pytest.fixture(autouse=True)
def cleanup_singleton() -> None:
    """Reset the job timeout service singleton after each test."""
    yield
    reset_job_timeout_service()


class TestTimeoutConfig:
    """Tests for TimeoutConfig dataclass."""

    def test_config_with_timeout_seconds(self) -> None:
        """Should create config with timeout_seconds."""
        config = TimeoutConfig(timeout_seconds=300)
        assert config.timeout_seconds == 300
        assert config.deadline is None
        assert config.max_retry_attempts == DEFAULT_MAX_RETRY_ATTEMPTS

    def test_config_with_deadline(self) -> None:
        """Should create config with deadline."""
        deadline = datetime.now(UTC) + timedelta(hours=1)
        config = TimeoutConfig(deadline=deadline)
        assert config.timeout_seconds is None
        assert config.deadline == deadline

    def test_config_with_both(self) -> None:
        """Should create config with both timeout and deadline."""
        deadline = datetime.now(UTC) + timedelta(hours=1)
        config = TimeoutConfig(timeout_seconds=300, deadline=deadline)
        assert config.timeout_seconds == 300
        assert config.deadline == deadline

    def test_config_with_custom_retry_attempts(self) -> None:
        """Should create config with custom retry attempts."""
        config = TimeoutConfig(timeout_seconds=300, max_retry_attempts=5)
        assert config.max_retry_attempts == 5

    def test_config_to_dict(self) -> None:
        """Should serialize to dictionary."""
        deadline = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        config = TimeoutConfig(
            timeout_seconds=300,
            deadline=deadline,
            max_retry_attempts=5,
        )
        data = config.to_dict()
        assert data["timeout_seconds"] == 300
        assert data["deadline"] == "2024-01-15T10:30:00+00:00"
        assert data["max_retry_attempts"] == 5

    def test_config_to_dict_without_deadline(self) -> None:
        """Should serialize to dictionary without deadline."""
        config = TimeoutConfig(timeout_seconds=300)
        data = config.to_dict()
        assert data["timeout_seconds"] == 300
        assert data["deadline"] is None

    def test_config_from_dict(self) -> None:
        """Should deserialize from dictionary."""
        data = {
            "timeout_seconds": 300,
            "deadline": "2024-01-15T10:30:00+00:00",
            "max_retry_attempts": 5,
        }
        config = TimeoutConfig.from_dict(data)
        assert config.timeout_seconds == 300
        assert config.deadline == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        assert config.max_retry_attempts == 5

    def test_config_from_dict_with_defaults(self) -> None:
        """Should use defaults when deserializing partial data."""
        data = {"timeout_seconds": 300}
        config = TimeoutConfig.from_dict(data)
        assert config.timeout_seconds == 300
        assert config.deadline is None
        assert config.max_retry_attempts == DEFAULT_MAX_RETRY_ATTEMPTS


class TestJobTimeoutServiceDefaultTimeouts:
    """Tests for default timeout configuration."""

    def test_get_default_timeout_for_known_type(
        self, job_timeout_service: JobTimeoutService
    ) -> None:
        """Should return configured timeout for known job types."""
        assert job_timeout_service.get_default_timeout("ai_analysis") == JOB_TIMEOUTS["ai_analysis"]
        assert job_timeout_service.get_default_timeout("export") == JOB_TIMEOUTS["export"]
        assert job_timeout_service.get_default_timeout("cleanup") == JOB_TIMEOUTS["cleanup"]
        assert job_timeout_service.get_default_timeout("retention") == JOB_TIMEOUTS["retention"]

    def test_get_default_timeout_for_unknown_type(
        self, job_timeout_service: JobTimeoutService
    ) -> None:
        """Should return default timeout for unknown job types."""
        assert job_timeout_service.get_default_timeout("unknown_type") == DEFAULT_JOB_TIMEOUT
        assert job_timeout_service.get_default_timeout("custom_job") == DEFAULT_JOB_TIMEOUT


class TestJobTimeoutServiceSetGetConfig:
    """Tests for setting and getting timeout configuration."""

    @pytest.mark.asyncio
    async def test_set_timeout_config(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should store timeout config in Redis."""
        config = TimeoutConfig(timeout_seconds=300)
        await job_timeout_service.set_timeout_config("job-123", config)

        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args
        assert "job:job-123:timeout" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_set_timeout_config_sets_ttl(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should set TTL on timeout config key to prevent unbounded memory growth (NEM-2508)."""
        config = TimeoutConfig(timeout_seconds=300)
        await job_timeout_service.set_timeout_config("job-789", config)

        # Verify redis.set was called with expire= parameter for TTL
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "job:job-789:timeout"  # Key
        assert call_args[0][1] == config.to_dict()  # Value
        assert call_args[1]["expire"] == TIMEOUT_CONFIG_TTL_SECONDS  # TTL (48 hours)

    def test_timeout_config_ttl_seconds_value(self) -> None:
        """Verify TIMEOUT_CONFIG_TTL_SECONDS is 48 hours (NEM-2508)."""
        assert TIMEOUT_CONFIG_TTL_SECONDS == 48 * 60 * 60  # 48 hours in seconds
        assert TIMEOUT_CONFIG_TTL_SECONDS == 172800  # Explicit value check

    @pytest.mark.asyncio
    async def test_get_timeout_config_returns_config(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should return timeout config from Redis."""
        mock_redis.get.return_value = {
            "timeout_seconds": 300,
            "deadline": None,
            "max_retry_attempts": 3,
        }

        config = await job_timeout_service.get_timeout_config("job-123")

        assert config is not None
        assert config.timeout_seconds == 300

    @pytest.mark.asyncio
    async def test_get_timeout_config_returns_none_when_not_set(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should return None when no config exists."""
        mock_redis.get.return_value = None

        config = await job_timeout_service.get_timeout_config("job-123")

        assert config is None


class TestJobTimeoutServiceAttemptCount:
    """Tests for attempt counting."""

    @pytest.mark.asyncio
    async def test_get_attempt_count_returns_zero_when_not_set(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should return 0 when no attempts recorded."""
        mock_redis.get.return_value = None

        count = await job_timeout_service.get_attempt_count("job-123")

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_attempt_count_returns_stored_value(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should return stored attempt count."""
        mock_redis.get.return_value = {"count": 2}

        count = await job_timeout_service.get_attempt_count("job-123")

        assert count == 2

    @pytest.mark.asyncio
    async def test_increment_attempt_count(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should increment and return new attempt count."""
        mock_redis.get.return_value = {"count": 1}

        new_count = await job_timeout_service.increment_attempt_count("job-123")

        assert new_count == 2
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_increment_attempt_count_sets_ttl(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should set TTL on attempt count key to prevent unbounded growth."""
        mock_redis.get.return_value = None  # No existing count

        await job_timeout_service.increment_attempt_count("job-456")

        # Verify redis.set was called with expire= parameter for TTL
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "job:job-456:attempts"  # Key
        assert call_args[0][1] == {"count": 1}  # Value
        assert call_args[1]["expire"] == ATTEMPT_COUNT_TTL_SECONDS  # TTL

    def test_attempt_count_ttl_seconds_value(self) -> None:
        """Verify ATTEMPT_COUNT_TTL_SECONDS is 1 hour (matches job lifecycle)."""
        assert ATTEMPT_COUNT_TTL_SECONDS == 3600  # 1 hour in seconds


class TestJobTimeoutServiceIsJobTimedOut:
    """Tests for timeout detection."""

    @pytest.mark.asyncio
    async def test_non_running_job_not_timed_out(
        self, job_timeout_service: JobTimeoutService
    ) -> None:
        """Should return False for non-running jobs."""
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.PENDING,
            progress=0,
            message=None,
            created_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
        )

        is_timed_out = await job_timeout_service.is_job_timed_out(job)

        assert is_timed_out is False

    @pytest.mark.asyncio
    async def test_job_without_started_at_not_timed_out(
        self, job_timeout_service: JobTimeoutService
    ) -> None:
        """Should return False for jobs without started_at."""
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=datetime.now(UTC),
            started_at=None,  # No started_at
            completed_at=None,
            result=None,
            error=None,
        )

        is_timed_out = await job_timeout_service.is_job_timed_out(job)

        assert is_timed_out is False

    @pytest.mark.asyncio
    async def test_job_timed_out_by_timeout_seconds(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should detect timeout when timeout_seconds exceeded."""
        # Job started 10 minutes ago
        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        # Timeout after 5 minutes
        config = TimeoutConfig(timeout_seconds=300)

        is_timed_out = await job_timeout_service.is_job_timed_out(job, config)

        assert is_timed_out is True

    @pytest.mark.asyncio
    async def test_job_not_timed_out_within_timeout_seconds(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should not timeout when within timeout_seconds."""
        # Job started 2 minutes ago
        started_at = datetime.now(UTC) - timedelta(minutes=2)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        # Timeout after 5 minutes
        config = TimeoutConfig(timeout_seconds=300)

        is_timed_out = await job_timeout_service.is_job_timed_out(job, config)

        assert is_timed_out is False

    @pytest.mark.asyncio
    async def test_job_timed_out_by_deadline(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should detect timeout when deadline passed."""
        started_at = datetime.now(UTC) - timedelta(hours=2)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        # Deadline was 1 hour ago
        deadline = datetime.now(UTC) - timedelta(hours=1)
        config = TimeoutConfig(deadline=deadline)

        is_timed_out = await job_timeout_service.is_job_timed_out(job, config)

        assert is_timed_out is True

    @pytest.mark.asyncio
    async def test_job_not_timed_out_before_deadline(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should not timeout when before deadline."""
        started_at = datetime.now(UTC) - timedelta(minutes=30)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        # Deadline is 1 hour from now
        deadline = datetime.now(UTC) + timedelta(hours=1)
        config = TimeoutConfig(deadline=deadline)

        is_timed_out = await job_timeout_service.is_job_timed_out(job, config)

        assert is_timed_out is False

    @pytest.mark.asyncio
    async def test_job_uses_default_timeout_when_no_config(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should use default timeout when no config provided."""
        mock_redis.get.return_value = None  # No stored config

        # Job started longer than default export timeout (30 minutes)
        started_at = datetime.now(UTC) - timedelta(minutes=35)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        is_timed_out = await job_timeout_service.is_job_timed_out(job)

        assert is_timed_out is True


class TestJobTimeoutServiceHandleTimeout:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_handle_timeout_marks_job_failed(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should mark timed-out job as failed."""
        mock_redis.get.return_value = None  # No attempts yet

        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        result = await job_timeout_service.handle_timeout(job)

        mock_job_status_service.fail_job.assert_called_once()
        call_args = mock_job_status_service.fail_job.call_args
        assert call_args[1]["job_id"] == "job-123"
        assert "timed out" in call_args[1]["error"]

    @pytest.mark.asyncio
    async def test_handle_timeout_reschedules_with_retries_remaining(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should reschedule job when retries remaining."""
        mock_redis.get.return_value = {"count": 0}  # First attempt

        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        result = await job_timeout_service.handle_timeout(job)

        assert result.was_rescheduled is True
        assert result.attempt_count == 1
        mock_job_status_service.start_job.assert_called()

    @pytest.mark.asyncio
    async def test_handle_timeout_no_reschedule_at_max_attempts(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should not reschedule when max attempts reached."""
        # Set attempt count to max - 1 (so after increment it equals max)
        mock_redis.get.return_value = {"count": DEFAULT_MAX_RETRY_ATTEMPTS - 1}

        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        result = await job_timeout_service.handle_timeout(job)

        assert result.was_rescheduled is False
        assert result.attempt_count == DEFAULT_MAX_RETRY_ATTEMPTS
        mock_job_status_service.start_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_timeout_uses_custom_max_attempts(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should use custom max attempts from config."""
        # First call returns timeout config with 1 retry
        # Second call returns attempt count of 0
        mock_redis.get.side_effect = [
            {
                "timeout_seconds": 300,
                "deadline": None,
                "max_retry_attempts": 1,
            },
            {"count": 0},  # Already had one attempt
        ]

        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        result = await job_timeout_service.handle_timeout(job)

        assert result.max_attempts == 1
        assert result.was_rescheduled is False  # 1 >= 1

    @pytest.mark.asyncio
    async def test_handle_timeout_includes_timeout_seconds_in_message(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should include timeout seconds in error message."""
        mock_redis.get.side_effect = [
            {"timeout_seconds": 300, "deadline": None, "max_retry_attempts": 3},
            {"count": 2},  # At max attempts
        ]

        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        result = await job_timeout_service.handle_timeout(job)

        assert "300 seconds" in result.error_message


class TestJobTimeoutServiceCheckForTimeouts:
    """Tests for the batch timeout checking."""

    @pytest.mark.asyncio
    async def test_check_for_timeouts_returns_empty_when_no_active_jobs(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should return empty list when no active jobs."""
        mock_redis.zrangebyscore.return_value = []

        results = await job_timeout_service.check_for_timeouts()

        assert results == []

    @pytest.mark.asyncio
    async def test_check_for_timeouts_handles_timed_out_jobs(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should handle timed-out jobs."""
        # Setup active jobs
        mock_redis.zrangebyscore.return_value = ["job-123"]

        # Job started 40 minutes ago (longer than export default of 30 min)
        started_at = datetime.now(UTC) - timedelta(minutes=40)
        mock_job_status_service.get_job_status.return_value = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        # No timeout config, so uses default
        # No attempt count
        mock_redis.get.return_value = None

        results = await job_timeout_service.check_for_timeouts()

        assert len(results) == 1
        assert results[0].job_id == "job-123"
        mock_job_status_service.fail_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_for_timeouts_skips_non_timed_out_jobs(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should skip jobs that haven't timed out."""
        mock_redis.zrangebyscore.return_value = ["job-123"]

        # Job started 5 minutes ago (within export default of 30 min)
        started_at = datetime.now(UTC) - timedelta(minutes=5)
        mock_job_status_service.get_job_status.return_value = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        mock_redis.get.return_value = None  # No config

        results = await job_timeout_service.check_for_timeouts()

        assert len(results) == 0
        mock_job_status_service.fail_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_timeouts_handles_missing_jobs(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Should handle jobs that don't exist in status service."""
        mock_redis.zrangebyscore.return_value = ["job-123", "job-456"]
        mock_job_status_service.get_job_status.side_effect = [None, None]

        results = await job_timeout_service.check_for_timeouts()

        assert len(results) == 0


class TestJobTimeoutServiceCleanup:
    """Tests for timeout data cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_timeout_data(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """Should delete timeout and attempt data."""
        await job_timeout_service.cleanup_timeout_data("job-123")

        assert mock_redis.delete.call_count == 2
        delete_calls = [call[0][0] for call in mock_redis.delete.call_args_list]
        assert "job:job-123:timeout" in delete_calls
        assert "job:job-123:attempts" in delete_calls


class TestJobTimeoutServiceSingleton:
    """Tests for singleton management."""

    def test_get_job_timeout_service_returns_singleton(self, mock_redis: AsyncMock) -> None:
        """Should return the same instance on repeated calls."""
        service1 = get_job_timeout_service(mock_redis)
        service2 = get_job_timeout_service(mock_redis)
        assert service1 is service2

    def test_reset_clears_singleton(self, mock_redis: AsyncMock) -> None:
        """Should clear the singleton on reset."""
        service1 = get_job_timeout_service(mock_redis)
        reset_job_timeout_service()
        service2 = get_job_timeout_service(mock_redis)
        assert service1 is not service2


class TestTimeoutResult:
    """Tests for TimeoutResult dataclass."""

    def test_timeout_result_creation(self) -> None:
        """Should create timeout result with all fields."""
        result = TimeoutResult(
            job_id="job-123",
            job_type="export",
            was_rescheduled=True,
            attempt_count=2,
            max_attempts=3,
            error_message="Job timed out after 300 seconds",
        )
        assert result.job_id == "job-123"
        assert result.job_type == "export"
        assert result.was_rescheduled is True
        assert result.attempt_count == 2
        assert result.max_attempts == 3
        assert "300 seconds" in result.error_message
