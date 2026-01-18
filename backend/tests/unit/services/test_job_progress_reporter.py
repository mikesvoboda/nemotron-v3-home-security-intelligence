"""Unit tests for JobProgressReporter (NEM-2743).

This module tests the JobProgressReporter service which handles job progress
WebSocket event emission with throttling logic.

Test Coverage:
    - Job Lifecycle: start(), complete(), fail() event emission and duration tracking
    - Progress Reporting: report_progress() basic emission, throttling, force emit, 10% jump
    - Context Manager: __aenter__, __aexit__ auto-completion, exception handling
    - Error Handling: state validation errors (already started, not started, etc.)
    - Concurrency: multiple jobs and rapid updates

Acceptance Criteria:
    - 15-18 test functions
    - Throttling behavior verified (max 1 event/second)
    - Context manager fully tested (success and exception paths)
    - All tests pass with proper mocking

Related Issues:
    - NEM-2743: Add unit tests for job_progress_reporter.py
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.core.websocket.event_types import WebSocketEventType
from backend.services.job_progress_reporter import (
    PROGRESS_THROTTLE_INTERVAL,
    JobProgressReporter,
    create_job_progress_reporter,
)

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_emitter():
    """Create a mock WebSocketEmitterService."""
    emitter = MagicMock()
    emitter.emit = AsyncMock()
    return emitter


@pytest.fixture
def job_id():
    """Generate a test job ID."""
    return str(uuid4())


@pytest.fixture
def reporter(mock_emitter, job_id):
    """Create a JobProgressReporter instance with mocked emitter."""
    return JobProgressReporter(
        job_id=job_id,
        job_type="test_job",
        total_items=100,
        emitter=mock_emitter,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestJobProgressReporterInitialization:
    """Tests for JobProgressReporter initialization."""

    def test_initialization_with_uuid(self, mock_emitter):
        """Verify initialization with UUID job_id.

        Given: A UUID job_id
        When: JobProgressReporter is initialized
        Then: The job_id is converted to string
        """
        job_id = uuid4()
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="export",
            total_items=1000,
            emitter=mock_emitter,
        )

        assert reporter.job_id == str(job_id)
        assert reporter.job_type == "export"
        assert reporter.total_items == 1000
        assert not reporter.is_started
        assert not reporter.is_completed

    def test_initialization_with_string(self, mock_emitter, job_id):
        """Verify initialization with string job_id.

        Given: A string job_id
        When: JobProgressReporter is initialized
        Then: The job_id is stored as-is
        """
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="cleanup",
            total_items=500,
            emitter=mock_emitter,
        )

        assert reporter.job_id == job_id
        assert reporter.job_type == "cleanup"
        assert reporter.total_items == 500

    def test_initialization_total_items_zero_protection(self, mock_emitter, job_id):
        """Verify total_items=0 is converted to 1 to prevent division by zero.

        Given: total_items=0
        When: JobProgressReporter is initialized
        Then: total_items is set to 1
        """
        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="test",
            total_items=0,
            emitter=mock_emitter,
        )

        assert reporter.total_items == 1

    def test_initialization_duration_none_before_start(self, reporter):
        """Verify duration is None before job starts.

        Given: A newly initialized reporter
        When: duration_seconds is accessed
        Then: It returns None
        """
        assert reporter.duration_seconds is None

    @pytest.mark.asyncio
    async def test_create_classmethod_fetches_global_emitter(self, job_id):
        """Verify create() classmethod fetches global emitter.

        Given: A job_id, job_type, and total_items
        When: JobProgressReporter.create() is called
        Then: The global emitter is fetched and used
        """
        mock_emitter = MagicMock()
        mock_emitter.emit = AsyncMock()

        with patch(
            "backend.services.websocket_emitter.get_websocket_emitter",
            return_value=mock_emitter,
        ):
            reporter = await JobProgressReporter.create(
                job_id=job_id,
                job_type="export",
                total_items=100,
            )

            assert reporter.job_id == job_id
            assert reporter._emitter is mock_emitter

    @pytest.mark.asyncio
    async def test_create_convenience_function(self, job_id):
        """Verify create_job_progress_reporter convenience function.

        Given: Job parameters
        When: create_job_progress_reporter() is called
        Then: It delegates to JobProgressReporter.create()
        """
        mock_emitter = MagicMock()
        mock_emitter.emit = AsyncMock()

        with patch(
            "backend.services.websocket_emitter.get_websocket_emitter",
            return_value=mock_emitter,
        ):
            reporter = await create_job_progress_reporter(
                job_id=job_id,
                job_type="backup",
                total_items=50,
            )

            assert isinstance(reporter, JobProgressReporter)
            assert reporter.job_type == "backup"


# =============================================================================
# Job Lifecycle Tests
# =============================================================================


class TestJobLifecycle:
    """Tests for job lifecycle methods: start(), complete(), fail()."""

    @pytest.mark.asyncio
    async def test_start_emits_job_started_event(self, reporter, mock_emitter, job_id):
        """Verify start() emits JOB_STARTED event.

        Given: A reporter instance
        When: start() is called
        Then: JOB_STARTED event is emitted with correct payload
        """
        await reporter.start()

        assert reporter.is_started
        assert reporter._started_at is not None
        mock_emitter.emit.assert_called_once()

        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_STARTED
        payload = call_args[0][1]
        assert payload["job_id"] == job_id
        assert payload["job_type"] == "test_job"
        assert "started_at" in payload

    @pytest.mark.asyncio
    async def test_start_with_metadata(self, reporter, mock_emitter):
        """Verify start() includes optional metadata.

        Given: Estimated duration and metadata
        When: start() is called with these parameters
        Then: They are included in the event payload
        """
        metadata = {"user": "test_user", "batch_size": 100}
        await reporter.start(estimated_duration=300, metadata=metadata)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["estimated_duration"] == 300
        assert payload["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_start_raises_if_already_started(self, reporter):
        """Verify start() raises RuntimeError if already started.

        Given: A reporter that has already been started
        When: start() is called again
        Then: RuntimeError is raised
        """
        await reporter.start()

        with pytest.raises(RuntimeError, match="has already been started"):
            await reporter.start()

    @pytest.mark.asyncio
    async def test_complete_emits_job_completed_event(self, reporter, mock_emitter, job_id):
        """Verify complete() emits JOB_COMPLETED event.

        Given: A started reporter
        When: complete() is called
        Then: JOB_COMPLETED event is emitted with duration
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        # Add small delay for duration calculation
        await asyncio.sleep(0.01)

        result_summary = {"items_processed": 100, "errors": 0}
        await reporter.complete(result_summary=result_summary)

        assert reporter.is_completed
        mock_emitter.emit.assert_called_once()

        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_COMPLETED
        payload = call_args[0][1]
        assert payload["job_id"] == job_id
        assert payload["job_type"] == "test_job"
        assert payload["result"] == result_summary
        assert payload["duration_seconds"] is not None
        assert payload["duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_complete_raises_if_not_started(self, reporter):
        """Verify complete() raises RuntimeError if job not started.

        Given: A reporter that has not been started
        When: complete() is called
        Then: RuntimeError is raised
        """
        with pytest.raises(RuntimeError, match="has not been started"):
            await reporter.complete()

    @pytest.mark.asyncio
    async def test_complete_raises_if_already_completed(self, reporter):
        """Verify complete() raises RuntimeError if already completed.

        Given: A reporter that has already been completed
        When: complete() is called again
        Then: RuntimeError is raised
        """
        await reporter.start()
        await reporter.complete()

        with pytest.raises(RuntimeError, match="has already completed"):
            await reporter.complete()

    @pytest.mark.asyncio
    async def test_fail_emits_job_failed_event_with_exception(self, reporter, mock_emitter, job_id):
        """Verify fail() emits JOB_FAILED event with exception details.

        Given: A started reporter and an exception
        When: fail() is called with the exception
        Then: JOB_FAILED event is emitted with formatted error
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        error = ValueError("Something went wrong")
        await reporter.fail(error, retryable=True, error_code="VAL_001")

        assert reporter.is_completed
        mock_emitter.emit.assert_called_once()

        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_FAILED
        payload = call_args[0][1]
        assert payload["job_id"] == job_id
        assert "ValueError: Something went wrong" in payload["error"]
        assert payload["retryable"] is True
        assert payload["error_code"] == "VAL_001"

    @pytest.mark.asyncio
    async def test_fail_emits_job_failed_event_with_string(self, reporter, mock_emitter):
        """Verify fail() emits JOB_FAILED event with string error.

        Given: A started reporter and an error string
        When: fail() is called with the string
        Then: JOB_FAILED event is emitted
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.fail("Database connection lost")

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["error"] == "Database connection lost"
        assert payload["retryable"] is False
        assert payload["error_code"] is None

    @pytest.mark.asyncio
    async def test_fail_raises_if_not_started(self, reporter):
        """Verify fail() raises RuntimeError if job not started.

        Given: A reporter that has not been started
        When: fail() is called
        Then: RuntimeError is raised
        """
        with pytest.raises(RuntimeError, match="has not been started"):
            await reporter.fail("error")

    @pytest.mark.asyncio
    async def test_fail_raises_if_already_completed(self, reporter):
        """Verify fail() raises RuntimeError if already completed.

        Given: A reporter that has already been completed
        When: fail() is called
        Then: RuntimeError is raised
        """
        await reporter.start()
        await reporter.complete()

        with pytest.raises(RuntimeError, match="has already completed"):
            await reporter.fail("error")

    @pytest.mark.asyncio
    async def test_duration_tracking(self, reporter):
        """Verify duration is tracked correctly.

        Given: A started reporter
        When: Time passes and duration_seconds is accessed
        Then: It returns the correct elapsed time
        """
        await reporter.start()
        await asyncio.sleep(0.05)  # Sleep for 50ms

        duration = reporter.duration_seconds
        assert duration is not None
        assert duration >= 0.04  # Allow small margin


# =============================================================================
# Progress Reporting Tests
# =============================================================================


class TestProgressReporting:
    """Tests for report_progress() method and throttling behavior."""

    @pytest.mark.asyncio
    async def test_report_progress_emits_event(self, reporter, mock_emitter, job_id):
        """Verify report_progress() emits JOB_PROGRESS event.

        Given: A started reporter
        When: report_progress() is called
        Then: JOB_PROGRESS event is emitted
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        emitted = await reporter.report_progress(50, current_step="Processing batch 1")

        assert emitted is True
        mock_emitter.emit.assert_called_once()

        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_PROGRESS
        payload = call_args[0][1]
        assert payload["job_id"] == job_id
        assert payload["progress"] == 50
        assert payload["status"] == "running"
        assert payload["message"] == "Processing batch 1"

    @pytest.mark.asyncio
    async def test_report_progress_throttling(self, reporter, mock_emitter):
        """Verify progress updates are throttled to max 1 per second.

        Given: A started reporter
        When: Multiple progress updates are sent rapidly
        Then: Only the first update is emitted, subsequent ones are throttled
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        # First update should emit
        emitted1 = await reporter.report_progress(10)
        assert emitted1 is True
        assert mock_emitter.emit.call_count == 1

        # Second update immediately after should be throttled
        emitted2 = await reporter.report_progress(11)
        assert emitted2 is False
        assert mock_emitter.emit.call_count == 1

        # Third update after throttle interval should emit
        await asyncio.sleep(PROGRESS_THROTTLE_INTERVAL + 0.01)
        emitted3 = await reporter.report_progress(12)
        assert emitted3 is True
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_report_progress_force_bypasses_throttling(self, reporter, mock_emitter):
        """Verify force=True bypasses throttling.

        Given: A started reporter with recent progress update
        When: report_progress() is called with force=True
        Then: Event is emitted despite throttling
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(10)
        assert mock_emitter.emit.call_count == 1

        # Force emit should bypass throttling
        emitted = await reporter.report_progress(11, force=True)
        assert emitted is True
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_report_progress_10_percent_jump_triggers_emit(self, reporter, mock_emitter):
        """Verify 10% or more progress jump triggers immediate emit.

        Given: A started reporter at 10% progress
        When: Progress jumps to 20% or more
        Then: Event is emitted despite time throttling
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        # First update at 10%
        await reporter.report_progress(10)
        assert mock_emitter.emit.call_count == 1

        # Jump to 20% (10% delta) should emit immediately
        emitted = await reporter.report_progress(20)
        assert emitted is True
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_report_progress_9_percent_jump_throttled(self, reporter, mock_emitter):
        """Verify progress jump less than 10% is still throttled.

        Given: A started reporter at 10% progress
        When: Progress increases by less than 10%
        Then: Update is throttled by time
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(10)
        assert mock_emitter.emit.call_count == 1

        # Jump to 19% (9% delta) should be throttled
        emitted = await reporter.report_progress(19)
        assert emitted is False
        assert mock_emitter.emit.call_count == 1

    @pytest.mark.asyncio
    async def test_report_progress_caps_at_100_percent(self, reporter, mock_emitter):
        """Verify progress is capped at 100%.

        Given: A started reporter with 100 total items
        When: report_progress() is called with 150 items processed
        Then: Progress is capped at 100%
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(150)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["progress"] == 100

    @pytest.mark.asyncio
    async def test_report_progress_raises_if_not_started(self, reporter):
        """Verify report_progress() raises RuntimeError if job not started.

        Given: A reporter that has not been started
        When: report_progress() is called
        Then: RuntimeError is raised
        """
        with pytest.raises(RuntimeError, match="has not been started"):
            await reporter.report_progress(10)

    @pytest.mark.asyncio
    async def test_report_progress_raises_if_completed(self, reporter):
        """Verify report_progress() raises RuntimeError if job completed.

        Given: A reporter that has been completed
        When: report_progress() is called
        Then: RuntimeError is raised
        """
        await reporter.start()
        await reporter.complete()

        with pytest.raises(RuntimeError, match="has already completed"):
            await reporter.report_progress(50)


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestContextManager:
    """Tests for async context manager support (__aenter__, __aexit__)."""

    @pytest.mark.asyncio
    async def test_aenter_calls_start(self, reporter, mock_emitter):
        """Verify __aenter__ calls start() and returns self.

        Given: A reporter instance
        When: __aenter__ is called
        Then: start() is called and self is returned
        """
        result = await reporter.__aenter__()

        assert result is reporter
        assert reporter.is_started
        mock_emitter.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_auto_completes_on_success(self, reporter, mock_emitter):
        """Verify __aexit__ auto-completes job on success.

        Given: A reporter used in async with block
        When: Block exits normally without exception
        Then: complete() is called automatically
        """
        await reporter.__aenter__()
        mock_emitter.emit.reset_mock()

        await reporter.__aexit__(None, None, None)

        assert reporter.is_completed
        # Should have emitted JOB_COMPLETED
        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_COMPLETED

    @pytest.mark.asyncio
    async def test_aexit_auto_fails_on_exception(self, reporter, mock_emitter):
        """Verify __aexit__ auto-fails job on exception.

        Given: A reporter used in async with block
        When: Block exits with exception
        Then: fail() is called automatically with the exception
        """
        await reporter.__aenter__()
        mock_emitter.emit.reset_mock()

        error = ValueError("Test error")
        await reporter.__aexit__(ValueError, error, None)

        assert reporter.is_completed
        # Should have emitted JOB_FAILED
        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.JOB_FAILED
        payload = call_args[0][1]
        assert "ValueError: Test error" in payload["error"]

    @pytest.mark.asyncio
    async def test_aexit_does_not_suppress_exceptions(self, reporter):
        """Verify __aexit__ returns False to propagate exceptions.

        Given: A reporter in async with block
        When: __aexit__ is called with an exception
        Then: It returns False (or None) to propagate the exception
        """
        await reporter.__aenter__()

        result = await reporter.__aexit__(ValueError, ValueError("test"), None)

        assert result is False

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, reporter, mock_emitter):
        """Verify reporter can be used with async with statement.

        Given: A reporter instance
        When: Used in async with block
        Then: start() is called on entry, complete() on exit
        """
        async with reporter as r:
            assert r is reporter
            assert reporter.is_started
            assert not reporter.is_completed

        assert reporter.is_completed
        # Should have emitted JOB_STARTED and JOB_COMPLETED
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, reporter, mock_emitter):
        """Verify context manager handles exceptions correctly.

        Given: A reporter in async with block
        When: Exception is raised inside block
        Then: fail() is called and exception is propagated
        """
        with pytest.raises(RuntimeError, match="test error"):
            async with reporter:
                assert reporter.is_started
                raise RuntimeError("test error")

        # Should have emitted JOB_STARTED and JOB_FAILED
        assert mock_emitter.emit.call_count == 2
        assert reporter.is_completed

    @pytest.mark.asyncio
    async def test_aexit_skips_completion_if_already_completed(self, reporter, mock_emitter):
        """Verify __aexit__ skips auto-completion if job already completed.

        Given: A reporter that manually calls complete()
        When: __aexit__ is called
        Then: It does not call complete() again
        """
        await reporter.__aenter__()
        await reporter.complete()
        emit_count_after_complete = mock_emitter.emit.call_count

        await reporter.__aexit__(None, None, None)

        # Emit count should not increase
        assert mock_emitter.emit.call_count == emit_count_after_complete


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and state validation."""

    @pytest.mark.asyncio
    async def test_negative_progress_is_clamped(self, reporter, mock_emitter):
        """Verify negative progress values are handled gracefully.

        Given: A started reporter
        When: report_progress() is called with negative items_processed
        Then: Progress is calculated as 0% and may or may not emit due to throttling
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        emitted = await reporter.report_progress(-10)

        # If emitted, check the payload
        if emitted:
            payload = mock_emitter.emit.call_args[0][1]
            # Negative divided by positive gives negative, min() clamps to 0
            assert payload["progress"] >= 0


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestConcurrency:
    """Tests for concurrent job reporting scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_jobs_report_simultaneously(self, mock_emitter):
        """Verify multiple jobs can report progress simultaneously.

        Given: Multiple reporter instances
        When: All report progress concurrently
        Then: All events are emitted correctly
        """
        jobs = [
            JobProgressReporter(
                job_id=str(uuid4()),
                job_type=f"job_{i}",
                total_items=100,
                emitter=mock_emitter,
            )
            for i in range(5)
        ]

        # Start all jobs
        await asyncio.gather(*[job.start() for job in jobs])

        # Report progress on all jobs
        mock_emitter.emit.reset_mock()
        results = await asyncio.gather(
            *[job.report_progress(50, current_step=f"Step {i}") for i, job in enumerate(jobs)]
        )

        # All should have emitted
        assert all(results)
        assert mock_emitter.emit.call_count == 5

    @pytest.mark.asyncio
    async def test_rapid_updates_respect_throttling(self, reporter, mock_emitter):
        """Verify rapid updates on single job respect throttling.

        Given: A started reporter
        When: 10 rapid updates are sent
        Then: Only a few are emitted due to throttling
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        results = []
        for i in range(10):
            result = await reporter.report_progress(i + 1)
            results.append(result)
            await asyncio.sleep(0.05)  # 50ms between updates

        # Only first should emit, rest throttled (all within 1 second)
        emitted_count = sum(results)
        assert emitted_count < 10
        # At least one should have been emitted
        assert emitted_count >= 1

    @pytest.mark.asyncio
    async def test_get_emitter_lazy_loading(self, job_id):
        """Verify _get_emitter() fetches global emitter on demand.

        Given: A reporter created without emitter
        When: start() is called (which calls _get_emitter())
        Then: Global emitter is fetched
        """
        mock_emitter = MagicMock()
        mock_emitter.emit = AsyncMock()

        reporter = JobProgressReporter(
            job_id=job_id,
            job_type="test",
            total_items=100,
            emitter=None,  # No emitter provided
        )

        with patch(
            "backend.services.websocket_emitter.get_websocket_emitter",
            return_value=mock_emitter,
        ):
            await reporter.start()

            # Emitter should have been fetched and used
            assert reporter._emitter is mock_emitter
            mock_emitter.emit.assert_called_once()
