"""Unit tests for the CleanupService.

This module contains comprehensive unit tests for the CleanupService, which manages
automated cleanup of old data including events, detections, GPU stats, logs,
thumbnails, and optionally source images.

Related Issues:
    - NEM-1661: Improve Test Documentation with Intent and Acceptance Criteria

Test Organization:
    - CleanupStats tests: Verify the data class for tracking cleanup metrics
    - Initialization tests: Verify service creation with default/custom settings
    - Time parsing tests: Verify cleanup time HH:MM parsing logic
    - File deletion tests: Verify safe file deletion behavior
    - Service lifecycle tests: Verify start/stop behavior and idempotency
    - run_cleanup tests: Verify actual cleanup operations with database
    - dry_run_cleanup tests: Verify preview mode without deletion
    - Log cleanup tests: Verify old log entry removal
    - Edge case tests: Verify boundary conditions and error handling

Acceptance Criteria:
    - Cleanup service respects configured retention_days
    - Cleanup runs at scheduled cleanup_time (HH:MM format)
    - Cleanup deletes old events, detections, GPU stats, and logs
    - Cleanup optionally deletes thumbnail and source image files
    - Dry run mode counts records without deleting
    - Service handles database errors gracefully
    - Service lifecycle (start/stop) is idempotent

Notes:
    These tests use mocks and do not require a database connection.
    Tests that require PostgreSQL are in backend/tests/integration/test_cleanup_service.py.
"""

import asyncio
import contextlib
import logging
import os
import tempfile
import types
from datetime import UTC, datetime, timedelta
from operator import lt
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import backend.services.cleanup_service as cs
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.gpu_stats import GPUStats
from backend.models.log import Log
from backend.services.cleanup_service import CleanupService, CleanupStats

# Mark all tests in this module as unit tests (use mocks, no database required)
pytestmark = pytest.mark.unit

# Fixtures


@pytest.fixture(autouse=True)
def mock_settings_for_cleanup_tests():
    """Set up minimal environment for tests that don't use test_db.

    This fixture sets DATABASE_URL so get_settings() doesn't fail when
    CleanupService is instantiated without explicit retention_days.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")

    # Only set DATABASE_URL if not already set (e.g., by test_db fixture)
    if not original_db_url:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
        )
        get_settings.cache_clear()

    yield

    # Restore original state
    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url
    get_settings.cache_clear()


@pytest.fixture
def cleanup_service():
    """Create cleanup service instance with test configuration."""
    service = CleanupService(
        cleanup_time="03:00",
        retention_days=30,
        thumbnail_dir="data/thumbnails",
        delete_images=False,
    )
    return service


@pytest.fixture
def cleanup_service_delete_images(tmp_path):
    """Create cleanup service configured to delete images."""
    service = CleanupService(
        cleanup_time="02:00",
        retention_days=7,
        thumbnail_dir=str(tmp_path / "thumbnails"),
        delete_images=True,
    )
    return service


# =============================================================================
# CleanupStats Tests
# =============================================================================


class TestCleanupStats:
    """Tests for the CleanupStats data class.

    CleanupStats tracks metrics from a cleanup operation including:
    - Number of events, detections, GPU stats, and logs deleted
    - Number of thumbnail and image files deleted
    - Total disk space reclaimed in bytes
    """

    def test_initialization_with_zero_values(self):
        """Verify CleanupStats initializes all counters to zero.

        Given: No arguments provided to CleanupStats constructor
        When: A new CleanupStats instance is created
        Then: All counter fields should be initialized to 0
        """
        stats = CleanupStats()

        assert stats.events_deleted == 0
        assert stats.detections_deleted == 0
        assert stats.gpu_stats_deleted == 0
        assert stats.logs_deleted == 0
        assert stats.thumbnails_deleted == 0
        assert stats.images_deleted == 0
        assert stats.space_reclaimed == 0

    def test_to_dict_converts_all_fields(self):
        """Verify CleanupStats converts to dictionary with all fields.

        Given: A CleanupStats instance with populated values
        When: to_dict() is called
        Then: Returns a dictionary containing all field names and values
        """
        stats = CleanupStats()
        stats.events_deleted = 10
        stats.detections_deleted = 25
        stats.gpu_stats_deleted = 100
        stats.logs_deleted = 50
        stats.thumbnails_deleted = 20
        stats.images_deleted = 15
        stats.space_reclaimed = 1024000

        result = stats.to_dict()

        assert result == {
            "events_deleted": 10,
            "detections_deleted": 25,
            "gpu_stats_deleted": 100,
            "logs_deleted": 50,
            "thumbnails_deleted": 20,
            "images_deleted": 15,
            "space_reclaimed": 1024000,
        }

    def test_repr_includes_key_fields(self):
        """Verify CleanupStats string representation includes key metrics.

        Given: A CleanupStats instance with some values set
        When: repr() is called on the instance
        Then: String includes class name and key metric values
        """
        stats = CleanupStats()
        stats.events_deleted = 5
        stats.detections_deleted = 10

        repr_str = repr(stats)

        assert "CleanupStats" in repr_str
        assert "events=5" in repr_str
        assert "detections=10" in repr_str


# =============================================================================
# CleanupService Initialization Tests
# =============================================================================


class TestCleanupServiceInitialization:
    """Tests for CleanupService initialization and configuration.

    The CleanupService can be configured with:
    - cleanup_time: When to run daily cleanup (HH:MM format, default "03:00")
    - retention_days: How many days of data to keep (default 30)
    - thumbnail_dir: Directory containing thumbnail images
    - delete_images: Whether to delete source images (default False)
    """

    def test_default_configuration(self):
        """Verify CleanupService initializes with sensible defaults.

        Given: No configuration parameters provided
        When: A new CleanupService instance is created
        Then: Uses default cleanup_time="03:00", retention_days=30, delete_images=False

        Note: We mock get_settings to return actual defaults because the runtime.env
        file may override values. This test is specifically testing code defaults.
        """
        mock_settings = MagicMock()
        mock_settings.retention_days = 30  # Default from Settings class

        with patch(
            "backend.services.cleanup_service.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
            service = CleanupService()

        assert service.cleanup_time == "03:00"
        assert service.retention_days == 30  # From config default
        assert service.delete_images is False
        assert service.running is False
        assert service._cleanup_task is None

    def test_custom_configuration(self):
        """Verify CleanupService accepts custom configuration values.

        Given: Custom configuration parameters
        When: A new CleanupService instance is created with those parameters
        Then: Service uses the provided custom values
        """
        service = CleanupService(
            cleanup_time="01:30",
            retention_days=14,
            thumbnail_dir="/custom/path",
            delete_images=True,
        )

        assert service.cleanup_time == "01:30"
        assert service.retention_days == 14
        assert service.delete_images is True
        assert str(service.thumbnail_dir) == "/custom/path"


# =============================================================================
# Time Parsing Tests
# =============================================================================


class TestCleanupTimeParsing:
    """Tests for cleanup time parsing (HH:MM format).

    The cleanup_time setting determines when the daily cleanup runs.
    It must be in 24-hour HH:MM format (e.g., "03:00" for 3 AM).
    """

    def test_valid_time_format(self):
        """Verify valid HH:MM time strings are parsed correctly.

        Given: A CleanupService configured with cleanup_time="14:30"
        When: _parse_cleanup_time() is called
        Then: Returns tuple (14, 30) representing 2:30 PM
        """
        service = CleanupService(cleanup_time="14:30")
        hours, minutes = service._parse_cleanup_time()

        assert hours == 14
        assert minutes == 30

    def test_midnight_time(self):
        """Verify midnight (00:00) is parsed correctly.

        Given: A CleanupService configured with cleanup_time="00:00"
        When: _parse_cleanup_time() is called
        Then: Returns tuple (0, 0) representing midnight
        """
        service = CleanupService(cleanup_time="00:00")
        hours, minutes = service._parse_cleanup_time()

        assert hours == 0
        assert minutes == 0

    def test_invalid_format_raises_error(self):
        """Verify invalid time format raises ValueError.

        Given: A CleanupService configured with an invalid time string
        When: _parse_cleanup_time() is called
        Then: Raises ValueError with descriptive message
        """
        service = CleanupService(cleanup_time="invalid")

        with pytest.raises(ValueError, match="Invalid cleanup_time format"):
            service._parse_cleanup_time()

    def test_out_of_range_hour_raises_error(self):
        """Verify out-of-range hour value raises ValueError.

        Given: A CleanupService configured with hour > 23
        When: _parse_cleanup_time() is called
        Then: Raises ValueError with descriptive message
        """
        service = CleanupService(cleanup_time="25:00")

        with pytest.raises(ValueError, match="Invalid cleanup_time format"):
            service._parse_cleanup_time()


# =============================================================================
# Next Cleanup Calculation Tests
# =============================================================================


class TestNextCleanupCalculation:
    """Tests for calculating the next scheduled cleanup time.

    The service calculates when to next run cleanup based on:
    - Current time
    - Configured cleanup_time (HH:MM)
    - Whether today's cleanup time has already passed
    """

    def test_cleanup_scheduled_for_today_when_time_not_passed(self):
        """Verify cleanup is scheduled for today when time hasn't passed.

        Given: Current time is 10:00 AM, cleanup_time is "14:00"
        When: _calculate_next_cleanup() is called
        Then: Returns today's date at 14:00
        """
        # Use a fixed time that's definitely in the morning to avoid midnight edge cases
        mock_now = datetime(2025, 12, 23, 10, 0, 0)  # 10:00 AM
        future_time = "14:00"  # 2:00 PM - still 4 hours away

        with patch("backend.services.cleanup_service.datetime", autospec=True) as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            service = CleanupService(cleanup_time=future_time)
            next_cleanup = service._calculate_next_cleanup()

            # Should be today
            assert next_cleanup.date() == mock_now.date()
            assert next_cleanup > mock_now

    def test_cleanup_scheduled_for_tomorrow_when_time_passed(self):
        """Verify cleanup is scheduled for tomorrow when today's time has passed.

        Given: Current time is 14:00, cleanup_time is "12:00"
        When: _calculate_next_cleanup() is called
        Then: Returns tomorrow's date at 12:00
        """
        # Use a fixed time (14:00) to avoid edge cases near midnight
        # Mock datetime to ensure the test time is well past the cleanup time
        fixed_now = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)

        with patch("backend.services.cleanup_service.datetime", autospec=True) as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            # Pass through timedelta calls
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # Set cleanup time to 2 hours before our fixed time (12:00)
            service = CleanupService(cleanup_time="12:00")
            next_cleanup = service._calculate_next_cleanup()

        # Should be tomorrow at 12:00
        assert next_cleanup.date() == (fixed_now + timedelta(days=1)).date()
        assert next_cleanup > fixed_now
        assert next_cleanup.hour == 12
        assert next_cleanup.minute == 0


# =============================================================================
# File Deletion Tests
# =============================================================================


class TestFileDeletion:
    """Tests for the _delete_file helper method.

    This method safely deletes files, handling common error conditions:
    - Nonexistent files
    - Permission errors
    - Directories (should not delete)
    """

    def test_successful_deletion(self, tmp_path):
        """Verify successful file deletion returns True.

        Given: A file exists at a valid path
        When: _delete_file() is called with that path
        Then: Returns True and file no longer exists
        """
        # Create test file
        test_file = tmp_path / "test.jpg"
        test_file.write_text("test data")

        service = CleanupService()
        result = service._delete_file(str(test_file))

        assert result is True
        assert not test_file.exists()

    def test_nonexistent_file_returns_false(self):
        """Verify deleting nonexistent file returns False.

        Given: A file path that does not exist
        When: _delete_file() is called with that path
        Then: Returns False without raising exception
        """
        service = CleanupService()
        result = service._delete_file("/path/that/does/not/exist.jpg")

        assert result is False

    def test_permission_error_returns_false(self, tmp_path):
        """Verify permission error is handled gracefully.

        Given: A file that cannot be deleted due to permissions
        When: _delete_file() is called
        Then: Returns False without raising exception
        """
        test_file = tmp_path / "readonly.jpg"
        test_file.write_text("test")

        service = CleanupService()

        # Mock unlink to raise permission error
        with patch.object(
            Path, "unlink", side_effect=PermissionError("Access denied"), autospec=True
        ):
            result = service._delete_file(str(test_file))

        assert result is False


# =============================================================================
# Service Status Tests
# =============================================================================


class TestServiceStatus:
    """Tests for the get_cleanup_stats() method.

    This method returns the current service configuration and state,
    useful for health checks and admin dashboards.
    """

    def test_stats_when_not_running(self):
        """Verify stats show service is not running when stopped.

        Given: A CleanupService that has not been started
        When: get_cleanup_stats() is called
        Then: Returns running=False and next_cleanup=None
        """
        service = CleanupService(retention_days=14, cleanup_time="02:00")

        stats = service.get_cleanup_stats()

        assert stats["running"] is False
        assert stats["retention_days"] == 14
        assert stats["cleanup_time"] == "02:00"
        assert stats["delete_images"] is False
        assert stats["next_cleanup"] is None

    def test_stats_when_running(self):
        """Verify stats show service is running with next cleanup time.

        Given: A CleanupService that is running
        When: get_cleanup_stats() is called
        Then: Returns running=True and next_cleanup is set
        """
        service = CleanupService()
        service.running = True

        stats = service.get_cleanup_stats()

        assert stats["running"] is True
        assert stats["next_cleanup"] is not None


# =============================================================================
# Service Lifecycle Tests (Start/Stop)
# =============================================================================


class TestServiceLifecycle:
    """Tests for CleanupService start() and stop() methods.

    The service lifecycle should be idempotent - calling start() multiple
    times should be safe, and stop() should gracefully handle already-stopped
    services.
    """

    @pytest.mark.asyncio
    async def test_start_creates_cleanup_task(self):
        """Verify starting service creates background cleanup task.

        Given: A new CleanupService instance
        When: start() is called
        Then: Service is running and cleanup task is created
        """
        service = CleanupService()

        await service.start()

        assert service.running is True
        assert service._cleanup_task is not None

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        """Verify calling start() multiple times is safe.

        Given: A CleanupService that is already running
        When: start() is called again
        Then: Same task is used, no duplicate tasks created
        """
        service = CleanupService()

        await service.start()
        first_task = service._cleanup_task

        await service.start()
        second_task = service._cleanup_task

        # Should be same task
        assert first_task is second_task

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_cleanup_task(self):
        """Verify stopping service cancels background task.

        Given: A running CleanupService
        When: stop() is called
        Then: Service is not running and task is cleared
        """
        service = CleanupService()

        await service.start()
        assert service.running is True

        await service.stop()

        assert service.running is False
        assert service._cleanup_task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Verify stopping a non-running service is safe.

        Given: A CleanupService that has not been started
        When: stop() is called
        Then: No exception is raised
        """
        service = CleanupService()

        # Should not raise exception
        await service.stop()

        assert service.running is False


@pytest.mark.asyncio
async def test_cleanup_loop_runs_scheduled():
    """Test cleanup loop waits and runs at scheduled time."""
    service = CleanupService(cleanup_time="03:00", retention_days=30)

    # Track call counts
    wait_calls = 0
    cleanup_calls = 0

    async def mock_wait():
        nonlocal wait_calls
        wait_calls += 1
        # Stop after first iteration to prevent infinite loop
        if wait_calls > 1:
            service.running = False
        await asyncio.sleep(0.01)  # Small delay to yield control

    async def mock_cleanup():
        nonlocal cleanup_calls
        cleanup_calls += 1
        return CleanupStats()

    with (
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait, autospec=True),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup, autospec=True),
    ):
        # Start service
        await service.start()

        # Wait for loop to complete
        await asyncio.sleep(0.1)

        # Stop service (may already be stopped by mock)
        await service.stop()

        # Verify wait and cleanup were called
        assert wait_calls >= 1
        assert cleanup_calls >= 1


@pytest.mark.asyncio
async def test_cleanup_loop_handles_errors():
    """Test cleanup loop continues after errors.

    This tests that the cleanup loop recovers from errors and continues running.
    We mock the error recovery sleep to avoid the 60 second wait.
    """
    service = CleanupService()

    # Track call counts
    wait_calls = 0
    cleanup_calls = 0

    async def mock_wait():
        nonlocal wait_calls
        wait_calls += 1
        # Stop after third iteration (enough for: error -> recover -> success)
        if wait_calls > 2:
            service.running = False
        await asyncio.sleep(0.01)

    async def mock_cleanup_with_error():
        nonlocal cleanup_calls
        cleanup_calls += 1
        if cleanup_calls == 1:
            raise Exception("Test error")
        return CleanupStats()

    # Patch the error recovery sleep (60s) in the cleanup loop
    original_sleep = asyncio.sleep

    async def patched_sleep(seconds):
        # For the 60-second error recovery sleep, make it instant
        if seconds >= 60:
            await original_sleep(0.01)
        else:
            await original_sleep(seconds)

    with (
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait, autospec=True),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup_with_error, autospec=True),
        patch(
            "backend.services.cleanup_service.asyncio.sleep",
            side_effect=patched_sleep,
            autospec=True,
        ),
    ):
        # Start service
        await service.start()

        # Wait for loop to run through error and recovery
        await asyncio.sleep(0.2)

        # Stop service (may already be stopped by mock)
        await service.stop()

        # Verify loop continued after error (called at least twice)
        assert cleanup_calls >= 2, f"Expected cleanup >= 2, got {cleanup_calls}"


@pytest.mark.asyncio
async def test_wait_until_next_cleanup():
    """Test waiting until next cleanup time."""
    service = CleanupService(cleanup_time="03:00")

    # Mock asyncio.sleep to avoid actual waiting
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await service._wait_until_next_cleanup()

        # Verify sleep was called with positive seconds
        mock_sleep.assert_called_once()
        wait_seconds = mock_sleep.call_args[0][0]
        assert wait_seconds > 0  # Should be waiting for future time


# Dry Run Cleanup Tests
# =============================================================================


@pytest.mark.asyncio
async def test_dry_run_cleanup_respects_retention_days():
    """Test that dry_run_cleanup uses the configured retention_days."""
    # Create service with different retention values
    service_7_days = CleanupService(retention_days=7)
    service_30_days = CleanupService(retention_days=30)

    # Verify they have different retention settings
    assert service_7_days.retention_days == 7
    assert service_30_days.retention_days == 30


# =============================================================================
# Additional Edge Cases
# =============================================================================


def test_parse_cleanup_time_edge_cases():
    """Test parsing edge case times."""
    # Exactly midnight
    service = CleanupService(cleanup_time="00:00")
    hours, minutes = service._parse_cleanup_time()
    assert hours == 0
    assert minutes == 0

    # Last minute of day
    service = CleanupService(cleanup_time="23:59")
    hours, minutes = service._parse_cleanup_time()
    assert hours == 23
    assert minutes == 59


def test_cleanup_stats_repr_all_fields():
    """Test CleanupStats repr includes all fields."""
    stats = CleanupStats()
    stats.events_deleted = 100
    stats.detections_deleted = 250
    stats.gpu_stats_deleted = 500
    stats.logs_deleted = 75
    stats.thumbnails_deleted = 30
    stats.images_deleted = 10
    stats.space_reclaimed = 1024 * 1024 * 100  # 100 MB

    repr_str = repr(stats)

    assert "events=100" in repr_str
    assert "detections=250" in repr_str


def test_delete_images_setting():
    """Test delete_images setting is respected."""
    service_with_delete = CleanupService(delete_images=True)
    service_without_delete = CleanupService(delete_images=False)

    assert service_with_delete.delete_images is True
    assert service_without_delete.delete_images is False


def test_thumbnail_dir_custom():
    """Test custom thumbnail directory."""
    service = CleanupService(thumbnail_dir="/custom/path/thumbnails")

    assert str(service.thumbnail_dir) == "/custom/path/thumbnails"


# =============================================================================
# run_cleanup tests (lines 188-259)
# =============================================================================


class MockDetection:
    """Mock Detection object for testing."""

    def __init__(
        self,
        id: int = 1,
        thumbnail_path: str | None = None,
        file_path: str | None = None,
    ):
        self.id = id
        self.thumbnail_path = thumbnail_path
        self.file_path = file_path


class MockAsyncIterator:
    """Mock async iterator for stream_scalars() results."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


def create_stream_scalars_mock(items):
    """Create an async mock for session.stream_scalars().

    stream_scalars() returns a coroutine that yields an async iterator,
    so we need to return an awaitable that returns an async iterator.
    """

    async def mock_stream_scalars(*args, **kwargs):
        return MockAsyncIterator(items)

    return mock_stream_scalars


@pytest.mark.asyncio
async def test_run_cleanup_basic():
    """Test run_cleanup deletes detections, events, GPU stats, and logs."""
    service = CleanupService(retention_days=30)

    # Mock session and database operations
    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths (returns empty)
    mock_session.stream_scalars = create_stream_scalars_mock([])

    # Mock delete results with rowcount
    mock_delete_detections_result = MagicMock()
    mock_delete_detections_result.rowcount = 5

    mock_delete_events_result = MagicMock()
    mock_delete_events_result.rowcount = 3

    mock_delete_gpu_stats_result = MagicMock()
    mock_delete_gpu_stats_result.rowcount = 100

    # Set up execute for delete operations
    mock_session.execute = AsyncMock(
        side_effect=[
            mock_delete_detections_result,  # delete detections
            mock_delete_events_result,  # delete events
            mock_delete_gpu_stats_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    # Mock get_session as async context manager
    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=50, autospec=True),
    ):
        stats = await service.run_cleanup()

    assert stats.detections_deleted == 5
    assert stats.events_deleted == 3
    assert stats.gpu_stats_deleted == 100
    assert stats.logs_deleted == 50
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_cleanup_with_thumbnail_files(tmp_path):
    """Test run_cleanup deletes thumbnail files for deleted detections."""
    service = CleanupService(retention_days=30)

    # Create test thumbnail files
    thumbnail1 = tmp_path / "thumb1.jpg"
    thumbnail2 = tmp_path / "thumb2.jpg"
    thumbnail1.write_text("thumbnail 1")
    thumbnail2.write_text("thumbnail 2")

    # Mock detections with thumbnail paths
    mock_detection1 = MockDetection(id=1, thumbnail_path=str(thumbnail1))
    mock_detection2 = MockDetection(id=2, thumbnail_path=str(thumbnail2))

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths
    mock_session.stream_scalars = create_stream_scalars_mock([mock_detection1, mock_detection2])

    # Mock delete results
    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 2

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_delete_result,  # delete detections
            mock_delete_result,  # delete events
            mock_delete_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.run_cleanup()

    assert stats.thumbnails_deleted == 2
    assert not thumbnail1.exists()
    assert not thumbnail2.exists()


@pytest.mark.asyncio
async def test_run_cleanup_with_image_files_enabled(tmp_path):
    """Test run_cleanup deletes image files when delete_images is True."""
    service = CleanupService(retention_days=30, delete_images=True)

    # Create test image and thumbnail files
    image1 = tmp_path / "image1.jpg"
    image2 = tmp_path / "image2.jpg"
    thumbnail1 = tmp_path / "thumb1.jpg"
    image1.write_text("image 1")
    image2.write_text("image 2")
    thumbnail1.write_text("thumbnail 1")

    # Mock detections with both thumbnail and file paths
    mock_detection1 = MockDetection(id=1, thumbnail_path=str(thumbnail1), file_path=str(image1))
    mock_detection2 = MockDetection(id=2, thumbnail_path=None, file_path=str(image2))

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths
    mock_session.stream_scalars = create_stream_scalars_mock([mock_detection1, mock_detection2])

    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 2

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_delete_result,  # delete detections
            mock_delete_result,  # delete events
            mock_delete_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.run_cleanup()

    assert stats.thumbnails_deleted == 1  # Only mock_detection1 has thumbnail
    assert stats.images_deleted == 2
    assert not image1.exists()
    assert not image2.exists()
    assert not thumbnail1.exists()


@pytest.mark.asyncio
async def test_run_cleanup_exception_handling():
    """Test run_cleanup re-raises exceptions after logging."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Database error"))

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        pytest.raises(Exception, match="Database error"),
    ):
        await service.run_cleanup()


@pytest.mark.asyncio
async def test_run_cleanup_with_none_rowcount():
    """Test run_cleanup handles None rowcount from database."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths (returns empty)
    mock_session.stream_scalars = create_stream_scalars_mock([])

    # Simulate None rowcount (can happen in some edge cases)
    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = None

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_delete_result,  # delete detections
            mock_delete_result,  # delete events
            mock_delete_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.run_cleanup()

    # Should handle None gracefully
    assert stats.detections_deleted == 0
    assert stats.events_deleted == 0
    assert stats.gpu_stats_deleted == 0


# =============================================================================
# dry_run_cleanup tests (lines 274-353)
# =============================================================================


@pytest.mark.asyncio
async def test_dry_run_cleanup_basic():
    """Test dry_run_cleanup counts records without deleting."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths (returns empty)
    mock_session.stream_scalars = create_stream_scalars_mock([])

    # Mock count queries - use MagicMock for sync result methods
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 10

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 5

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 100

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,  # count detections
            mock_event_count,  # count events
            mock_gpu_stats_count,  # count gpu stats
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=25, autospec=True),
    ):
        stats = await service.dry_run_cleanup()

    assert stats.detections_deleted == 10
    assert stats.events_deleted == 5
    assert stats.gpu_stats_deleted == 100
    assert stats.logs_deleted == 25
    # Verify commit was NOT called (dry run)
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_dry_run_cleanup_with_files(tmp_path):
    """Test dry_run_cleanup counts files and space without deleting."""
    service = CleanupService(retention_days=30, delete_images=True)

    # Create test files
    thumbnail1 = tmp_path / "thumb1.jpg"
    thumbnail2 = tmp_path / "thumb2.jpg"
    image1 = tmp_path / "image1.jpg"
    thumbnail1.write_text("t" * 1000)  # 1000 bytes
    thumbnail2.write_text("t" * 2000)  # 2000 bytes
    image1.write_text("i" * 5000)  # 5000 bytes

    mock_detection1 = MockDetection(id=1, thumbnail_path=str(thumbnail1), file_path=str(image1))
    mock_detection2 = MockDetection(id=2, thumbnail_path=str(thumbnail2), file_path=None)

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths
    mock_session.stream_scalars = create_stream_scalars_mock([mock_detection1, mock_detection2])

    # Use MagicMock for result objects
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 2

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,  # count detections
            mock_event_count,  # count events
            mock_gpu_stats_count,  # count gpu stats
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.dry_run_cleanup()

    assert stats.thumbnails_deleted == 2
    assert stats.images_deleted == 1
    assert stats.space_reclaimed == 8000  # 1000 + 2000 + 5000
    # Files should still exist (dry run)
    assert thumbnail1.exists()
    assert thumbnail2.exists()
    assert image1.exists()


@pytest.mark.asyncio
async def test_dry_run_cleanup_file_stat_error(tmp_path):
    """Test dry_run_cleanup handles nonexistent file paths."""
    service = CleanupService(retention_days=30)

    # Use a nonexistent file path to test the case where file doesn't exist
    mock_detection = MockDetection(id=1, thumbnail_path="/nonexistent/path.jpg")

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths
    mock_session.stream_scalars = create_stream_scalars_mock([mock_detection])

    # Use MagicMock for result objects
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 1

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,  # count detections
            mock_event_count,  # count events
            mock_gpu_stats_count,  # count gpu stats
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.dry_run_cleanup()

    # File doesn't exist, so no space is counted and no thumbnails counted
    assert stats.space_reclaimed == 0
    assert stats.thumbnails_deleted == 0


@pytest.mark.asyncio
async def test_dry_run_cleanup_oserror_on_stat(tmp_path):
    """Test dry_run_cleanup handles OSError when calling stat() on existing file."""
    service = CleanupService(retention_days=30, delete_images=True)

    # Create real files that we'll mock stat() errors on
    thumbnail = tmp_path / "thumb.jpg"
    image = tmp_path / "image.jpg"
    thumbnail.write_text("thumb data")
    image.write_text("image data")

    mock_detection = MockDetection(id=1, thumbnail_path=str(thumbnail), file_path=str(image))

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths
    mock_session.stream_scalars = create_stream_scalars_mock([mock_detection])

    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 1

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,  # count detections
            mock_event_count,  # count events
            mock_gpu_stats_count,  # count gpu stats
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    # Create a mock Path class that raises OSError on stat()
    original_path_stat = Path.stat

    def mock_stat(self):
        # Raise OSError for our specific test files
        if str(self).endswith(".jpg"):
            raise OSError("Permission denied")
        return original_path_stat(self)

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0, autospec=True),
        patch.object(Path, "stat", mock_stat),
    ):
        stats = await service.dry_run_cleanup()

    # Files exist and are counted, but space_reclaimed stays 0 due to OSError
    assert stats.thumbnails_deleted == 1
    assert stats.images_deleted == 1
    assert stats.space_reclaimed == 0  # OSError caught, space not counted


@pytest.mark.asyncio
async def test_dry_run_cleanup_exception():
    """Test dry_run_cleanup re-raises exceptions."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Database error"))

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        pytest.raises(Exception, match="Database error"),
    ):
        await service.dry_run_cleanup()


@pytest.mark.asyncio
async def test_dry_run_cleanup_delete_images_disabled(tmp_path):
    """Test dry_run_cleanup respects delete_images=False."""
    service = CleanupService(retention_days=30, delete_images=False)

    image = tmp_path / "image.jpg"
    image.write_text("image data")

    mock_detection = MockDetection(id=1, thumbnail_path=None, file_path=str(image))

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths
    mock_session.stream_scalars = create_stream_scalars_mock([mock_detection])

    # Use MagicMock for result objects
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 1

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,  # count detections
            mock_event_count,  # count events
            mock_gpu_stats_count,  # count gpu stats
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.dry_run_cleanup()

    # Image should NOT be counted since delete_images is False
    assert stats.images_deleted == 0


# =============================================================================
# _count_old_logs tests (lines 361-377)
# =============================================================================


@pytest.mark.asyncio
async def test_count_old_logs_with_logs():
    """Test _count_old_logs returns count of old logs."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        count = await service._count_old_logs()

    assert count == 42


@pytest.mark.asyncio
async def test_count_old_logs_no_logs():
    """Test _count_old_logs returns 0 when no old logs."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        count = await service._count_old_logs()

    assert count == 0


@pytest.mark.asyncio
async def test_count_old_logs_none_result():
    """Test _count_old_logs handles None result."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = None

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        count = await service._count_old_logs()

    assert count == 0


# =============================================================================
# cleanup_old_logs tests (lines 385-396)
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_old_logs_deletes_logs():
    """Test cleanup_old_logs deletes old logs and returns count."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.rowcount = 15

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        deleted = await service.cleanup_old_logs()

    assert deleted == 15
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_old_logs_no_logs_to_delete():
    """Test cleanup_old_logs when no logs need deletion."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.rowcount = 0

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        deleted = await service.cleanup_old_logs()

    assert deleted == 0
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_old_logs_none_rowcount():
    """Test cleanup_old_logs handles None rowcount."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.rowcount = None

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        deleted = await service.cleanup_old_logs()

    assert deleted == 0


# =============================================================================
# _cleanup_loop CancelledError tests (lines 452-453)
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_loop_cancelled():
    """Test cleanup loop handles CancelledError gracefully."""
    service = CleanupService()

    call_count = 0

    async def mock_wait():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Simulate task cancellation during wait
            raise asyncio.CancelledError()
        await asyncio.sleep(0.01)

    with patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait, autospec=True):
        service.running = True
        # Run the cleanup loop directly
        await service._cleanup_loop()

    # Loop should have exited cleanly
    assert call_count == 1


@pytest.mark.asyncio
async def test_cleanup_loop_stops_before_cleanup():
    """Test cleanup loop checks running flag before running cleanup."""
    service = CleanupService()

    cleanup_called = False

    async def mock_wait():
        # Stop service during wait
        service.running = False
        await asyncio.sleep(0.01)

    async def mock_cleanup():
        nonlocal cleanup_called
        cleanup_called = True
        return CleanupStats()

    with (
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait, autospec=True),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup, autospec=True),
    ):
        service.running = True
        await service._cleanup_loop()

    # Cleanup should NOT have been called since service stopped during wait
    assert not cleanup_called


# =============================================================================
# Additional edge case tests for better coverage
# =============================================================================


def test_delete_file_directory(tmp_path):
    """Test _delete_file returns False for directories."""
    service = CleanupService()

    # Create a directory instead of file
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    result = service._delete_file(str(test_dir))

    assert result is False
    assert test_dir.exists()


@pytest.mark.asyncio
async def test_run_cleanup_missing_thumbnail_file(tmp_path):
    """Test run_cleanup handles missing thumbnail files gracefully."""
    service = CleanupService(retention_days=30)

    # Detection points to non-existent file
    mock_detection = MockDetection(id=1, thumbnail_path="/nonexistent/path.jpg")

    mock_session = AsyncMock()

    # Mock stream_scalars for streaming detection file paths
    mock_session.stream_scalars = create_stream_scalars_mock([mock_detection])

    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 1

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_delete_result,  # delete detections
            mock_delete_result,  # delete events
            mock_delete_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.run_cleanup()

    # File didn't exist, so thumbnail count stays 0
    assert stats.thumbnails_deleted == 0


# =============================================================================
# Redis Job Status Tracking Tests (lines 156-180)
# =============================================================================


@pytest.mark.asyncio
async def test_run_cleanup_with_redis_job_tracking():
    """Test run_cleanup tracks job status via Redis."""
    mock_redis_client = AsyncMock()
    service = CleanupService(retention_days=30, redis_client=mock_redis_client)

    # Mock job status service
    mock_job_service = AsyncMock()
    mock_job_service.start_job = AsyncMock(return_value="cleanup-20250112-120000")
    mock_job_service.update_progress = AsyncMock()
    mock_job_service.complete_job = AsyncMock()

    # Mock session and database operations
    mock_session = AsyncMock()
    mock_session.stream_scalars = create_stream_scalars_mock([])

    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 5

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_delete_result,  # delete detections
            mock_delete_result,  # delete events
            mock_delete_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(
            service, "_get_job_status_service", return_value=mock_job_service, autospec=True
        ),
        patch.object(service, "cleanup_old_logs", return_value=10, autospec=True),
    ):
        stats = await service.run_cleanup()

    # Verify job tracking calls
    mock_job_service.start_job.assert_called_once()
    assert mock_job_service.update_progress.call_count >= 4  # Multiple progress updates
    mock_job_service.complete_job.assert_called_once()
    assert stats.detections_deleted == 5


@pytest.mark.asyncio
async def test_run_cleanup_with_redis_job_tracking_failure():
    """Test run_cleanup marks job as failed when exception occurs."""
    mock_redis_client = AsyncMock()
    service = CleanupService(retention_days=30, redis_client=mock_redis_client)

    # Mock job status service
    mock_job_service = AsyncMock()
    mock_job_service.start_job = AsyncMock(return_value="cleanup-20250112-120000")
    mock_job_service.update_progress = AsyncMock()
    mock_job_service.fail_job = AsyncMock()

    # Mock session that raises exception
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Database error"))

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(
            service, "_get_job_status_service", return_value=mock_job_service, autospec=True
        ),
        pytest.raises(Exception, match="Database error"),
    ):
        await service.run_cleanup()

    # Verify job was marked as failed
    mock_job_service.fail_job.assert_called_once_with("cleanup-20250112-120000", "Database error")


def test_get_job_status_service_without_redis():
    """Test _get_job_status_service returns None when no Redis client."""
    service = CleanupService(retention_days=30)

    result = service._get_job_status_service()

    assert result is None


def test_get_job_status_service_with_redis():
    """Test _get_job_status_service creates service with Redis client."""
    mock_redis_client = AsyncMock()
    service = CleanupService(retention_days=30, redis_client=mock_redis_client)

    mock_job_service = MagicMock()

    with patch("backend.services.job_status.get_job_status_service", autospec=True) as mock_get:
        mock_get.return_value = mock_job_service

        result = service._get_job_status_service()

        assert result is mock_job_service
        mock_get.assert_called_once_with(mock_redis_client)


def test_get_job_status_service_caching():
    """Test _get_job_status_service caches the service instance."""
    mock_redis_client = AsyncMock()
    service = CleanupService(retention_days=30, redis_client=mock_redis_client)

    mock_job_service = MagicMock()

    with patch("backend.services.job_status.get_job_status_service", autospec=True) as mock_get:
        mock_get.return_value = mock_job_service

        # First call
        result1 = service._get_job_status_service()
        # Second call
        result2 = service._get_job_status_service()

        assert result1 is result2
        # Should only be called once due to caching
        mock_get.assert_called_once()


def test_set_redis_client():
    """Test set_redis_client updates Redis client and resets cache."""
    service = CleanupService(retention_days=30)

    # Set initial Redis client
    mock_redis_client1 = AsyncMock()
    service.set_redis_client(mock_redis_client1)

    assert service._redis_client is mock_redis_client1
    assert service._job_status_service is None

    # Simulate caching by setting job status service
    service._job_status_service = MagicMock()

    # Set new Redis client
    mock_redis_client2 = AsyncMock()
    service.set_redis_client(mock_redis_client2)

    assert service._redis_client is mock_redis_client2
    assert service._job_status_service is None  # Cache cleared


# =============================================================================
# Async Context Manager Tests (lines 613-645)
# =============================================================================


@pytest.mark.asyncio
async def test_async_context_manager():
    """Test CleanupService can be used as async context manager."""
    service = CleanupService(retention_days=30)

    assert not service.running

    async with service as ctx_service:
        assert ctx_service is service
        assert service.running is True

    # Should be stopped after exiting context
    assert service.running is False


@pytest.mark.asyncio
async def test_async_context_manager_with_exception():
    """Test async context manager stops service even when exception occurs."""
    service = CleanupService(retention_days=30)

    with pytest.raises(ValueError, match="Test error"):
        async with service:
            assert service.running is True
            raise ValueError("Test error")

    # Should still be stopped after exception
    assert service.running is False


# =============================================================================
# format_bytes utility tests (lines 648-670)
# =============================================================================


def test_format_bytes_negative():
    """Test format_bytes handles negative values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(-100)

    assert result == "0 B"


def test_format_bytes_zero():
    """Test format_bytes handles zero."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(0)

    assert result == "0 B"


def test_format_bytes_small():
    """Test format_bytes formats small byte values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(512)

    assert result == "512 B"


def test_format_bytes_kilobytes():
    """Test format_bytes formats KB values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(1024)

    assert result == "1.00 KB"


def test_format_bytes_megabytes():
    """Test format_bytes formats MB values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(1024 * 1024)

    assert result == "1.00 MB"


def test_format_bytes_gigabytes():
    """Test format_bytes formats GB values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(1024 * 1024 * 1024)

    assert result == "1.00 GB"


def test_format_bytes_terabytes():
    """Test format_bytes formats TB values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(1024 * 1024 * 1024 * 1024)

    assert result == "1.00 TB"


def test_format_bytes_petabytes():
    """Test format_bytes formats PB values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(1024 * 1024 * 1024 * 1024 * 1024)

    assert result == "1.00 PB"


def test_format_bytes_max_unit():
    """Test format_bytes stops at PB for very large values."""
    from backend.services.cleanup_service import format_bytes

    # Should not go beyond PB
    result = format_bytes(1024**6)

    assert "PB" in result


def test_format_bytes_fractional():
    """Test format_bytes formats fractional values."""
    from backend.services.cleanup_service import format_bytes

    result = format_bytes(1536)  # 1.5 KB

    assert result == "1.50 KB"


# =============================================================================
# OrphanedFileCleanupStats Tests (lines 673-704)
# =============================================================================


def test_orphaned_file_cleanup_stats_initialization():
    """Test OrphanedFileCleanupStats initializes with zero values."""
    from backend.services.cleanup_service import OrphanedFileCleanupStats

    stats = OrphanedFileCleanupStats()

    assert stats.orphaned_count == 0
    assert stats.total_size == 0
    assert stats.dry_run is True
    assert stats.orphaned_files == []


def test_orphaned_file_cleanup_stats_to_dict():
    """Test OrphanedFileCleanupStats converts to dictionary."""
    from backend.services.cleanup_service import OrphanedFileCleanupStats

    stats = OrphanedFileCleanupStats()
    stats.orphaned_count = 10
    stats.total_size = 5000
    stats.dry_run = False
    stats.orphaned_files = ["/path/1.jpg", "/path/2.jpg"]

    result = stats.to_dict()

    assert result["orphaned_count"] == 10
    assert result["total_size"] == 5000
    assert result["total_size_formatted"] == "4.88 KB"
    assert result["dry_run"] is False
    assert result["orphaned_files"] == ["/path/1.jpg", "/path/2.jpg"]


def test_orphaned_file_cleanup_stats_to_dict_limits_files():
    """Test OrphanedFileCleanupStats limits file list to 100 entries."""
    from backend.services.cleanup_service import OrphanedFileCleanupStats

    stats = OrphanedFileCleanupStats()
    stats.orphaned_files = [f"/path/{i}.jpg" for i in range(200)]

    result = stats.to_dict()

    # Should only include first 100 files
    assert len(result["orphaned_files"]) == 100


def test_orphaned_file_cleanup_stats_repr():
    """Test OrphanedFileCleanupStats string representation."""
    from backend.services.cleanup_service import OrphanedFileCleanupStats

    stats = OrphanedFileCleanupStats()
    stats.orphaned_count = 5
    stats.total_size = 1024000

    repr_str = repr(stats)

    assert "OrphanedFileCleanupStats" in repr_str
    assert "orphaned_count=5" in repr_str
    assert "1000.00 KB" in repr_str or "0.98 MB" in repr_str
    assert "dry_run=True" in repr_str


# =============================================================================
# OrphanedFileCleanup Tests (lines 707-921)
# =============================================================================


def test_orphaned_file_cleanup_initialization():
    """Test OrphanedFileCleanup initializes with default storage paths."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    mock_settings = MagicMock()
    mock_settings.video_thumbnails_dir = "/data/thumbnails"
    mock_settings.clips_directory = "/data/clips"

    with patch(
        "backend.services.cleanup_service.get_settings", return_value=mock_settings, autospec=True
    ):
        cleanup = OrphanedFileCleanup()

    assert "/data/thumbnails" in cleanup._storage_paths
    assert "/data/clips" in cleanup._storage_paths


def test_orphaned_file_cleanup_custom_storage_paths():
    """Test OrphanedFileCleanup accepts custom storage paths."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    custom_paths = ["/custom/path1", "/custom/path2"]
    cleanup = OrphanedFileCleanup(storage_paths=custom_paths)

    assert cleanup._storage_paths == custom_paths


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_get_referenced_files():
    """Test _get_referenced_files queries database for all file references."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    cleanup = OrphanedFileCleanup(storage_paths=["/test"])

    # Mock database results
    mock_session = AsyncMock()

    # Mock detection query
    detection_result = MagicMock()
    detection_result.all.return_value = [
        ("/path/image1.jpg", "/path/thumb1.jpg"),
        ("/path/image2.jpg", None),
        (None, "/path/thumb2.jpg"),
    ]

    # Mock event query
    event_result = MagicMock()
    event_result.all.return_value = [
        ("/path/clip1.mp4",),
        ("/path/clip2.mp4",),
    ]

    mock_session.execute = AsyncMock(side_effect=[detection_result, event_result])

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        referenced = await cleanup._get_referenced_files()

    # Should include all file paths (converted to absolute)
    assert len(referenced) >= 5


def test_orphaned_file_cleanup_scan_storage_directories(tmp_path):
    """Test _scan_storage_directories finds all files recursively."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test directory structure
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    file1 = dir1 / "file1.jpg"
    file2 = dir2 / "file2.jpg"
    file3 = dir2 / "subdir" / "file3.jpg"
    file3.parent.mkdir()

    file1.write_text("test1")
    file2.write_text("test2")
    file3.write_text("test3")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    files = cleanup._scan_storage_directories()

    # Should find all 3 files
    assert len(files) == 3
    file_paths = [f[0] for f in files]
    assert any("file1.jpg" in p for p in file_paths)
    assert any("file2.jpg" in p for p in file_paths)
    assert any("file3.jpg" in p for p in file_paths)


def test_orphaned_file_cleanup_scan_nonexistent_directory():
    """Test _scan_storage_directories handles nonexistent directories."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    cleanup = OrphanedFileCleanup(storage_paths=["/nonexistent/path"])

    files = cleanup._scan_storage_directories()

    # Should return empty list without error
    assert files == []


def test_orphaned_file_cleanup_scan_file_instead_of_directory(tmp_path):
    """Test _scan_storage_directories handles file paths."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create a file instead of directory
    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    cleanup = OrphanedFileCleanup(storage_paths=[str(test_file)])

    files = cleanup._scan_storage_directories()

    # Should return empty list (not a directory)
    assert files == []


def test_orphaned_file_cleanup_scan_with_stat_error(tmp_path):
    """Test _scan_storage_directories handles stat errors gracefully."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test file
    test_file = tmp_path / "test.jpg"
    test_file.write_text("test")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock stat to raise OSError
    original_stat = Path.stat

    def mock_stat(self):
        if self.name == "test.jpg":
            raise OSError("Permission denied")
        return original_stat(self)

    with patch.object(Path, "stat", mock_stat):
        files = cleanup._scan_storage_directories()

    # Should handle error and return empty list
    assert files == []


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_run_dry_run(tmp_path):
    """Test run_cleanup in dry run mode identifies but doesn't delete files."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test files
    orphaned1 = tmp_path / "orphaned1.jpg"
    orphaned2 = tmp_path / "orphaned2.jpg"
    referenced = tmp_path / "referenced.jpg"

    orphaned1.write_text("o" * 1000)
    orphaned2.write_text("o" * 2000)
    referenced.write_text("r" * 5000)

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock _get_referenced_files to return only the referenced file
    async def mock_get_referenced():
        return {str(referenced.resolve())}

    with patch.object(
        cleanup, "_get_referenced_files", side_effect=mock_get_referenced, autospec=True
    ):
        stats = await cleanup.run_cleanup(dry_run=True)

    # Should identify orphaned files
    assert stats.orphaned_count == 2
    assert stats.total_size == 3000
    assert stats.dry_run is True

    # Files should still exist (dry run)
    assert orphaned1.exists()
    assert orphaned2.exists()


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_run_delete(tmp_path):
    """Test run_cleanup in delete mode removes orphaned files."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test files
    orphaned1 = tmp_path / "orphaned1.jpg"
    orphaned2 = tmp_path / "orphaned2.jpg"
    referenced = tmp_path / "referenced.jpg"

    orphaned1.write_text("orphaned")
    orphaned2.write_text("orphaned")
    referenced.write_text("referenced")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock _get_referenced_files
    async def mock_get_referenced():
        return {str(referenced.resolve())}

    with patch.object(
        cleanup, "_get_referenced_files", side_effect=mock_get_referenced, autospec=True
    ):
        stats = await cleanup.run_cleanup(dry_run=False)

    # Should identify and delete orphaned files
    assert stats.orphaned_count == 2
    assert stats.dry_run is False

    # Orphaned files should be deleted
    assert not orphaned1.exists()
    assert not orphaned2.exists()
    # Referenced file should still exist
    assert referenced.exists()


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_with_job_tracker(tmp_path):
    """Test run_cleanup reports progress via job tracker."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    mock_job_tracker = MagicMock()
    mock_job_tracker.create_job = MagicMock(return_value="job-123")
    mock_job_tracker.start_job = MagicMock()
    mock_job_tracker.complete_job = MagicMock()

    cleanup = OrphanedFileCleanup(job_tracker=mock_job_tracker, storage_paths=[str(tmp_path)])

    # Mock _get_referenced_files
    async def mock_get_referenced():
        return set()

    with patch.object(
        cleanup, "_get_referenced_files", side_effect=mock_get_referenced, autospec=True
    ):
        stats = await cleanup.run_cleanup(dry_run=True)

    # Verify job tracker calls
    mock_job_tracker.create_job.assert_called_once_with("orphaned_file_cleanup")
    mock_job_tracker.start_job.assert_called_once()
    mock_job_tracker.complete_job.assert_called_once()


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_exception_handling():
    """Test run_cleanup handles exceptions and fails job."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    mock_job_tracker = MagicMock()
    mock_job_tracker.create_job = MagicMock(return_value="job-123")
    mock_job_tracker.start_job = MagicMock()
    mock_job_tracker.fail_job = MagicMock()

    cleanup = OrphanedFileCleanup(job_tracker=mock_job_tracker, storage_paths=["/test"])

    # Mock _get_referenced_files to raise exception
    async def mock_get_referenced_error():
        raise Exception("Database error")

    with (
        patch.object(
            cleanup, "_get_referenced_files", side_effect=mock_get_referenced_error, autospec=True
        ),
        pytest.raises(Exception, match="Database error"),
    ):
        await cleanup.run_cleanup(dry_run=True)

    # Verify job was marked as failed
    mock_job_tracker.fail_job.assert_called_once_with("job-123", "Database error")


def test_orphaned_file_cleanup_update_job_progress_without_tracker():
    """Test _update_job_progress handles missing job tracker gracefully."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    cleanup = OrphanedFileCleanup(storage_paths=["/test"])

    # Should not raise error
    cleanup._update_job_progress("job-123", 50, "Test message")


def test_orphaned_file_cleanup_update_job_progress_with_tracker():
    """Test _update_job_progress calls job tracker when available."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    mock_job_tracker = MagicMock()
    cleanup = OrphanedFileCleanup(job_tracker=mock_job_tracker, storage_paths=["/test"])

    cleanup._update_job_progress("job-123", 50, "Test message")

    mock_job_tracker.update_progress.assert_called_once_with("job-123", 50, "Test message")


def test_orphaned_file_cleanup_delete_orphaned_files(tmp_path):
    """Test _delete_orphaned_files removes files and returns count."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test files
    file1 = tmp_path / "file1.jpg"
    file2 = tmp_path / "file2.jpg"
    file1.write_text("test1")
    file2.write_text("test2")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    orphaned_files = [(str(file1), 100), (str(file2), 200)]
    deleted_count = cleanup._delete_orphaned_files(orphaned_files)

    assert deleted_count == 2
    assert not file1.exists()
    assert not file2.exists()


def test_orphaned_file_cleanup_delete_orphaned_files_with_error(tmp_path):
    """Test _delete_orphaned_files handles deletion errors gracefully."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test file
    file1 = tmp_path / "file1.jpg"
    file1.write_text("test")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock unlink to raise error
    with patch.object(Path, "unlink", side_effect=OSError("Permission denied"), autospec=True):
        orphaned_files = [(str(file1), 100)]
        deleted_count = cleanup._delete_orphaned_files(orphaned_files)

    # Should return 0 since deletion failed
    assert deleted_count == 0
    # File should still exist
    assert file1.exists()


# =============================================================================
# Consolidated from test_cleanup_cutoff_kill.py & test_cleanup_service_batch35_l.py (B4.4 step 2)
# =============================================================================


class _CapturingStmt:
    """Stands in for delete(model): records (operator, cutoff bound) per .where().

    The operator is captured too: :283/:294/:303 all compare `col < cutoff_date`,
    and a < -> > mutant inverts which rows the DELETE claims (hoards expired
    footage / spares evidence) without changing the bound value at all."""

    def __init__(self, sink: list) -> None:
        self._sink = sink

    def where(self, clause):
        # col < cutoff  ->  BinaryExpression.right is the BindParameter
        right = getattr(clause, "right", None)
        self._sink.append((getattr(clause, "operator", None), getattr(right, "value", "UNBOUND")))
        return self


@pytest.fixture
def jobless_service():
    """CleanupService with the Redis job-tracking path closed off."""
    from backend.services.cleanup_service import CleanupService

    svc = CleanupService(
        cleanup_time="03:00",
        retention_days=30,
        thumbnail_dir="data/thumbnails",
        delete_images=False,
    )
    svc._get_job_status_service = MagicMock(return_value=None)
    return svc


@pytest.mark.asyncio
async def test_run_cleanup_deletes_exactly_at_retention_cutoff(jobless_service):
    """ALL THREE delete bounds == now-30d, tz-aware — the :266 arithmetic
    pinned at the place it is consumed (the DELETE), not where it is computed."""
    bounds: list = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    from backend.services import cleanup_service as cs

    with (
        patch.object(cs, "get_session", autospec=True, return_value=cm),
        patch.object(
            cs, "delete", autospec=True, side_effect=lambda _model: _CapturingStmt(bounds)
        ),
        patch.object(
            jobless_service,
            "_get_detection_file_paths_streaming",
            new=AsyncMock(return_value=([], [])),
        ),
        patch.object(jobless_service, "cleanup_old_logs", new=AsyncMock(return_value=0)),
    ):
        before = datetime.now(UTC)
        stats = await jobless_service.run_cleanup()
        after = datetime.now(UTC)

    assert stats is not None
    assert len(bounds) == 3, f"Detection+Event+GPUStats deletes expected, got {bounds!r}"
    lo, hi = before - timedelta(days=30), after - timedelta(days=30)
    for op, b in bounds:
        # operator.lt is a builtin function object, not a type — identity check
        assert op is lt, f"delete clause must be `col < cutoff`, got {op!r}"
        assert isinstance(b, datetime), f"delete bound is not a datetime: {b!r}"
        assert b.tzinfo is not None, f"cutoff must be tz-aware UTC (now(UTC)): {b!r}"
        assert lo <= b <= hi, (
            f"delete bound {b} outside [{lo}, {hi}] — run_cleanup :266 cutoff "
            "arithmetic is mutated (WP3.2 silent-data-loss mutant)"
        )


@pytest.mark.asyncio
async def test_run_cleanup_cutoff_uses_instance_retention_not_default(jobless_service):
    """retention_days is per-instance config; a mutant hardwiring 30 (or any
    constant) while the instance says 7 must be caught — the bound follows
    the INSTANCE value."""
    jobless_service.retention_days = 7
    bounds: list = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    from backend.services import cleanup_service as cs

    with (
        patch.object(cs, "get_session", autospec=True, return_value=cm),
        patch.object(
            cs, "delete", autospec=True, side_effect=lambda _model: _CapturingStmt(bounds)
        ),
        patch.object(
            jobless_service,
            "_get_detection_file_paths_streaming",
            new=AsyncMock(return_value=([], [])),
        ),
        patch.object(jobless_service, "cleanup_old_logs", new=AsyncMock(return_value=0)),
    ):
        before = datetime.now(UTC)
        await jobless_service.run_cleanup()
        after = datetime.now(UTC)

    lo, hi = before - timedelta(days=7), after - timedelta(days=7)
    assert bounds and all(lo <= b <= hi for _op, b in bounds), (
        f"cutoff must follow instance retention (7d): {bounds!r}"
    )


MISS = object()
PIN = datetime(2026, 9, 15, 12, 0, 0, 0, tzinfo=UTC)
PIN_A = datetime(2026, 9, 15, 12, 7, 9, 123456, tzinfo=UTC)  # nonzero sec/micro
JOBS = "cleanup-20260915-120000"
RET = 30
LOG_RET = 7
DET_CUT = PIN - timedelta(days=RET)  # 2026-08-16 12:00+00:00
LOG_CUT = PIN - timedelta(days=LOG_RET)  # 2026-09-08 12:00+00:00
NOWHERE = "/nonexistent-orphan-zz"
SLEEPS: list[object] = []
TASK_NAMES: list[object] = []

INFO = logging.INFO
WARNING = logging.WARNING
DEBUG = logging.DEBUG
ERROR = logging.ERROR


def _attempt(coro):
    """Run a coroutine to completion; battery red = ANY escaping exception."""
    import asyncio

    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# log capture -- exact ordered (level, message) lists
# ---------------------------------------------------------------------------
class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextlib.contextmanager
def _capture_logs():
    """Capture through the MODULE logger only; propagate=False keeps suite-
    order ambient handlers/formatters from mutating records (K-era lesson)."""
    cap = _Capture()
    handlers = cs.logger.handlers[:]
    cs.logger.handlers[:] = [cap]
    prev, prev_prop = cs.logger.level, cs.logger.propagate
    cs.logger.setLevel(logging.DEBUG)
    cs.logger.propagate = False
    try:
        yield cap
    finally:
        cs.logger.handlers[:] = handlers
        cs.logger.setLevel(prev)
        cs.logger.propagate = prev_prop


def _assert_msgs(cap, expected):
    got = [(r.levelno, r.getMessage()) for r in cap.records]
    assert got == list(expected), got


# ---------------------------------------------------------------------------
# swaps (direct module-attribute swaps, K-era pattern)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _attr(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield old
    finally:
        setattr(obj, name, old)


class _Settings:
    retention_days = 44
    log_retention_days = LOG_RET


@contextlib.contextmanager
def _pinned():
    """Pinned settings for BOTH construction time and call time (the
    await-time-getter rule: _count_old_logs/cleanup_old_logs read
    get_settings() INSIDE the awaited call)."""
    with _attr(cs, "get_settings", lambda: _Settings()):
        yield


class _Clock:
    """Replaces cs.datetime. now(tz) RECORDS the tz argument identity and
    returns a REAL datetime -- naive when tz is None -- so naive-vs-aware
    mutants change downstream param reprs, not just metadata."""

    def __init__(self, when: datetime) -> None:
        self.when = when
        self.tzs: list[object] = []

    def now(self, tz=MISS):
        self.tzs.append(tz)
        if tz is None or tz is MISS:
            return self.when.replace(tzinfo=None)
        return self.when

    def __getattr__(self, item):
        return getattr(datetime, item)


@contextlib.contextmanager
def _clocked(when: datetime):
    clk = _Clock(when)
    with _attr(cs, "datetime", clk):
        yield clk


def _svc(cls=None, **kw):
    with _pinned():
        return (cls or cs.CleanupService)(**kw)


def _osvc(**kw):
    with _pinned():
        return cs.OrphanedFileCleanup(**kw)


# ---------------------------------------------------------------------------
# SQL digest -- recorded in the MUTANT world, compared to the same function
# run in the TEST world over identically built statements.
# ---------------------------------------------------------------------------
def _dig(stmt):
    if stmt is None:
        return ("NONE",)
    table = getattr(getattr(stmt, "table", None), "name", None)
    try:
        sql = " ".join(str(stmt).split())
    except Exception as exc:
        sql = "RAISE:" + type(exc).__name__
    try:
        params = tuple(sorted(repr(v) for v in stmt.compile().params.values()))
    except Exception as exc:
        params = ("RAISE:" + type(exc).__name__,)
    try:
        cols = tuple(
            (d["name"], getattr(d["expr"], "key", repr(d["expr"])))
            for d in stmt.column_descriptions
        )
    except Exception as exc:
        cols = ("RAISE:" + type(exc).__name__,)
    return (type(stmt).__name__, table, sql, params, cols)


def _dig_count(col, model, cutoff):
    from sqlalchemy import func

    return _dig(select(func.count()).select_from(model).where(col < cutoff))


def _dig_model(col, model, cutoff):
    return _dig(select(model).where(col < cutoff))


def _dig_delete(model, col, cutoff):
    from sqlalchemy import delete

    return _dig(delete(model).where(col < cutoff))


DIG_DET_COUNT = _dig_count(Detection.detected_at, Detection, DET_CUT)
DIG_DET_QUERY = _dig_model(Detection.detected_at, Detection, DET_CUT)
DIG_EVT_COUNT = _dig_count(Event.started_at, Event, DET_CUT)
DIG_GPU_COUNT = _dig_count(GPUStats.recorded_at, GPUStats, DET_CUT)
DIG_DEL_DET = _dig_delete(Detection, Detection.detected_at, DET_CUT)
DIG_DEL_EVT = _dig_delete(Event, Event.started_at, DET_CUT)
DIG_DEL_GPU = _dig_delete(GPUStats, GPUStats.recorded_at, DET_CUT)
DIG_LOG_COUNT = _dig_count(Log.timestamp, Log, LOG_CUT)
DIG_DEL_LOG = _dig_delete(Log, Log.timestamp, LOG_CUT)
DIG_REF_DET = _dig(select(Detection.file_path, Detection.thumbnail_path))
DIG_REF_EVT = _dig(select(Event.clip_path).where(Event.clip_path.isnot(None)))


# ---------------------------------------------------------------------------
# recorder session + job stand-ins
# ---------------------------------------------------------------------------
class _Res:
    def __init__(self, rowcount=None, scalar=None) -> None:
        self.rowcount = rowcount
        self._scalar = scalar

    def scalar_one(self):
        return self._scalar


class _Rows:
    def __init__(self, rows) -> None:
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _Sess:
    def __init__(self, results=(), rows=(), raise_at=()) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.commits = 0
        self._results = list(results)
        self._rows = list(rows)
        self._raise_at = set(raise_at)

    async def execute(self, stmt):
        idx = sum(1 for c in self.calls if c[0] == "execute")
        self.calls.append(("execute", _dig(stmt)))
        if idx in self._raise_at:
            raise RuntimeError("boom")
        return self._results.pop(0)

    async def stream_scalars(self, stmt):
        self.calls.append(("stream", _dig(stmt)))
        rows = list(self._rows)

        async def agen():
            for r in rows:
                yield r

        return agen()

    async def commit(self):
        self.commits += 1


@contextlib.contextmanager
def _session(sess):
    @contextlib.asynccontextmanager
    async def factory():
        yield sess

    with _attr(cs, "get_session", factory):
        yield sess


class _Job:
    """JobStatusService stand-in: async methods, COMPLETE call list."""

    def __init__(self, job_id="J1") -> None:
        self.calls: list[tuple] = []
        self._job_id = job_id

    async def start_job(self, *args, **kwargs):
        self.calls.append(("start_job", args, kwargs))
        return self._job_id

    async def update_progress(self, *args, **kwargs):
        self.calls.append(("update_progress", args, kwargs))

    async def complete_job(self, *args, **kwargs):
        self.calls.append(("complete_job", args, kwargs))

    async def fail_job(self, *args, **kwargs):
        self.calls.append(("fail_job", args, kwargs))


def _tracked(svc, job):
    svc._redis_client = object()
    svc._job_status_service = job
    return svc


class _Track:
    """JobTracker stand-in (sync methods)."""

    def __init__(self, job_id="T1") -> None:
        self.calls: list[tuple] = []
        self._job_id = job_id

    def create_job(self, *args, **kwargs):
        self.calls.append(("create_job", args, kwargs))
        return self._job_id

    def start_job(self, *args, **kwargs):
        self.calls.append(("start_job", args, kwargs))

    def update_progress(self, *args, **kwargs):
        self.calls.append(("update_progress", args, kwargs))

    def complete_job(self, *args, **kwargs):
        self.calls.append(("complete_job", args, kwargs))

    def fail_job(self, *args, **kwargs):
        self.calls.append(("fail_job", args, kwargs))


class _Task:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def __await__(self):
        async def _die():
            import asyncio

            raise asyncio.CancelledError

        return _die().__await__()


class _AS:
    """cs.asyncio shim: REAL CancelledError, observed sleep/create_task."""

    @staticmethod
    def sleep(delay, result=None):
        SLEEPS.append(delay)

        async def _go():
            return result

        return _go()

    @staticmethod
    def create_task(coro, name=MISS):
        TASK_NAMES.append(name)
        coro.close()
        return _Task()


@contextlib.contextmanager
def _shim_asyncio():
    import asyncio

    SLEEPS.clear()
    TASK_NAMES.clear()
    shim = types.SimpleNamespace(
        CancelledError=asyncio.CancelledError,
        sleep=_AS.sleep,
        create_task=_AS.create_task,
    )
    with _attr(cs, "asyncio", shim):
        yield


def _det(thumb=MISS, file=MISS):
    return types.SimpleNamespace(
        thumbnail_path=None if thumb is MISS else thumb,
        file_path=None if file is MISS else file,
    )


class _SvcNL(cs.CleanupService):
    """run_cleanup tests stub the log-deletion leg (it opens its own session
    for the DELETE statement; cleanup_old_logs mutants have their own tests)."""

    async def cleanup_old_logs(self) -> int:
        return 41


# ---------------------------------------------------------------------------
# CleanupService.run_cleanup -- job tracking, SQL digests, messages
# ---------------------------------------------------------------------------
def test_run_cleanup_tracked_exact_calls_messages_and_digests():
    """Kills the update_progress/start_job arg+message families, every
    happy-polarity guard twin, execute(None) delete mutants, cutoff mutants,
    and the log-message families of run_cleanup."""
    svc = _svc(cls=_SvcNL, retention_days=RET)
    job = _Job(JOBS)
    _tracked(svc, job)
    sess = _Sess(results=[_Res(rowcount=5), _Res(rowcount=3), _Res(rowcount=100)])
    with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
        stats = _attempt(svc.run_cleanup())
    assert clk.tzs == [UTC, UTC], clk.tzs
    assert stats.to_dict() == {
        "events_deleted": 3,
        "detections_deleted": 5,
        "gpu_stats_deleted": 100,
        "logs_deleted": 41,
        "thumbnails_deleted": 0,
        "images_deleted": 0,
        "space_reclaimed": 0,
    }
    up = "update_progress"
    assert job.calls == [
        (
            "start_job",
            (),
            {"job_id": JOBS, "job_type": "data_cleanup", "metadata": {"retention_days": 30}},
        ),
        (up, (JOBS, 5, "Scanning for files to delete"), {}),
        (up, (JOBS, 15, "Deleting old detections"), {}),
        (up, (JOBS, 30, "Deleting old events"), {}),
        (up, (JOBS, 45, "Deleting old GPU stats"), {}),
        (up, (JOBS, 55, "Deleting old logs"), {}),
        (up, (JOBS, 70, "Deleting thumbnail files"), {}),
        ("complete_job", (JOBS,), {"result": stats.to_dict()}),
    ]
    assert sess.calls == [
        ("stream", DIG_DET_QUERY),
        ("execute", DIG_DEL_DET),
        ("execute", DIG_DEL_EVT),
        ("execute", DIG_DEL_GPU),
    ]
    assert sess.commits == 1
    _assert_msgs(
        cap,
        [
            (INFO, "Starting cleanup (retention: 30 days)"),
            (INFO, "Deleting records older than " + str(DET_CUT)),
            (INFO, "Deleted 5 old detections"),
            (INFO, "Deleted 3 old events"),
            (INFO, "Deleted 100 old GPU stats"),
            (INFO, "Database cleanup committed successfully"),
            (INFO, "Deleted 0 thumbnail files"),
            (INFO, "Cleanup completed: " + str(stats)),
        ],
    )


def test_run_cleanup_files_and_delete_images_call_list():
    with tempfile.TemporaryDirectory() as td:
        t1 = Path(td) / "t1.jpg"
        t1.write_text("t1")
        i1 = Path(td) / "i1.jpg"
        i1.write_text("img1")
        svc = _svc(cls=_SvcNL, retention_days=RET, delete_images=True)
        job = _Job(JOBS)
        _tracked(svc, job)
        rows = [_det(thumb=str(t1), file=str(i1)), _det()]
        sess = _Sess(results=[_Res(rowcount=1), _Res(rowcount=1), _Res(rowcount=1)], rows=rows)
        with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
            stats = _attempt(svc.run_cleanup())
        assert (not t1.exists()) and (not i1.exists())
        assert stats.thumbnails_deleted == 1 and stats.images_deleted == 1
        up = "update_progress"
        assert job.calls[-2] == (up, (JOBS, 85, "Deleting image files"), {})
        assert job.calls[-1] == ("complete_job", (JOBS,), {"result": stats.to_dict()})
        # the delete_images=True path is the ONLY one that reaches the
        # "Deleted N original image files" line -- capture its full ordered
        # log so that line's message mutants (None/XX/case) cannot hide.
        _assert_msgs(
            cap,
            [
                (INFO, "Starting cleanup (retention: 30 days)"),
                (INFO, "Deleting records older than " + str(DET_CUT)),
                (INFO, "Deleted 1 old detections"),
                (INFO, "Deleted 1 old events"),
                (INFO, "Deleted 1 old GPU stats"),
                (INFO, "Database cleanup committed successfully"),
                (INFO, "Deleted 1 thumbnail files"),
                (INFO, "Deleted 1 original image files"),
                (INFO, "Cleanup completed: " + str(stats)),
            ],
        )


def test_run_cleanup_startjob_none_polarity_zero_side_calls():
    """start_job returns None: shipped makes NO update/complete/fail call;
    the 'or' guard twins call update_progress(None, ...)/complete_job(None,
    ...) and land RED here (files present so the 85% block is live)."""
    with tempfile.TemporaryDirectory() as td:
        t1 = Path(td) / "t1.jpg"
        t1.write_text("t1")
        svc = _svc(cls=_SvcNL, retention_days=RET, delete_images=True)
        job = _Job(None)
        _tracked(svc, job)
        rows = [_det(thumb=str(t1))]
        sess = _Sess(results=[_Res(rowcount=1), _Res(rowcount=1), _Res(rowcount=1)], rows=rows)
        with _pinned(), _clocked(PIN), _session(sess):
            _attempt(svc.run_cleanup())
        assert [c for c in job.calls if c[0] != "start_job"] == [], job.calls


def test_run_cleanup_untracked_untouched_by_guard_twins():
    """job_service None polarity: the 'job_service is None and ...' twins
    would call update_progress on None -> AttributeError inside the try ->
    the error path; shipped just runs and commits."""
    sess = _Sess(results=[_Res(rowcount=0), _Res(rowcount=0), _Res(rowcount=0)])
    svc = _svc(cls=_SvcNL, retention_days=RET)
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        stats = _attempt(svc.run_cleanup())
    assert sess.commits == 1
    assert stats.logs_deleted == 41
    assert [(r.levelno, r.getMessage()) for r in cap.records][1] == (
        INFO,
        "Deleting records older than " + str(DET_CUT),
    )


def test_run_cleanup_failure_logs_error_with_exc_info_and_fails_job():
    svc = _svc(cls=_SvcNL, retention_days=RET)
    job = _Job(JOBS)
    _tracked(svc, job)
    sess = _Sess(results=[], rows=[], raise_at={0})
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        try:
            _attempt(svc.run_cleanup())
            raise AssertionError("must re-raise")
        except RuntimeError as exc:
            assert exc.args == ("boom",)
    assert job.calls[-1] == ("fail_job", (JOBS, "boom"), {})
    err = cap.records[-1]
    assert err.levelno == ERROR
    assert err.getMessage() == "Cleanup failed: boom"
    assert err.exc_info[0] is RuntimeError and err.exc_info[1].args == ("boom",)


def test_run_cleanup_failure_none_polarity_no_fail_call():
    """start_job -> None + exception: shipped skips fail_job; the L349 'or'
    twin calls fail_job(None, 'boom')."""
    svc = _svc(cls=_SvcNL, retention_days=RET)
    job = _Job(None)
    _tracked(svc, job)
    sess = _Sess(results=[], rows=[], raise_at={0})
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        try:
            _attempt(svc.run_cleanup())
            raise AssertionError("must re-raise")
        except RuntimeError:
            pass
    assert [c for c in job.calls if c[0] != "start_job"] == [], job.calls
    err = cap.records[-1]
    assert err.getMessage() == "Cleanup failed: boom"
    assert err.exc_info[1].args == ("boom",)


# ---------------------------------------------------------------------------
# _delete_file
# ---------------------------------------------------------------------------
def test_delete_file_true_for_real_file():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.bin"
        f.write_text("x")
        svc = _svc()
        assert svc._delete_file(str(f)) is True
        assert not f.exists()


def test_delete_file_directory_takes_debug_not_unlink():
    """and -> or: the OR lets a DIRECTORY through to unlink(), replacing the
    shipped debug line with a failure warning (is_file() is os.path.isdir-
    backed, so overriding stat() cannot fake this -- a real dir is needed)."""
    with tempfile.TemporaryDirectory() as td:
        svc = _svc()
        with _capture_logs() as cap:
            assert svc._delete_file(td) is False
        _assert_msgs(cap, [(DEBUG, "File not found or not a file: " + td)])


def test_delete_file_missing_takes_debug_path():
    svc = _svc()
    with _capture_logs() as cap:
        assert svc._delete_file(NOWHERE + "/x.bin") is False
    _assert_msgs(cap, [(DEBUG, "File not found or not a file: " + NOWHERE + "/x.bin")])


class _NoUnlink(Path):
    def unlink(self, missing_ok=False):
        if self.name == "noclean.bin":
            raise OSError("nope")
        return super().unlink(missing_ok=missing_ok)


def test_delete_file_unlink_failure_warns_with_exc_info():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "noclean.bin"
        f.write_text("x")
        svc = _svc()
        with _attr(cs, "Path", _NoUnlink), _capture_logs() as cap:
            assert svc._delete_file(str(f)) is False
        assert len(cap.records) == 1
        rec = cap.records[0]
        assert rec.levelno == WARNING
        assert rec.getMessage() == "Failed to delete file " + str(f) + ": nope"
        assert rec.exc_info[0] is OSError and rec.exc_info[1].args == ("nope",)


# ---------------------------------------------------------------------------
# _get_detection_file_paths_streaming
# ---------------------------------------------------------------------------
def _stream(svc, sess, cutoff):
    async def _go():
        return await svc._get_detection_file_paths_streaming(sess, cutoff)

    with _session(sess):
        return _attempt(_go())


def test_stream_paths_digest_and_no_images_polarity():
    """Digest kills the query mutants; delete_images=False with file_paths
    present must collect NOTHING on the image leg (kills the 'or' twin)."""
    svc = _svc(retention_days=RET, delete_images=False)
    sess = _Sess(rows=[_det(thumb="T1", file="F1"), _det(thumb="T2")])
    thumbs, images = _stream(svc, sess, DET_CUT)
    assert thumbs == ["T1", "T2"]
    assert images == []
    assert sess.calls == [("stream", DIG_DET_QUERY)]


def test_stream_paths_delete_images_true_collects_both():
    svc = _svc(retention_days=RET, delete_images=True)
    sess = _Sess(rows=[_det(thumb="T1", file="F1"), _det(thumb=None, file="F2"), _det()])
    thumbs, images = _stream(svc, sess, DET_CUT)
    assert thumbs == ["T1"]
    assert images == ["F1", "F2"]


# ---------------------------------------------------------------------------
# dry_run_cleanup
# ---------------------------------------------------------------------------
def test_dry_run_exact_digests_counts_stats_and_messages():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        real_t = tmp / "t.jpg"
        real_t.write_bytes(b"12345")  # 5 B
        real_t2 = tmp / "t2.jpg"
        real_t2.write_bytes(b"abc")  # 3 B -- the += 1 -> = 1 twin needs 2 hits
        dir_t = tmp / "dir.jpg"  # a DIRECTORY named like a media file
        dir_t.mkdir()
        img1 = tmp / "i1.jpg"
        img1.write_bytes(b"ab")  # 2 B
        img2 = tmp / "i2.jpg"
        img2.write_bytes(b"c")  # 1 B -> images 2, space 11
        rows = [
            _det(thumb=str(real_t), file=str(img1)),
            _det(thumb=str(dir_t), file=str(img2)),
            _det(thumb=str(real_t2), file=str(dir_t)),
        ]
        sess = _Sess(
            results=[_Res(scalar=7), _Res(scalar=3), _Res(scalar=11), _Res(scalar=9)],
            rows=rows,
        )
        svc = _svc(retention_days=RET, delete_images=True)
        with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
            stats = _attempt(svc.dry_run_cleanup())
        assert clk.tzs == [UTC, UTC], clk.tzs  # dry-run cutoff + _count_old_logs
        # shipped counts ONLY real files (dirs + missing skipped); the
        # and->or twins count the directory, the =1 twins pin to 1.
        assert stats.detections_deleted == 7
        assert stats.events_deleted == 3
        assert stats.gpu_stats_deleted == 11
        assert stats.logs_deleted == 9
        assert stats.thumbnails_deleted == 2
        assert stats.images_deleted == 2
        assert stats.space_reclaimed == 11
        assert sess.calls == [
            ("execute", DIG_DET_COUNT),
            ("stream", DIG_DET_QUERY),
            ("execute", DIG_EVT_COUNT),
            ("execute", DIG_GPU_COUNT),
            ("execute", DIG_LOG_COUNT),
        ]
        _assert_msgs(
            cap,
            [
                (INFO, "Starting cleanup dry run (retention: 30 days)"),
                (INFO, "Dry run: would delete records older than " + str(DET_CUT)),
                (INFO, "Dry run: would delete 7 detections"),
                (INFO, "Dry run: would delete 2 thumbnail files"),
                (INFO, "Dry run: would delete 2 image files"),
                (INFO, "Dry run: would delete 3 events"),
                (INFO, "Dry run: would delete 11 GPU stats"),
                (INFO, "Dry run: would delete 9 logs older than 7 days"),
                (INFO, "Cleanup dry run completed: " + str(stats)),
            ],
        )


def test_dry_run_failure_logs_error_with_exc_info():
    sess = _Sess(results=[_Res(scalar=0)], rows=[], raise_at={1})
    svc = _svc(retention_days=RET)
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        try:
            _attempt(svc.dry_run_cleanup())
            raise AssertionError("must re-raise")
        except RuntimeError as exc:
            assert exc.args == ("boom",)
    err = cap.records[-1]
    assert err.levelno == ERROR
    assert err.getMessage() == "Cleanup dry run failed: boom"
    assert err.exc_info[0] is RuntimeError and err.exc_info[1].args == ("boom",)


# ---------------------------------------------------------------------------
# _count_old_logs / cleanup_old_logs
# ---------------------------------------------------------------------------
def test_count_old_logs_zero_count_logs_nothing_exact_digest():
    sess = _Sess(results=[_Res(scalar=0)])
    svc = _svc()
    with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
        assert _attempt(svc._count_old_logs()) == 0
    assert clk.tzs == [UTC]
    assert sess.calls == [("execute", DIG_LOG_COUNT)]
    _assert_msgs(cap, [])  # the > -> >= twin logs on zero -- killed here


def test_count_old_logs_one_logs_exactly_once():
    sess = _Sess(results=[_Res(scalar=1)])
    svc = _svc()
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        assert _attempt(svc._count_old_logs()) == 1
    _assert_msgs(cap, [(INFO, "Dry run: would delete 1 logs older than 7 days")])
    # the > 1 twin drops this log -- killed by the assert above


def test_cleanup_old_logs_zero_no_log_commit_and_digest():
    sess = _Sess(results=[_Res(rowcount=0)])
    svc = _svc()
    with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
        assert _attempt(svc.cleanup_old_logs()) == 0
    assert clk.tzs == [UTC]
    assert sess.calls == [("execute", DIG_DEL_LOG)]
    assert sess.commits == 1
    _assert_msgs(cap, [])


def test_cleanup_old_logs_one_logs_exactly_once():
    sess = _Sess(results=[_Res(rowcount=1)])
    svc = _svc()
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        assert _attempt(svc.cleanup_old_logs()) == 1
    _assert_msgs(cap, [(INFO, "Cleaned up 1 logs older than 7 days")])


# ---------------------------------------------------------------------------
# _parse_cleanup_time boundaries + chained cause
# ---------------------------------------------------------------------------
def test_parse_cleanup_time_ranges_and_exact_cause():
    for hm in ["00:00", "23:59", "03:00"]:
        svc = _svc(cleanup_time=hm)
        assert svc._parse_cleanup_time() == tuple(int(x) for x in hm.split(":"))
    for bad in ["24:00", "25:00", "23:60", "23:61", "-1:00"]:
        svc = _svc(cleanup_time=bad)
        try:
            svc._parse_cleanup_time()
            raise AssertionError("must raise for " + bad)
        except ValueError as exc:
            assert str(exc) == (
                "Invalid cleanup_time format '" + bad + "'. Expected HH:MM (24-hour format)"
            ), str(exc)
            assert str(exc.__cause__) == "Invalid time range", str(exc.__cause__)
    svc = _svc(cleanup_time="12:")
    try:
        svc._parse_cleanup_time()
        raise AssertionError("must raise for malformed")
    except ValueError as exc:
        assert str(exc) == ("Invalid cleanup_time format '12:'. Expected HH:MM (24-hour format)")


def test_parse_cleanup_time_attribute_error_chain():
    svc = _svc()
    svc.cleanup_time = None
    try:
        svc._parse_cleanup_time()
        raise AssertionError("must raise")
    except ValueError as exc:
        assert isinstance(exc.__cause__, AttributeError)


# ---------------------------------------------------------------------------
# _calculate_next_cleanup / _wait_until_next_cleanup
# ---------------------------------------------------------------------------
def test_next_cleanup_exact_fields_with_nonzero_clock():
    svc = _svc(cleanup_time="02:30")
    with _clocked(PIN_A) as clk:
        got = svc._calculate_next_cleanup()
    assert got == datetime(2026, 9, 16, 2, 30, 0, 0, tzinfo=UTC), got
    assert clk.tzs == [UTC]


def test_next_cleanup_boundary_equal_now_rolls_forward():
    """<= -> < twin: cleanup_time EXACTLY equals the pinned instant --
    shipped treats an already-passed time and rolls to tomorrow."""
    svc = _svc(cleanup_time="12:00")
    with _clocked(PIN):
        got = svc._calculate_next_cleanup()
    assert got == datetime(2026, 9, 16, 12, 0, 0, 0, tzinfo=UTC), got


def test_wait_until_next_cleanup_sleeps_exact_seconds_logs_exact_message():
    svc = _svc(cleanup_time="13:00")
    with _clocked(PIN), _shim_asyncio(), _capture_logs() as cap:
        _attempt(svc._wait_until_next_cleanup())
    assert SLEEPS == [3600.0], SLEEPS
    _assert_msgs(
        cap,
        [(INFO, "Next cleanup scheduled for 2026-09-15 13:00:00+00:00 (3600s)")],
    )


# ---------------------------------------------------------------------------
# __init__ logs + attributes
# ---------------------------------------------------------------------------
def test_init_stores_batch_size_and_logs_exact_summary():
    with _capture_logs() as cap:
        svc = _svc(cleanup_time="03:00")
    assert svc.batch_size == 1000
    assert svc.retention_days == 44
    _assert_msgs(
        cap,
        [
            (
                INFO,
                "CleanupService initialized: retention=44 days, time=03:00, "
                "delete_images=False, batch_size=1000",
            )
        ],
    )


def test_orphan_init_logs_exact_storage_paths():
    with _capture_logs() as cap:
        _osvc(storage_paths=["/a", "/b"])
    _assert_msgs(
        cap,
        [(INFO, "OrphanedFileCleanup initialized with storage paths: ['/a', '/b']")],
    )


# ---------------------------------------------------------------------------
# start / stop / _cleanup_loop (cs.asyncio shimmed)
# ---------------------------------------------------------------------------
def test_start_creates_named_task_and_logs_exactly():
    svc = _svc()
    with _shim_asyncio(), _capture_logs() as cap:
        _attempt(svc.start())
        assert svc.running is True
        _attempt(svc.start())  # idempotent second call
    assert TASK_NAMES == ["cleanup-service"]  # None/MISSING/XX/UPPER killed
    assert svc._cleanup_task is not None
    _assert_msgs(
        cap,
        [
            (INFO, "Starting CleanupService"),
            (INFO, "CleanupService started successfully"),
            (WARNING, "CleanupService already running"),
        ],
    )


def test_stop_cancels_awaitable_clears_and_logs():
    svc = _svc()
    task = _Task()
    svc.running = True
    svc._cleanup_task = task
    with _capture_logs() as cap:
        _attempt(svc.stop())
    assert task.cancelled is True
    assert svc.running is False and svc._cleanup_task is None
    _assert_msgs(cap, [(INFO, "Stopping CleanupService"), (INFO, "CleanupService stopped")])


def test_stop_when_not_running_only_debugs():
    svc = _svc()
    with _capture_logs() as cap:
        _attempt(svc.stop())
    _assert_msgs(cap, [(DEBUG, "CleanupService not running, nothing to stop")])


class _LoopSvc(cs.CleanupService):
    """_wait/run spies: the loop's iteration sequence is deterministic."""

    def __init__(self, script) -> None:
        super().__init__(retention_days=1)
        self.script = list(script)
        self.runs = 0

    async def _wait_until_next_cleanup(self):
        step = self.script.pop(0)
        if step == "raise":
            raise RuntimeError("looperr")
        if step == "cancel":
            import asyncio

            raise asyncio.CancelledError
        if step == "stop":
            self.running = False

    async def run_cleanup(self):
        self.runs += 1
        return cs.CleanupStats()


def _lsvc(script):
    with _pinned():
        return _LoopSvc(script)


def _loop(svc):
    with _shim_asyncio(), _capture_logs() as cap:
        svc.running = True
        _attempt(svc._cleanup_loop())
    return cap


def test_cleanup_loop_happy_path_logs_bookends_and_runs_once():
    svc = _lsvc(["ok", "stop"])
    cap = _loop(svc)
    assert svc.runs == 1
    _assert_msgs(cap, [(INFO, "Cleanup loop started"), (INFO, "Cleanup loop stopped")])


def test_cleanup_loop_cancel_breaks_then_logs_stopped():
    """break -> return: the RETURN skips the stopped bookend."""
    svc = _lsvc(["cancel"])
    cap = _loop(svc)
    assert svc.runs == 0
    _assert_msgs(
        cap,
        [
            (INFO, "Cleanup loop started"),
            (INFO, "Cleanup loop cancelled"),
            (INFO, "Cleanup loop stopped"),
        ],
    )


def test_cleanup_loop_error_logs_then_sleeps_60_and_survives():
    svc = _lsvc(["raise", "stop"])
    cap = _loop(svc)
    assert SLEEPS == [60], SLEEPS  # the 61 twin killed by the exact value
    assert svc.runs == 0
    _assert_msgs(
        cap,
        [
            (INFO, "Cleanup loop started"),
            (ERROR, "Error in cleanup loop: looperr"),
            (INFO, "Cleanup loop stopped"),
        ],
    )
    errs = [r for r in cap.records if r.levelno == ERROR]
    assert len(errs) == 1
    assert errs[0].exc_info[0] is RuntimeError
    assert errs[0].exc_info[1].args == ("looperr",)


# ---------------------------------------------------------------------------
# OrphanedFileCleanup.run_cleanup + helpers
# ---------------------------------------------------------------------------
def test_orphan_run_cleanup_dry_default_exact_calls_and_messages():
    """Default arg (True->False would DELETE and set dry_run False), the
    full tracker call list, exact messages, and the orphaned-list contents
    (append(None) would put None in the list)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "ref.bin").write_bytes(b"r")
        (tmp / "orph1.bin").write_bytes(b"ab")
        (tmp / "orph2.bin").write_bytes(b"abcd")
        ref = str((tmp / "ref.bin").resolve())
        orph1 = str((tmp / "orph1.bin").resolve())
        orph2 = str((tmp / "orph2.bin").resolve())

        class _Dry(cs.OrphanedFileCleanup):
            async def _get_referenced_files(self):
                return {ref}

        tr = _Track("T1")
        svc = _Dry(job_tracker=tr, storage_paths=[td])
        with _capture_logs() as cap:
            stats = _attempt(svc.run_cleanup())
        assert stats.dry_run is True
        assert (tmp / "orph1.bin").exists() and (tmp / "orph2.bin").exists()
        assert stats.orphaned_count == 2
        assert stats.total_size == 6
        assert set(stats.orphaned_files) == {orph1, orph2}
        assert tr.calls == [
            ("create_job", ("orphaned_file_cleanup",), {}),
            ("start_job", ("T1", "Starting orphaned file cleanup"), {}),
            ("update_progress", ("T1", 10, "Querying database for referenced files"), {}),
            ("update_progress", ("T1", 30, "Scanning storage directories"), {}),
            ("update_progress", ("T1", 50, "Identifying orphaned files"), {}),
            ("complete_job", ("T1", stats.to_dict()), {}),
        ]
        _assert_msgs(
            cap,
            [
                (INFO, "Querying database for referenced files..."),
                (INFO, "Found 1 referenced files in database"),
                (INFO, "Scanning storage directories: ['" + td + "']"),
                (INFO, "Found 3 files on disk"),
                (INFO, "Found 2 orphaned files (6 B)"),
                (INFO, "Orphaned file cleanup completed: " + str(stats)),
            ],
        )


def test_orphan_run_cleanup_wet_deletes_logs_and_progress70():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "orph1.bin").write_bytes(b"ab")
        (tmp / "orph2.bin").write_bytes(b"abcd")

        class _Wet(cs.OrphanedFileCleanup):
            async def _get_referenced_files(self):
                return set()

        tr = _Track("T1")
        svc = _Wet(job_tracker=tr, storage_paths=[td])
        with _capture_logs() as cap:
            stats = _attempt(svc.run_cleanup(dry_run=False))
        assert not (tmp / "orph1.bin").exists()
        assert not (tmp / "orph2.bin").exists()
        assert stats.dry_run is False
        assert ("update_progress", ("T1", 70, "Deleting orphaned files"), {}) in tr.calls
        assert "Deleted 2 of 2 orphaned files" in [r.getMessage() for r in cap.records]
        assert tr.calls[-1] == ("complete_job", ("T1", stats.to_dict()), {})


def test_orphan_run_cleanup_failure_fails_job_with_exact_error():
    with tempfile.TemporaryDirectory() as td:

        class _Fail(cs.OrphanedFileCleanup):
            async def _get_referenced_files(self):
                raise RuntimeError("dbdown")

        tr = _Track("T1")
        svc = _Fail(job_tracker=tr, storage_paths=[td])
        with _capture_logs() as cap:
            try:
                _attempt(svc.run_cleanup())
                raise AssertionError("must re-raise")
            except RuntimeError as exc:
                assert exc.args == ("dbdown",)
        assert tr.calls[-1] == ("fail_job", ("T1", "dbdown"), {})
        rec = cap.records[-1]
        assert rec.getMessage() == "Orphaned file cleanup failed: dbdown"
        assert rec.exc_info[0] is RuntimeError and rec.exc_info[1].args == ("dbdown",)


def test_orphan_falsy_job_id_never_completes_or_fails():
    """create_job returns '' (falsy): shipped makes NO complete/fail call in
    either polarity; the 'or' guard twins call with ''."""

    class _Empty(cs.OrphanedFileCleanup):
        async def _get_referenced_files(self):
            return set()

    tr = _Track("")
    svc = _Empty(job_tracker=tr, storage_paths=[NOWHERE])
    _attempt(svc.run_cleanup())
    assert [c for c in tr.calls if c[0] in ("complete_job", "fail_job")] == []

    class _EmptyFail(cs.OrphanedFileCleanup):
        async def _get_referenced_files(self):
            raise RuntimeError("nope2")

    tr2 = _Track("")
    svc2 = _EmptyFail(job_tracker=tr2, storage_paths=[NOWHERE])
    try:
        _attempt(svc2.run_cleanup())
        raise AssertionError("must re-raise")
    except RuntimeError:
        pass
    assert [c for c in tr2.calls if c[0] == "fail_job"] == []


def test_orphan_get_referenced_files_digests_and_absolutization():
    # str(Path(rel).resolve()) in the TEST world sees the SAME process cwd the
    # module sees, so the absolute paths are predictable without chdir.
    rows = [("rel/a.img", "rel/b.jpg"), (None, None)]
    evt_rows = [("rel/c.mp4",), (None,)]
    sess = _Sess(results=[_Rows(rows), _Rows(evt_rows)])
    svc = _osvc(storage_paths=[NOWHERE])
    with _session(sess):
        got = _attempt(svc._get_referenced_files())
    assert sess.calls == [("execute", DIG_REF_DET), ("execute", DIG_REF_EVT)]
    assert got == {
        str(Path("rel/a.img").resolve()),
        str(Path("rel/b.jpg").resolve()),
        str(Path("rel/c.mp4").resolve()),
    }


class _NoStat(Path):
    def stat(self, follow_symlinks=True):
        if self.name == "nostat.bin":
            raise OSError("statdown")
        return super().stat(follow_symlinks=follow_symlinks)


def test_scan_storage_directories_skips_broken_and_continues():
    """Order: missing, a FILE (not a dir), d1 (one stat failure + one good),
    d2. The continue -> break twins stop at the first skip; shipped scans
    BOTH valid dirs. (Path.is_dir/is_file are os-path backed, so _NoStat can
    only break the explicit stat() call, which is what is being exercised.)"""
    with tempfile.TemporaryDirectory() as outer:
        outerp = Path(outer)
        missing = outerp / "missing"
        notadir = outerp / "file.txt"
        notadir.write_text("x")
        d1 = outerp / "d1"
        d1.mkdir()
        nostat = d1 / "nostat.bin"
        nostat.write_text("ns")
        (d1 / "good.bin").write_bytes(b"12")
        d2 = outerp / "d2"
        d2.mkdir()
        (d2 / "e.bin").write_bytes(b"12345")
        svc = _osvc(storage_paths=[str(missing), str(notadir), str(d1), str(d2)])
        with _attr(cs, "Path", _NoStat), _capture_logs() as cap:
            found = svc._scan_storage_directories()
        sizes = {Path(p).name: s for p, s in found}
        assert sorted(sizes) == ["e.bin", "good.bin"], sizes
        assert sizes["good.bin"] == 2 and sizes["e.bin"] == 5
        msgs = [r.getMessage() for r in cap.records]
        assert "Storage path does not exist: " + str(missing) in msgs
        assert "Storage path is not a directory: " + str(notadir) in msgs
        assert "Could not stat file " + str(nostat) + ": statdown" in msgs


def test_orphan_delete_orphaned_files_partial_failure_warns():
    with tempfile.TemporaryDirectory() as td:
        ok = Path(td) / "ok.bin"
        ok.write_text("x")
        bad = Path(td) / "noclean.bin"
        bad.write_text("x")
        svc = _osvc(storage_paths=[NOWHERE])
        with _attr(cs, "Path", _NoUnlink), _capture_logs() as cap:
            n = svc._delete_orphaned_files([(str(ok), 1), (str(bad), 1)])
        assert n == 1
        assert not ok.exists() and bad.exists()
        _assert_msgs(cap, [(WARNING, "Failed to delete orphaned file " + str(bad) + ": nope")])


# ---------------------------------------------------------------------------
# digest-channel self-check (not a mutant claim): the channel must separate
# the shipped streaming query from its <= twin, where(None) twin and None.
# ---------------------------------------------------------------------------
def test_digest_helper_selfcheck_distinguishes_families():
    le = _dig(select(Detection).where(Detection.detected_at <= DET_CUT))
    wnone = _dig(select(Detection).where(None))
    assert le != DIG_DET_QUERY
    assert wnone != DIG_DET_QUERY
    assert _dig(None) != DIG_DET_QUERY
    naive = _dig_model(Detection.detected_at, Detection, DET_CUT.replace(tzinfo=None))
    assert naive != DIG_DET_QUERY
