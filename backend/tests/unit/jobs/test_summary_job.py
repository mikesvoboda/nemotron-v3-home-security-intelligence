"""Unit tests for the SummaryJob.

This module contains comprehensive unit tests for the SummaryJob,
which generates hourly and daily dashboard summaries using the SummaryGenerator.

Related Issues:
    - NEM-2891: Create scheduled job for generating summaries

Test Organization:
    - SummaryJob initialization tests
    - Job execution tests
    - Timeout handling tests
    - Cache invalidation tests
    - WebSocket broadcast tests
    - Scheduler tests
    - Singleton management tests
    - Error handling tests
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_summary():
    """Create a mock Summary object."""
    summary = MagicMock()
    summary.id = 1
    summary.content = "Test summary content"
    summary.event_count = 2
    summary.window_start = datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC)
    summary.window_end = datetime(2026, 1, 18, 15, 0, 0, tzinfo=UTC)
    summary.generated_at = datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)
    return summary


@pytest.fixture
def mock_generator(mock_summary):
    """Create a mock SummaryGenerator."""
    generator = MagicMock()
    generator.generate_all_summaries = AsyncMock(
        return_value={"hourly": mock_summary, "daily": mock_summary}
    )
    return generator


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = MagicMock()
    client.delete = AsyncMock(return_value=1)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_broadcaster():
    """Create a mock EventBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.broadcast_summary_update = AsyncMock(return_value=5)
    return broadcaster


@pytest.fixture
def mock_cache_service(mock_redis_client):
    """Create a mock CacheService."""
    from backend.services.cache_service import CacheService

    with patch.object(CacheService, "__init__", lambda _self, _redis: None):
        service = CacheService(mock_redis_client)
        service._redis = mock_redis_client
        service.invalidate = AsyncMock(return_value=True)
        return service


# =============================================================================
# SummaryJob Initialization Tests
# =============================================================================


class TestSummaryJobInitialization:
    """Tests for SummaryJob initialization."""

    def test_default_initialization(self, mock_generator):
        """Test job initializes with default values."""
        from backend.jobs.summary_job import DEFAULT_TIMEOUT_SECONDS, SummaryJob

        with patch("backend.jobs.summary_job.get_summary_generator", return_value=mock_generator):
            job = SummaryJob()

        assert job._timeout == DEFAULT_TIMEOUT_SECONDS
        assert job._redis_client is None
        assert job._broadcaster is None

    def test_custom_initialization(self, mock_generator, mock_redis_client, mock_broadcaster):
        """Test job with custom configuration."""
        from backend.jobs.summary_job import SummaryJob

        job = SummaryJob(
            generator=mock_generator,
            redis_client=mock_redis_client,
            broadcaster=mock_broadcaster,
            timeout=30.0,
        )

        assert job._generator is mock_generator
        assert job._redis_client is mock_redis_client
        assert job._broadcaster is mock_broadcaster
        assert job._timeout == 30.0


# =============================================================================
# Job Execution Tests
# =============================================================================


class TestSummaryJobExecution:
    """Tests for SummaryJob.run() method."""

    @pytest.mark.asyncio
    async def test_run_success(self, mock_generator, mock_summary):
        """Test successful job execution."""
        from backend.jobs.summary_job import SummaryJob

        job = SummaryJob(generator=mock_generator)
        result = await job.run()

        assert result["success"] is True
        assert result["hourly_event_count"] == 2
        assert result["daily_event_count"] == 2
        mock_generator.generate_all_summaries.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_calls_generator(self, mock_generator):
        """Test that run() calls generate_all_summaries()."""
        from backend.jobs.summary_job import SummaryJob

        job = SummaryJob(generator=mock_generator)
        await job.run()

        mock_generator.generate_all_summaries.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_handles_no_summaries(self, mock_generator):
        """Test run handles case when no summaries are generated."""
        from backend.jobs.summary_job import SummaryJob

        mock_generator.generate_all_summaries.return_value = {
            "hourly": None,
            "daily": None,
        }

        job = SummaryJob(generator=mock_generator)
        result = await job.run()

        assert result["success"] is True
        assert result["hourly_event_count"] == 0
        assert result["daily_event_count"] == 0


# =============================================================================
# Timeout Handling Tests
# =============================================================================


class TestTimeoutHandling:
    """Tests for timeout behavior."""

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, mock_generator):
        """Test that timeout raises TimeoutError."""
        from backend.jobs.summary_job import SummaryJob

        # Make generator hang
        async def slow_generate():
            await asyncio.sleep(10)
            return {"hourly": None, "daily": None}

        mock_generator.generate_all_summaries = slow_generate

        job = SummaryJob(generator=mock_generator, timeout=0.1)

        with pytest.raises(TimeoutError):
            await job.run()

    @pytest.mark.asyncio
    async def test_timeout_logs_error(self, mock_generator):
        """Test that timeout is logged properly."""
        from backend.jobs.summary_job import SummaryJob

        async def slow_generate():
            await asyncio.sleep(10)
            return {"hourly": None, "daily": None}

        mock_generator.generate_all_summaries = slow_generate

        job = SummaryJob(generator=mock_generator, timeout=0.1)

        with patch("backend.jobs.summary_job.logger") as mock_logger:
            with pytest.raises(TimeoutError):
                await job.run()

            # Verify error was logged
            mock_logger.error.assert_called()


# =============================================================================
# Cache Invalidation Tests
# =============================================================================


class TestCacheInvalidation:
    """Tests for cache invalidation behavior."""

    @pytest.mark.asyncio
    async def test_cache_invalidation_called(self, mock_generator, mock_redis_client):
        """Test that cache is invalidated after summary generation."""
        from backend.jobs.summary_job import SummaryJob

        with patch("backend.jobs.summary_job.CacheService") as MockCacheService:
            mock_cache = MagicMock()
            mock_cache.invalidate = AsyncMock(return_value=True)
            MockCacheService.return_value = mock_cache

            job = SummaryJob(
                generator=mock_generator,
                redis_client=mock_redis_client,
            )
            result = await job.run()

            # Should have tried to invalidate all 3 cache keys
            assert mock_cache.invalidate.call_count == 3
            assert result["cache_invalidated"] == 3

    @pytest.mark.asyncio
    async def test_cache_invalidation_handles_failure(self, mock_generator, mock_redis_client):
        """Test that cache invalidation failure doesn't stop the job."""
        from backend.jobs.summary_job import SummaryJob

        with patch("backend.jobs.summary_job.CacheService") as MockCacheService:
            mock_cache = MagicMock()
            mock_cache.invalidate = AsyncMock(side_effect=Exception("Redis error"))
            MockCacheService.return_value = mock_cache

            job = SummaryJob(
                generator=mock_generator,
                redis_client=mock_redis_client,
            )
            # Should not raise - cache failures are handled gracefully
            result = await job.run()

            assert result["success"] is True
            assert result["cache_invalidated"] == 0

    @pytest.mark.asyncio
    async def test_no_cache_invalidation_without_redis(self, mock_generator):
        """Test that no cache invalidation happens without Redis client."""
        from backend.jobs.summary_job import SummaryJob

        job = SummaryJob(generator=mock_generator, redis_client=None)
        result = await job.run()

        assert result["success"] is True
        assert result["cache_invalidated"] == 0


# =============================================================================
# WebSocket Broadcast Tests
# =============================================================================


class TestWebSocketBroadcast:
    """Tests for WebSocket broadcast behavior."""

    @pytest.mark.asyncio
    async def test_broadcast_called(self, mock_generator, mock_broadcaster, mock_summary):
        """Test that broadcast is called after summary generation."""
        from backend.jobs.summary_job import SummaryJob

        job = SummaryJob(
            generator=mock_generator,
            broadcaster=mock_broadcaster,
        )
        await job.run()

        mock_broadcaster.broadcast_summary_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_receives_summary_data(
        self, mock_generator, mock_broadcaster, mock_summary
    ):
        """Test that broadcast receives properly formatted summary data."""
        from backend.jobs.summary_job import SummaryJob

        job = SummaryJob(
            generator=mock_generator,
            broadcaster=mock_broadcaster,
        )
        await job.run()

        # Verify the broadcast was called with hourly and daily data
        call_kwargs = mock_broadcaster.broadcast_summary_update.call_args.kwargs
        assert "hourly" in call_kwargs
        assert "daily" in call_kwargs
        # Check hourly data has expected fields
        hourly_data = call_kwargs["hourly"]
        assert hourly_data["id"] == 1
        assert hourly_data["content"] == "Test summary content"
        assert hourly_data["event_count"] == 2

    @pytest.mark.asyncio
    async def test_broadcast_handles_failure(self, mock_generator, mock_broadcaster):
        """Test that broadcast failure doesn't stop the job."""
        from backend.jobs.summary_job import SummaryJob

        mock_broadcaster.broadcast_summary_update.side_effect = Exception("WebSocket error")

        job = SummaryJob(
            generator=mock_generator,
            broadcaster=mock_broadcaster,
        )
        # Should not raise - broadcast failures are handled gracefully
        result = await job.run()

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_no_broadcast_without_broadcaster(self, mock_generator):
        """Test that no broadcast happens without broadcaster."""
        from backend.jobs.summary_job import SummaryJob

        job = SummaryJob(generator=mock_generator, broadcaster=None)
        result = await job.run()

        assert result["success"] is True


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling behavior."""

    @pytest.mark.asyncio
    async def test_generator_error_raises(self, mock_generator):
        """Test that generator errors are raised."""
        from backend.jobs.summary_job import SummaryJob

        mock_generator.generate_all_summaries.side_effect = Exception("LLM error")

        job = SummaryJob(generator=mock_generator)

        with pytest.raises(Exception, match="LLM error"):
            await job.run()

    @pytest.mark.asyncio
    async def test_generator_error_logged(self, mock_generator):
        """Test that generator errors are logged."""
        from backend.jobs.summary_job import SummaryJob

        mock_generator.generate_all_summaries.side_effect = Exception("LLM error")

        job = SummaryJob(generator=mock_generator)

        with patch("backend.jobs.summary_job.logger") as mock_logger:
            with pytest.raises(Exception):
                await job.run()

            mock_logger.error.assert_called()


# =============================================================================
# Scheduler Tests
# =============================================================================


class TestSummaryJobScheduler:
    """Tests for the SummaryJobScheduler."""

    def test_scheduler_initialization(self):
        """Test scheduler initializes with correct values."""
        from backend.jobs.summary_job import (
            DEFAULT_INTERVAL_MINUTES,
            DEFAULT_TIMEOUT_SECONDS,
            SummaryJobScheduler,
        )

        scheduler = SummaryJobScheduler()

        assert scheduler.interval_minutes == DEFAULT_INTERVAL_MINUTES
        assert scheduler._timeout == DEFAULT_TIMEOUT_SECONDS
        assert scheduler.is_running is False

    def test_scheduler_custom_config(self, mock_redis_client, mock_broadcaster):
        """Test scheduler with custom configuration."""
        from backend.jobs.summary_job import SummaryJobScheduler

        scheduler = SummaryJobScheduler(
            interval_minutes=10,
            redis_client=mock_redis_client,
            broadcaster=mock_broadcaster,
            timeout=120.0,
        )

        assert scheduler.interval_minutes == 10
        assert scheduler._redis_client is mock_redis_client
        assert scheduler._broadcaster is mock_broadcaster
        assert scheduler._timeout == 120.0

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """Test scheduler start and stop lifecycle."""
        from backend.jobs.summary_job import SummaryJobScheduler

        scheduler = SummaryJobScheduler(interval_minutes=60)

        # Mock the job loop to avoid actual execution
        scheduler._job_loop = AsyncMock()

        await scheduler.start()
        assert scheduler.is_running is True

        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_scheduler_start_idempotent(self):
        """Test that starting an already running scheduler is safe."""
        from backend.jobs.summary_job import SummaryJobScheduler

        scheduler = SummaryJobScheduler(interval_minutes=60)
        scheduler._job_loop = AsyncMock()

        await scheduler.start()
        # Second start should be a no-op
        await scheduler.start()

        assert scheduler.is_running is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop_when_not_running(self):
        """Test stop is safe when scheduler is not running."""
        from backend.jobs.summary_job import SummaryJobScheduler

        scheduler = SummaryJobScheduler()

        # Should not raise
        await scheduler.stop()

        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_scheduler_run_once(self, mock_generator, mock_summary):
        """Test run_once method for manual triggering."""
        from backend.jobs.summary_job import SummaryJobScheduler

        with patch("backend.jobs.summary_job.get_summary_generator", return_value=mock_generator):
            scheduler = SummaryJobScheduler()
            result = await scheduler.run_once()

        assert result["success"] is True
        mock_generator.generate_all_summaries.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scheduler_context_manager(self):
        """Test scheduler as async context manager."""
        from backend.jobs.summary_job import SummaryJobScheduler

        async with SummaryJobScheduler(interval_minutes=60) as scheduler:
            scheduler._job_loop = AsyncMock()
            # In context, should start
            # Note: We mock _job_loop after entering context, so start() was already called
            # Just verify we're in a valid state
            pass

        # After context, should be stopped
        assert scheduler.is_running is False


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSchedulerSingleton:
    """Tests for scheduler singleton management."""

    def test_get_scheduler_returns_singleton(self):
        """Test get_summary_job_scheduler returns same instance."""
        from backend.jobs.summary_job import (
            get_summary_job_scheduler,
            reset_summary_job_scheduler,
        )

        reset_summary_job_scheduler()

        scheduler1 = get_summary_job_scheduler()
        scheduler2 = get_summary_job_scheduler()

        assert scheduler1 is scheduler2

        reset_summary_job_scheduler()

    def test_reset_clears_singleton(self):
        """Test reset_summary_job_scheduler clears the singleton."""
        from backend.jobs.summary_job import (
            get_summary_job_scheduler,
            reset_summary_job_scheduler,
        )

        scheduler1 = get_summary_job_scheduler()
        reset_summary_job_scheduler()
        scheduler2 = get_summary_job_scheduler()

        assert scheduler1 is not scheduler2

        reset_summary_job_scheduler()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    @pytest.mark.asyncio
    async def test_invalidate_summary_cache(self):
        """Test invalidate_summary_cache function."""
        from backend.jobs.summary_job import invalidate_summary_cache

        mock_cache = MagicMock()
        mock_cache.invalidate = AsyncMock(return_value=True)

        result = await invalidate_summary_cache(mock_cache)

        assert result == 3  # All 3 keys invalidated
        assert mock_cache.invalidate.call_count == 3

    @pytest.mark.asyncio
    async def test_invalidate_summary_cache_partial_failure(self):
        """Test invalidate_summary_cache with partial failures."""
        from backend.jobs.summary_job import invalidate_summary_cache

        mock_cache = MagicMock()
        # First call succeeds, second fails, third succeeds
        mock_cache.invalidate = AsyncMock(side_effect=[True, False, True])

        result = await invalidate_summary_cache(mock_cache)

        assert result == 2  # Only 2 keys were invalidated

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_success(self, mock_broadcaster, mock_summary):
        """Test broadcast_summary_update function."""
        from backend.jobs.summary_job import broadcast_summary_update

        summaries = {"hourly": mock_summary, "daily": mock_summary}

        result = await broadcast_summary_update(mock_broadcaster, summaries)

        assert result == 5  # Mock returns 5 subscribers
        mock_broadcaster.broadcast_summary_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_handles_none_summaries(self, mock_broadcaster):
        """Test broadcast_summary_update with None summaries."""
        from backend.jobs.summary_job import broadcast_summary_update

        summaries = {"hourly": None, "daily": None}

        result = await broadcast_summary_update(mock_broadcaster, summaries)

        # Should still call broadcast with None values
        call_kwargs = mock_broadcaster.broadcast_summary_update.call_args.kwargs
        assert call_kwargs["hourly"] is None
        assert call_kwargs["daily"] is None

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_handles_error(self, mock_broadcaster, mock_summary):
        """Test broadcast_summary_update returns 0 on error."""
        from backend.jobs.summary_job import broadcast_summary_update

        mock_broadcaster.broadcast_summary_update.side_effect = Exception("Error")
        summaries = {"hourly": mock_summary, "daily": mock_summary}

        result = await broadcast_summary_update(mock_broadcaster, summaries)

        assert result == 0


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_job_type_constant(self):
        """Test JOB_TYPE_GENERATE_SUMMARIES constant."""
        from backend.jobs.summary_job import JOB_TYPE_GENERATE_SUMMARIES

        assert JOB_TYPE_GENERATE_SUMMARIES == "generate_summaries"

    def test_default_values(self):
        """Test default configuration values."""
        from backend.jobs.summary_job import (
            DEFAULT_INTERVAL_MINUTES,
            DEFAULT_TIMEOUT_SECONDS,
        )

        assert DEFAULT_INTERVAL_MINUTES == 5
        assert DEFAULT_TIMEOUT_SECONDS == 60

    def test_cache_keys(self):
        """Test SUMMARY_CACHE_KEYS matches route keys."""
        from backend.jobs.summary_job import SUMMARY_CACHE_KEYS

        assert "summaries:latest" in SUMMARY_CACHE_KEYS
        assert "summaries:hourly" in SUMMARY_CACHE_KEYS
        assert "summaries:daily" in SUMMARY_CACHE_KEYS
        assert len(SUMMARY_CACHE_KEYS) == 3
