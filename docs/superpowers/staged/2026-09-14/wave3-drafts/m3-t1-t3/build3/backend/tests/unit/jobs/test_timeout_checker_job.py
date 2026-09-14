"""Tests for the timeout checker background job.

This module tests the TimeoutCheckerJob which periodically checks
for and handles timed-out jobs.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.jobs.timeout_checker_job import (
    DEFAULT_CHECK_INTERVAL_SECONDS,
    TimeoutCheckerJob,
    get_timeout_checker_job,
    reset_timeout_checker_job,
)
from backend.services.job_timeout_service import JobTimeoutService, TimeoutResult


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    return AsyncMock()


@pytest.fixture
def mock_timeout_service() -> AsyncMock:
    """Create a mock job timeout service."""
    service = AsyncMock(spec=JobTimeoutService)
    service.check_for_timeouts = AsyncMock(return_value=[])
    return service


@pytest.fixture
def timeout_checker(
    mock_redis: AsyncMock,
    mock_timeout_service: AsyncMock,
) -> TimeoutCheckerJob:
    """Create a timeout checker job with mocks."""
    return TimeoutCheckerJob(
        redis_client=mock_redis,
        timeout_service=mock_timeout_service,
        check_interval=1,  # Use short interval for testing
    )


@pytest.fixture(autouse=True)
def cleanup_singleton() -> None:
    """Reset the timeout checker singleton after each test."""
    yield
    reset_timeout_checker_job()


class TestTimeoutCheckerJobProperties:
    """Tests for TimeoutCheckerJob properties."""

    def test_check_interval_property(self, timeout_checker: TimeoutCheckerJob) -> None:
        """Should return configured check interval."""
        assert timeout_checker.check_interval == 1

    def test_default_check_interval(self, mock_redis: AsyncMock) -> None:
        """Should use default check interval when not specified."""
        checker = TimeoutCheckerJob(redis_client=mock_redis)
        assert checker.check_interval == DEFAULT_CHECK_INTERVAL_SECONDS

    def test_is_running_initially_false(self, timeout_checker: TimeoutCheckerJob) -> None:
        """Should be not running initially."""
        assert timeout_checker.is_running is False


class TestTimeoutCheckerJobStartStop:
    """Tests for starting and stopping the checker."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, timeout_checker: TimeoutCheckerJob) -> None:
        """Should set running flag when started."""
        await timeout_checker.start()

        try:
            assert timeout_checker.is_running is True
        finally:
            await timeout_checker.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, timeout_checker: TimeoutCheckerJob) -> None:
        """Should clear running flag when stopped."""
        await timeout_checker.start()
        await timeout_checker.stop()

        assert timeout_checker.is_running is False

    @pytest.mark.asyncio
    async def test_start_is_idempotent(
        self, timeout_checker: TimeoutCheckerJob, mock_timeout_service: AsyncMock
    ) -> None:
        """Should be safe to call start multiple times."""
        await timeout_checker.start()
        await timeout_checker.start()  # Should not raise

        try:
            assert timeout_checker.is_running is True
        finally:
            await timeout_checker.stop()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self, timeout_checker: TimeoutCheckerJob) -> None:
        """Should be safe to call stop multiple times."""
        await timeout_checker.start()
        await timeout_checker.stop()
        await timeout_checker.stop()  # Should not raise

        assert timeout_checker.is_running is False


class TestTimeoutCheckerJobExecution:
    """Tests for timeout check execution."""

    @pytest.mark.asyncio
    async def test_run_once_calls_timeout_service(
        self, timeout_checker: TimeoutCheckerJob, mock_timeout_service: AsyncMock
    ) -> None:
        """Should call timeout service check_for_timeouts."""
        mock_timeout_service.check_for_timeouts.return_value = []

        count = await timeout_checker.run_once()

        mock_timeout_service.check_for_timeouts.assert_called_once()
        assert count == 0

    @pytest.mark.asyncio
    async def test_run_once_returns_handled_count(
        self, timeout_checker: TimeoutCheckerJob, mock_timeout_service: AsyncMock
    ) -> None:
        """Should return number of handled jobs."""
        mock_timeout_service.check_for_timeouts.return_value = [
            TimeoutResult(
                job_id="job-1",
                job_type="export",
                was_rescheduled=True,
                attempt_count=1,
                max_attempts=3,
                error_message="Timed out",
            ),
            TimeoutResult(
                job_id="job-2",
                job_type="cleanup",
                was_rescheduled=False,
                attempt_count=3,
                max_attempts=3,
                error_message="Timed out",
            ),
        ]

        count = await timeout_checker.run_once()

        assert count == 2

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # Prevent hanging if something goes wrong
    async def test_loop_executes_periodically(
        self, mock_redis: AsyncMock, mock_timeout_service: AsyncMock
    ) -> None:
        """Should execute checks periodically in the loop."""
        # Use very short interval for test
        checker = TimeoutCheckerJob(
            redis_client=mock_redis,
            timeout_service=mock_timeout_service,
            check_interval=0,  # No sleep between checks
        )

        mock_timeout_service.check_for_timeouts.return_value = []

        await checker.start()

        # Wait for at least one check to complete
        await asyncio.sleep(0.1)

        await checker.stop()

        # Should have been called at least once
        assert mock_timeout_service.check_for_timeouts.call_count >= 1


class TestTimeoutCheckerJobErrorHandling:
    """Tests for error handling in the checker."""

    @pytest.mark.asyncio
    async def test_run_once_propagates_errors(
        self, timeout_checker: TimeoutCheckerJob, mock_timeout_service: AsyncMock
    ) -> None:
        """Should propagate errors from timeout service."""
        mock_timeout_service.check_for_timeouts.side_effect = RuntimeError("Test error")

        with pytest.raises(RuntimeError, match="Test error"):
            await timeout_checker.run_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_loop_continues_after_error(
        self, mock_redis: AsyncMock, mock_timeout_service: AsyncMock
    ) -> None:
        """Should continue loop after an error."""
        checker = TimeoutCheckerJob(
            redis_client=mock_redis,
            timeout_service=mock_timeout_service,
            check_interval=0,
        )

        # First call raises error, subsequent calls succeed
        mock_timeout_service.check_for_timeouts.side_effect = [
            RuntimeError("Test error"),
            [],
            [],
        ]

        await checker.start()
        await asyncio.sleep(0.1)
        await checker.stop()

        # Should have recovered and called multiple times
        assert mock_timeout_service.check_for_timeouts.call_count >= 2


class TestTimeoutCheckerJobSingleton:
    """Tests for singleton management."""

    def test_get_timeout_checker_job_returns_singleton(self, mock_redis: AsyncMock) -> None:
        """Should return the same instance on repeated calls."""
        checker1 = get_timeout_checker_job(mock_redis)
        checker2 = get_timeout_checker_job(mock_redis)
        assert checker1 is checker2

    def test_reset_clears_singleton(self, mock_redis: AsyncMock) -> None:
        """Should clear the singleton on reset."""
        checker1 = get_timeout_checker_job(mock_redis)
        reset_timeout_checker_job()
        checker2 = get_timeout_checker_job(mock_redis)
        assert checker1 is not checker2

    @pytest.mark.asyncio
    async def test_reset_stops_running_checker(self, mock_redis: AsyncMock) -> None:
        """Should stop the checker if running when reset."""
        checker = get_timeout_checker_job(mock_redis, check_interval=10)
        await checker.start()

        assert checker.is_running is True

        reset_timeout_checker_job()

        # Checker should be stopped
        assert checker.is_running is False
