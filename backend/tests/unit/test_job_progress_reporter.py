"""Unit tests for job progress reporter service.

This module tests the JobProgressReporter including:
- Job start event emission
- Progress updates with throttling
- Job completion and failure events
- Duration tracking
- Context manager usage
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.websocket.event_types import WebSocketEventType
from backend.services.job_progress_reporter import (
    PROGRESS_THROTTLE_INTERVAL,
    JobProgressReporter,
    create_job_progress_reporter,
)
from backend.services.websocket_emitter import (
    WebSocketEmitterService,
    reset_emitter_state,
)


@pytest.fixture
def mock_emitter():
    """Create a mock WebSocket emitter."""
    emitter = MagicMock(spec=WebSocketEmitterService)
    emitter.emit = AsyncMock(return_value=True)
    return emitter


@pytest.fixture
def job_id():
    """Generate a unique job ID."""
    return uuid.uuid4()


@pytest.fixture
def reporter(mock_emitter, job_id):
    """Create a JobProgressReporter with mock emitter."""
    return JobProgressReporter(
        job_id=job_id,
        job_type="export",
        total_items=100,
        emitter=mock_emitter,
    )


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global emitter state before and after each test."""
    reset_emitter_state()
    yield
    reset_emitter_state()


class TestJobProgressReporterInit:
    """Tests for JobProgressReporter initialization."""

    def test_init_with_uuid(self, mock_emitter):
        """Test initialization with UUID job ID."""
        job_id = uuid.uuid4()
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="export",
            total_items=100,
            emitter=mock_emitter,
        )
        assert reporter.job_id == str(job_id)
        assert reporter.job_type == "export"
        assert reporter.total_items == 100
        assert reporter.is_started is False
        assert reporter.is_completed is False

    def test_init_with_string_id(self, mock_emitter):
        """Test initialization with string job ID."""
        reporter = JobProgressReporter(
            job_id="job-123",
            job_type="cleanup",
            total_items=50,
            emitter=mock_emitter,
        )
        assert reporter.job_id == "job-123"
        assert reporter.job_type == "cleanup"

    def test_init_with_zero_items_defaults_to_one(self, mock_emitter):
        """Test that zero total_items defaults to 1 to avoid division by zero."""
        reporter = JobProgressReporter(
            job_id="job-123",
            job_type="test",
            total_items=0,
            emitter=mock_emitter,
        )
        assert reporter.total_items == 1

    def test_init_with_negative_items_defaults_to_one(self, mock_emitter):
        """Test that negative total_items defaults to 1."""
        reporter = JobProgressReporter(
            job_id="job-123",
            job_type="test",
            total_items=-10,
            emitter=mock_emitter,
        )
        assert reporter.total_items == 1

    def test_init_without_emitter(self):
        """Test initialization without emitter (will use global)."""
        reporter = JobProgressReporter(
            job_id="job-123",
            job_type="test",
            total_items=10,
        )
        assert reporter._emitter is None


class TestJobProgressReporterCreate:
    """Tests for JobProgressReporter.create() class method."""

    @pytest.mark.asyncio
    async def test_create_with_global_emitter(self):
        """Test create() method fetches global emitter."""
        mock_emitter = MagicMock()
        mock_get_emitter = AsyncMock(return_value=mock_emitter)

        with patch(
            "backend.services.websocket_emitter.get_websocket_emitter",
            mock_get_emitter,
        ):
            reporter = await JobProgressReporter.create(
                job_id=uuid.uuid4(),
                job_type="export",
                total_items=100,
            )

            mock_get_emitter.assert_awaited_once()
            assert reporter._emitter is mock_emitter

    @pytest.mark.asyncio
    async def test_create_job_progress_reporter_function(self):
        """Test convenience function create_job_progress_reporter."""
        mock_emitter = MagicMock()
        mock_get_emitter = AsyncMock(return_value=mock_emitter)

        with patch(
            "backend.services.websocket_emitter.get_websocket_emitter",
            mock_get_emitter,
        ):
            reporter = await create_job_progress_reporter(
                job_id=uuid.uuid4(),
                job_type="cleanup",
                total_items=50,
            )

            assert reporter.job_type == "cleanup"
            assert reporter.total_items == 50


class TestJobStart:
    """Tests for job start functionality."""

    @pytest.mark.asyncio
    async def test_start_emits_job_started_event(self, reporter, mock_emitter):
        """Test start() emits job.started event."""
        await reporter.start()

        mock_emitter.emit.assert_awaited_once()
        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_STARTED
        payload = call_args[0][1]
        assert payload["job_id"] == reporter.job_id
        assert payload["job_type"] == "export"
        assert "started_at" in payload

    @pytest.mark.asyncio
    async def test_start_sets_started_flag(self, reporter, mock_emitter):
        """Test start() sets is_started flag."""
        assert reporter.is_started is False
        await reporter.start()
        assert reporter.is_started is True

    @pytest.mark.asyncio
    async def test_start_sets_started_at_timestamp(self, reporter, mock_emitter):
        """Test start() records started_at timestamp."""
        assert reporter._started_at is None
        before = datetime.now(UTC)
        await reporter.start()
        after = datetime.now(UTC)
        assert reporter._started_at is not None
        assert before <= reporter._started_at <= after

    @pytest.mark.asyncio
    async def test_start_with_estimated_duration(self, reporter, mock_emitter):
        """Test start() with estimated duration."""
        await reporter.start(estimated_duration=300)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["estimated_duration"] == 300

    @pytest.mark.asyncio
    async def test_start_with_metadata(self, reporter, mock_emitter):
        """Test start() with additional metadata."""
        await reporter.start(metadata={"filters": {"camera": "front_door"}})

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["metadata"] == {"filters": {"camera": "front_door"}}

    @pytest.mark.asyncio
    async def test_start_twice_raises_runtime_error(self, reporter, mock_emitter):
        """Test starting twice raises RuntimeError."""
        await reporter.start()

        with pytest.raises(RuntimeError, match="has already been started"):
            await reporter.start()


class TestProgressReporting:
    """Tests for progress reporting functionality."""

    @pytest.mark.asyncio
    async def test_report_progress_emits_event(self, reporter, mock_emitter):
        """Test report_progress() emits job.progress event."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        emitted = await reporter.report_progress(50)

        assert emitted is True
        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_PROGRESS
        payload = call_args[0][1]
        assert payload["job_id"] == reporter.job_id
        assert payload["progress"] == 50
        assert payload["status"] == "running"

    @pytest.mark.asyncio
    async def test_report_progress_with_current_step(self, reporter, mock_emitter):
        """Test report_progress() includes current step message."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(25, current_step="Processing batch 1 of 4")

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["message"] == "Processing batch 1 of 4"

    @pytest.mark.asyncio
    async def test_report_progress_calculates_percentage(self, reporter, mock_emitter):
        """Test progress percentage is calculated correctly."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        # 50 items of 100 = 50%
        await reporter.report_progress(50)
        assert mock_emitter.emit.call_args[0][1]["progress"] == 50

    @pytest.mark.asyncio
    async def test_report_progress_caps_at_100(self, reporter, mock_emitter):
        """Test progress is capped at 100%."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        # More items than total
        await reporter.report_progress(200)
        assert mock_emitter.emit.call_args[0][1]["progress"] == 100

    @pytest.mark.asyncio
    async def test_report_progress_throttled(self, reporter, mock_emitter):
        """Test progress updates are throttled."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        # First update should emit
        result1 = await reporter.report_progress(10)
        assert result1 is True
        assert mock_emitter.emit.call_count == 1

        # Second update immediately after should be throttled
        result2 = await reporter.report_progress(11)
        assert result2 is False
        assert mock_emitter.emit.call_count == 1

    @pytest.mark.asyncio
    async def test_report_progress_emits_after_throttle_interval(self, reporter, mock_emitter):
        """Test progress emits after throttle interval passes."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(10)
        assert mock_emitter.emit.call_count == 1

        # Simulate time passing by manipulating last progress time
        reporter._last_progress_time = time.monotonic() - PROGRESS_THROTTLE_INTERVAL - 0.1

        result = await reporter.report_progress(20)
        assert result is True
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_report_progress_emits_on_large_progress_jump(self, reporter, mock_emitter):
        """Test progress emits when progress jumps 10% or more."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        # First update
        await reporter.report_progress(10)
        assert mock_emitter.emit.call_count == 1

        # Jump from 10% to 25% (15% jump) should emit even if throttled
        result = await reporter.report_progress(25)
        assert result is True
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_report_progress_force_bypasses_throttle(self, reporter, mock_emitter):
        """Test force=True bypasses throttling."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(10)
        assert mock_emitter.emit.call_count == 1

        # Forced update should emit even if throttled
        result = await reporter.report_progress(11, force=True)
        assert result is True
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_report_progress_before_start_raises_error(self, reporter, mock_emitter):
        """Test report_progress before start raises RuntimeError."""
        with pytest.raises(RuntimeError, match="has not been started"):
            await reporter.report_progress(50)

    @pytest.mark.asyncio
    async def test_report_progress_after_complete_raises_error(self, reporter, mock_emitter):
        """Test report_progress after completion raises RuntimeError."""
        await reporter.start()
        await reporter.complete()

        with pytest.raises(RuntimeError, match="has already completed"):
            await reporter.report_progress(50)


class TestJobCompletion:
    """Tests for job completion functionality."""

    @pytest.mark.asyncio
    async def test_complete_emits_job_completed_event(self, reporter, mock_emitter):
        """Test complete() emits job.completed event."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.complete()

        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_COMPLETED
        payload = call_args[0][1]
        assert payload["job_id"] == reporter.job_id
        assert payload["job_type"] == "export"
        assert "completed_at" in payload
        assert "duration_seconds" in payload

    @pytest.mark.asyncio
    async def test_complete_with_result_summary(self, reporter, mock_emitter):
        """Test complete() includes result summary."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.complete(result_summary={"items_exported": 100, "file_size": 1024})

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["result"] == {"items_exported": 100, "file_size": 1024}

    @pytest.mark.asyncio
    async def test_complete_sets_completed_flag(self, reporter, mock_emitter):
        """Test complete() sets is_completed flag."""
        await reporter.start()
        assert reporter.is_completed is False
        await reporter.complete()
        assert reporter.is_completed is True

    @pytest.mark.asyncio
    async def test_complete_calculates_duration(self, reporter, mock_emitter):
        """Test complete() calculates job duration."""
        await reporter.start()

        # Simulate some time passing
        await asyncio.sleep(0.01)

        await reporter.complete()

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["duration_seconds"] is not None
        assert payload["duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_complete_before_start_raises_error(self, reporter, mock_emitter):
        """Test complete() before start raises RuntimeError."""
        with pytest.raises(RuntimeError, match="has not been started"):
            await reporter.complete()

    @pytest.mark.asyncio
    async def test_complete_twice_raises_error(self, reporter, mock_emitter):
        """Test completing twice raises RuntimeError."""
        await reporter.start()
        await reporter.complete()

        with pytest.raises(RuntimeError, match="has already completed"):
            await reporter.complete()


class TestJobFailure:
    """Tests for job failure functionality."""

    @pytest.mark.asyncio
    async def test_fail_emits_job_failed_event(self, reporter, mock_emitter):
        """Test fail() emits job.failed event."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.fail("Database connection lost")

        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_FAILED
        payload = call_args[0][1]
        assert payload["job_id"] == reporter.job_id
        assert payload["job_type"] == "export"
        assert payload["error"] == "Database connection lost"
        assert "failed_at" in payload

    @pytest.mark.asyncio
    async def test_fail_with_exception(self, reporter, mock_emitter):
        """Test fail() with exception object."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.fail(ValueError("Invalid data format"))

        payload = mock_emitter.emit.call_args[0][1]
        assert "ValueError: Invalid data format" in payload["error"]

    @pytest.mark.asyncio
    async def test_fail_with_retryable_flag(self, reporter, mock_emitter):
        """Test fail() with retryable flag."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.fail("Timeout error", retryable=True)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["retryable"] is True

    @pytest.mark.asyncio
    async def test_fail_with_error_code(self, reporter, mock_emitter):
        """Test fail() with error code."""
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.fail("Connection refused", error_code="CONN_REFUSED")

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["error_code"] == "CONN_REFUSED"

    @pytest.mark.asyncio
    async def test_fail_sets_completed_flag(self, reporter, mock_emitter):
        """Test fail() sets is_completed flag."""
        await reporter.start()
        assert reporter.is_completed is False
        await reporter.fail("Error")
        assert reporter.is_completed is True

    @pytest.mark.asyncio
    async def test_fail_before_start_raises_error(self, reporter, mock_emitter):
        """Test fail() before start raises RuntimeError."""
        with pytest.raises(RuntimeError, match="has not been started"):
            await reporter.fail("Error")

    @pytest.mark.asyncio
    async def test_fail_after_complete_raises_error(self, reporter, mock_emitter):
        """Test fail() after completion raises RuntimeError."""
        await reporter.start()
        await reporter.complete()

        with pytest.raises(RuntimeError, match="has already completed"):
            await reporter.fail("Error")


class TestDurationTracking:
    """Tests for duration tracking functionality."""

    def test_duration_before_start_is_none(self, reporter):
        """Test duration_seconds is None before start."""
        assert reporter.duration_seconds is None

    @pytest.mark.asyncio
    async def test_duration_after_start(self, reporter, mock_emitter):
        """Test duration_seconds after start."""
        await reporter.start()
        await asyncio.sleep(0.01)

        duration = reporter.duration_seconds
        assert duration is not None
        assert duration > 0


class TestContextManager:
    """Tests for async context manager usage."""

    @pytest.mark.asyncio
    async def test_context_manager_starts_job(self, mock_emitter, job_id):
        """Test context manager starts job on entry."""
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="export",
            total_items=10,
            emitter=mock_emitter,
        )

        async with reporter:
            assert reporter.is_started is True

    @pytest.mark.asyncio
    async def test_context_manager_completes_job(self, mock_emitter, job_id):
        """Test context manager completes job on normal exit."""
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="export",
            total_items=10,
            emitter=mock_emitter,
        )

        async with reporter:
            pass

        assert reporter.is_completed is True
        # Verify JOB_COMPLETED was emitted (last call)
        last_call = mock_emitter.emit.call_args_list[-1]
        assert last_call[0][0] == WebSocketEventType.JOB_COMPLETED

    @pytest.mark.asyncio
    async def test_context_manager_fails_job_on_exception(self, mock_emitter, job_id):
        """Test context manager fails job on exception."""
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="export",
            total_items=10,
            emitter=mock_emitter,
        )

        with pytest.raises(ValueError, match="Test error"):
            async with reporter:
                raise ValueError("Test error")

        assert reporter.is_completed is True
        # Verify JOB_FAILED was emitted
        last_call = mock_emitter.emit.call_args_list[-1]
        assert last_call[0][0] == WebSocketEventType.JOB_FAILED
        assert "ValueError: Test error" in last_call[0][1]["error"]

    @pytest.mark.asyncio
    async def test_context_manager_does_not_suppress_exceptions(self, mock_emitter, job_id):
        """Test context manager propagates exceptions."""
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="export",
            total_items=10,
            emitter=mock_emitter,
        )

        with pytest.raises(ValueError):
            async with reporter:
                raise ValueError("Should propagate")

    @pytest.mark.asyncio
    async def test_context_manager_with_manual_complete(self, mock_emitter, job_id):
        """Test context manager with manual completion inside block."""
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="export",
            total_items=10,
            emitter=mock_emitter,
        )

        async with reporter:
            await reporter.complete(result_summary={"manual": True})

        # Should not double-complete
        assert reporter.is_completed is True
        # Should only have one JOB_COMPLETED event (from manual complete)
        completed_calls = [
            call
            for call in mock_emitter.emit.call_args_list
            if call[0][0] == WebSocketEventType.JOB_COMPLETED
        ]
        assert len(completed_calls) == 1


class TestEmitterLazyLoading:
    """Tests for lazy emitter loading functionality."""

    @pytest.mark.asyncio
    async def test_emitter_fetched_on_first_use(self):
        """Test emitter is fetched lazily when not provided."""
        reporter = JobProgressReporter(
            job_id="test-123",
            job_type="test",
            total_items=10,
            emitter=None,
        )

        mock_emitter = MagicMock()
        mock_emitter.emit = AsyncMock(return_value=True)
        mock_get_emitter = AsyncMock(return_value=mock_emitter)

        with patch(
            "backend.services.websocket_emitter.get_websocket_emitter",
            mock_get_emitter,
        ):
            await reporter.start()

            mock_get_emitter.assert_awaited_once()
            assert reporter._emitter is mock_emitter


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_reporter_with_large_total_items(self, mock_emitter):
        """Test reporter handles large total_items correctly."""
        reporter = JobProgressReporter(
            job_id="test-123",
            job_type="export",
            total_items=1_000_000,
            emitter=mock_emitter,
        )

        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(500_000)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["progress"] == 50

    @pytest.mark.asyncio
    async def test_reporter_with_one_item(self, mock_emitter):
        """Test reporter handles single item correctly."""
        reporter = JobProgressReporter(
            job_id="test-123",
            job_type="export",
            total_items=1,
            emitter=mock_emitter,
        )

        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(1)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["progress"] == 100

    @pytest.mark.asyncio
    async def test_multiple_reporters_independent(self, mock_emitter):
        """Test multiple reporters are independent."""
        reporter1 = JobProgressReporter(
            job_id="job-1",
            job_type="export",
            total_items=100,
            emitter=mock_emitter,
        )
        reporter2 = JobProgressReporter(
            job_id="job-2",
            job_type="cleanup",
            total_items=50,
            emitter=mock_emitter,
        )

        await reporter1.start()
        await reporter2.start()

        assert reporter1.is_started is True
        assert reporter2.is_started is True
        assert reporter1.job_id != reporter2.job_id

        await reporter1.complete()
        assert reporter1.is_completed is True
        assert reporter2.is_completed is False


class TestProgressThrottleInterval:
    """Tests for the progress throttle interval constant."""

    def test_throttle_interval_is_one_second(self):
        """Test throttle interval is set to 1 second."""
        assert PROGRESS_THROTTLE_INTERVAL == 1.0
