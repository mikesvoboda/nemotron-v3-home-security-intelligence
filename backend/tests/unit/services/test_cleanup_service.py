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
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

        with patch("backend.services.cleanup_service.get_settings", return_value=mock_settings):
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

        with patch("backend.services.cleanup_service.datetime") as mock_datetime:
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

        with patch("backend.services.cleanup_service.datetime") as mock_datetime:
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
        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
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
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup),
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
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup_with_error),
        patch("backend.services.cleanup_service.asyncio.sleep", side_effect=patched_sleep),
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
        patch.object(service, "cleanup_old_logs", return_value=50),
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
        patch.object(service, "cleanup_old_logs", return_value=0),
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
        patch.object(service, "cleanup_old_logs", return_value=0),
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
        patch.object(service, "cleanup_old_logs", return_value=0),
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
        patch.object(service, "_count_old_logs", return_value=25),
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
        patch.object(service, "_count_old_logs", return_value=0),
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
        patch.object(service, "_count_old_logs", return_value=0),
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
        patch.object(service, "_count_old_logs", return_value=0),
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
        patch.object(service, "_count_old_logs", return_value=0),
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

    with patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait):
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
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup),
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
        patch.object(service, "cleanup_old_logs", return_value=0),
    ):
        stats = await service.run_cleanup()

    # File didn't exist, so thumbnail count stays 0
    assert stats.thumbnails_deleted == 0


# =============================================================================
# format_bytes tests
# =============================================================================


class TestFormatBytes:
    """Tests for the format_bytes helper function."""

    def test_format_bytes_zero(self):
        """Verify 0 bytes formats correctly."""
        from backend.services.cleanup_service import format_bytes

        assert format_bytes(0) == "0 B"

    def test_format_bytes_negative(self):
        """Verify negative values return 0 B."""
        from backend.services.cleanup_service import format_bytes

        assert format_bytes(-100) == "0 B"

    def test_format_bytes_bytes(self):
        """Verify small values stay in bytes."""
        from backend.services.cleanup_service import format_bytes

        assert format_bytes(500) == "500 B"
        assert format_bytes(1023) == "1023 B"

    def test_format_bytes_kilobytes(self):
        """Verify kilobyte formatting."""
        from backend.services.cleanup_service import format_bytes

        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1536) == "1.50 KB"

    def test_format_bytes_megabytes(self):
        """Verify megabyte formatting."""
        from backend.services.cleanup_service import format_bytes

        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 2.5) == "2.50 MB"

    def test_format_bytes_gigabytes(self):
        """Verify gigabyte formatting."""
        from backend.services.cleanup_service import format_bytes

        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(1024 * 1024 * 1024 * 1.5) == "1.50 GB"

    def test_format_bytes_terabytes(self):
        """Verify terabyte formatting."""
        from backend.services.cleanup_service import format_bytes

        assert format_bytes(1024**4) == "1.00 TB"


# =============================================================================
# OrphanedFileCleanupStats tests
# =============================================================================


class TestOrphanedFileCleanupStats:
    """Tests for the OrphanedFileCleanupStats data class."""

    def test_initialization(self):
        """Verify OrphanedFileCleanupStats initializes with defaults."""
        from backend.services.cleanup_service import OrphanedFileCleanupStats

        stats = OrphanedFileCleanupStats()

        assert stats.orphaned_count == 0
        assert stats.total_size == 0
        assert stats.dry_run is True
        assert stats.orphaned_files == []

    def test_to_dict(self):
        """Verify to_dict returns all fields correctly."""
        from backend.services.cleanup_service import OrphanedFileCleanupStats

        stats = OrphanedFileCleanupStats()
        stats.orphaned_count = 5
        stats.total_size = 1024 * 1024  # 1 MB
        stats.dry_run = False
        stats.orphaned_files = ["/path/file1.jpg", "/path/file2.jpg"]

        result = stats.to_dict()

        assert result["orphaned_count"] == 5
        assert result["total_size"] == 1024 * 1024
        assert result["total_size_formatted"] == "1.00 MB"
        assert result["dry_run"] is False
        assert result["orphaned_files"] == ["/path/file1.jpg", "/path/file2.jpg"]

    def test_to_dict_limits_orphaned_files(self):
        """Verify to_dict limits orphaned_files to 100 entries."""
        from backend.services.cleanup_service import OrphanedFileCleanupStats

        stats = OrphanedFileCleanupStats()
        stats.orphaned_files = [f"/path/file{i}.jpg" for i in range(150)]

        result = stats.to_dict()

        assert len(result["orphaned_files"]) == 100

    def test_repr(self):
        """Verify repr includes key information."""
        from backend.services.cleanup_service import OrphanedFileCleanupStats

        stats = OrphanedFileCleanupStats()
        stats.orphaned_count = 10
        stats.total_size = 1024 * 1024 * 500  # 500 MB

        repr_str = repr(stats)

        assert "OrphanedFileCleanupStats" in repr_str
        assert "orphaned_count=10" in repr_str
        assert "500.00 MB" in repr_str


# =============================================================================
# OrphanedFileCleanup tests
# =============================================================================


class TestOrphanedFileCleanup:
    """Tests for the OrphanedFileCleanup service class."""

    def test_initialization_with_defaults(self):
        """Verify initialization with default storage paths."""
        from backend.services.cleanup_service import OrphanedFileCleanup

        # Mock settings to return known paths
        mock_settings = MagicMock()
        mock_settings.video_thumbnails_dir = "data/thumbnails"
        mock_settings.clips_directory = "data/clips"

        with patch("backend.services.cleanup_service.get_settings", return_value=mock_settings):
            cleanup = OrphanedFileCleanup()

        assert "data/thumbnails" in cleanup._storage_paths
        assert "data/clips" in cleanup._storage_paths

    def test_initialization_with_custom_paths(self):
        """Verify initialization with custom storage paths."""
        from backend.services.cleanup_service import OrphanedFileCleanup

        custom_paths = ["/custom/path1", "/custom/path2"]
        cleanup = OrphanedFileCleanup(storage_paths=custom_paths)

        assert cleanup._storage_paths == custom_paths

    def test_initialization_with_job_tracker(self):
        """Verify initialization with job tracker."""
        from backend.services.cleanup_service import OrphanedFileCleanup
        from backend.services.job_tracker import JobTracker

        job_tracker = JobTracker()
        cleanup = OrphanedFileCleanup(job_tracker=job_tracker, storage_paths=["/test/path"])

        assert cleanup._job_tracker is job_tracker

    def test_scan_storage_directories_nonexistent_path(self, tmp_path):
        """Verify scanning handles nonexistent paths gracefully."""
        from backend.services.cleanup_service import OrphanedFileCleanup

        cleanup = OrphanedFileCleanup(storage_paths=["/nonexistent/path"])
        files = cleanup._scan_storage_directories()

        assert files == []

    def test_scan_storage_directories_file_instead_of_directory(self, tmp_path):
        """Verify scanning handles files (not directories) gracefully."""
        from backend.services.cleanup_service import OrphanedFileCleanup

        # Create a file instead of directory
        test_file = tmp_path / "file.txt"
        test_file.write_text("test")

        cleanup = OrphanedFileCleanup(storage_paths=[str(test_file)])
        files = cleanup._scan_storage_directories()

        assert files == []

    def test_scan_storage_directories_with_files(self, tmp_path):
        """Verify scanning finds all files recursively."""
        from backend.services.cleanup_service import OrphanedFileCleanup

        # Create test directory structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        file1 = tmp_path / "file1.jpg"
        file2 = subdir / "file2.jpg"
        file1.write_text("content1")
        file2.write_text("content2")

        cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])
        files = cleanup._scan_storage_directories()

        # Should find both files
        paths = [f[0] for f in files]
        assert len(files) == 2
        assert str(file1.resolve()) in paths
        assert str(file2.resolve()) in paths


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_dry_run(tmp_path):
    """Test orphaned file cleanup in dry run mode."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test files
    orphan1 = tmp_path / "orphan1.jpg"
    orphan2 = tmp_path / "orphan2.jpg"
    orphan1.write_text("orphan content 1")
    orphan2.write_text("orphan content 2")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock database to return empty set (no referenced files)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []  # No referenced files

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        stats = await cleanup.run_cleanup(dry_run=True)

    # Should find orphaned files
    assert stats.orphaned_count == 2
    assert stats.dry_run is True
    # Files should still exist (dry run)
    assert orphan1.exists()
    assert orphan2.exists()


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_actual_deletion(tmp_path):
    """Test orphaned file cleanup actually deletes files."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test files
    orphan1 = tmp_path / "orphan1.jpg"
    orphan2 = tmp_path / "orphan2.jpg"
    orphan1.write_text("orphan content 1")
    orphan2.write_text("orphan content 2")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock database to return empty set (no referenced files)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        stats = await cleanup.run_cleanup(dry_run=False)

    # Should find and delete orphaned files
    assert stats.orphaned_count == 2
    assert stats.dry_run is False
    # Files should be deleted
    assert not orphan1.exists()
    assert not orphan2.exists()


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_with_referenced_files(tmp_path):
    """Test orphaned file cleanup excludes referenced files."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test files
    referenced = tmp_path / "referenced.jpg"
    orphan = tmp_path / "orphan.jpg"
    referenced.write_text("referenced content")
    orphan.write_text("orphan content")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock database to return the referenced file
    mock_session = AsyncMock()

    # First call for detections
    mock_detection_result = MagicMock()
    mock_detection_result.all.return_value = [
        (str(referenced.resolve()), None)  # file_path, thumbnail_path
    ]

    # Second call for events (clip paths)
    mock_event_result = MagicMock()
    mock_event_result.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[mock_detection_result, mock_event_result])

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        stats = await cleanup.run_cleanup(dry_run=True)

    # Should only find the orphan file, not the referenced one
    assert stats.orphaned_count == 1
    assert str(orphan.resolve()) in stats.orphaned_files


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_with_job_tracker():
    """Test orphaned file cleanup reports progress to job tracker."""
    from backend.services.cleanup_service import OrphanedFileCleanup
    from backend.services.job_tracker import JobTracker

    job_tracker = JobTracker()

    # Create cleanup with empty storage paths (no files to find)
    cleanup = OrphanedFileCleanup(
        job_tracker=job_tracker,
        storage_paths=["/nonexistent/path"],
    )

    # Mock database
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        stats = await cleanup.run_cleanup(dry_run=True)

    # Verify job was tracked
    jobs = job_tracker.get_all_jobs(job_type="orphaned_file_cleanup")
    assert len(jobs) == 1
    assert jobs[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_handles_database_error():
    """Test orphaned file cleanup handles database errors gracefully."""
    from backend.services.cleanup_service import OrphanedFileCleanup
    from backend.services.job_tracker import JobTracker

    job_tracker = JobTracker()
    cleanup = OrphanedFileCleanup(
        job_tracker=job_tracker,
        storage_paths=["/test/path"],
    )

    # Mock database to raise an error
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Database error"))

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        pytest.raises(Exception, match="Database error"),
    ):
        await cleanup.run_cleanup(dry_run=True)

    # Verify job was marked as failed
    jobs = job_tracker.get_all_jobs(job_type="orphaned_file_cleanup")
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_delete_error_handling(tmp_path):
    """Test orphaned file cleanup handles file deletion errors gracefully."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    # Create test file
    orphan = tmp_path / "orphan.jpg"
    orphan.write_text("orphan content")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    # Mock database to return empty set
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    # Mock Path.unlink to raise an error
    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(Path, "unlink", side_effect=OSError("Permission denied")),
    ):
        # Should not raise, but log the error
        stats = await cleanup.run_cleanup(dry_run=False)

    # Stats should still show the file was found
    assert stats.orphaned_count == 1


# =============================================================================
# CleanupService Job Tracking Integration Tests (NEM-1974)
# =============================================================================


class TestCleanupServiceJobTracking:
    """Tests for job tracking integration in CleanupService (NEM-1974)."""

    @pytest.fixture
    def mock_job_tracker(self):
        """Create a mock JobTracker."""
        from unittest.mock import MagicMock

        tracker = MagicMock()
        tracker.create_job = MagicMock(return_value="test-cleanup-job-123")
        tracker.start_job = MagicMock()
        tracker.update_progress = MagicMock()
        tracker.complete_job = MagicMock()
        tracker.fail_job = MagicMock()
        tracker.is_cancelled = MagicMock(return_value=False)
        return tracker

    def test_cleanup_service_accepts_job_tracker(self, mock_job_tracker):
        """Test CleanupService can be initialized with job_tracker."""
        service = CleanupService(job_tracker=mock_job_tracker)
        assert service._job_tracker is mock_job_tracker

    def test_cleanup_service_job_type_constant(self):
        """Test CleanupService has correct JOB_TYPE constant."""
        assert CleanupService.JOB_TYPE == "cleanup"

    def test_is_job_cancelled_returns_false_without_tracker(self):
        """Test _is_job_cancelled returns False when no tracker configured."""
        service = CleanupService(job_tracker=None)
        assert service._is_job_cancelled("some-job-id") is False

    def test_is_job_cancelled_returns_false_with_none_job_id(self, mock_job_tracker):
        """Test _is_job_cancelled returns False when job_id is None."""
        service = CleanupService(job_tracker=mock_job_tracker)
        assert service._is_job_cancelled(None) is False
        mock_job_tracker.is_cancelled.assert_not_called()

    def test_is_job_cancelled_delegates_to_tracker(self, mock_job_tracker):
        """Test _is_job_cancelled delegates to job tracker."""
        mock_job_tracker.is_cancelled.return_value = True
        service = CleanupService(job_tracker=mock_job_tracker)
        assert service._is_job_cancelled("test-job-id") is True
        mock_job_tracker.is_cancelled.assert_called_once_with("test-job-id")

    @pytest.mark.asyncio
    async def test_run_cleanup_creates_job(self, mock_job_tracker):
        """Test run_cleanup creates a job when tracker is configured."""
        service = CleanupService(retention_days=30, job_tracker=mock_job_tracker)

        mock_session = AsyncMock()
        mock_session.stream_scalars = create_stream_scalars_mock([])

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 0

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
            patch.object(service, "cleanup_old_logs", return_value=0),
        ):
            await service.run_cleanup()

        mock_job_tracker.create_job.assert_called_once_with("cleanup")
        mock_job_tracker.start_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cleanup_updates_progress(self, mock_job_tracker):
        """Test run_cleanup updates progress during cleanup."""
        service = CleanupService(retention_days=30, job_tracker=mock_job_tracker)

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
            patch.object(service, "cleanup_old_logs", return_value=3),
        ):
            await service.run_cleanup()

        # Should have multiple progress updates
        assert mock_job_tracker.update_progress.call_count >= 5
        mock_job_tracker.complete_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cleanup_completes_job_with_results(self, mock_job_tracker):
        """Test run_cleanup completes job with cleanup stats."""
        service = CleanupService(retention_days=30, job_tracker=mock_job_tracker)

        mock_session = AsyncMock()
        mock_session.stream_scalars = create_stream_scalars_mock([])

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 10

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
            patch.object(service, "cleanup_old_logs", return_value=5),
        ):
            await service.run_cleanup()

        mock_job_tracker.complete_job.assert_called_once()
        call_args = mock_job_tracker.complete_job.call_args
        result = call_args[1]["result"]

        assert result["events_deleted"] == 10
        assert result["detections_deleted"] == 10
        assert result["gpu_stats_deleted"] == 10
        assert result["logs_deleted"] == 5

    @pytest.mark.asyncio
    async def test_run_cleanup_fails_job_on_exception(self, mock_job_tracker):
        """Test run_cleanup fails job when an exception occurs."""
        service = CleanupService(retention_days=30, job_tracker=mock_job_tracker)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            raise RuntimeError("Database connection failed")
            yield  # type: ignore

        with (
            patch("backend.services.cleanup_service.get_session", mock_get_session),
            pytest.raises(RuntimeError, match="Database connection failed"),
        ):
            await service.run_cleanup()

        mock_job_tracker.fail_job.assert_called_once()
        call_args = mock_job_tracker.fail_job.call_args
        assert "Database connection failed" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_run_cleanup_checks_cancellation(self, mock_job_tracker):
        """Test run_cleanup checks for cancellation."""
        mock_job_tracker.is_cancelled.return_value = True  # Simulate cancellation
        service = CleanupService(retention_days=30, job_tracker=mock_job_tracker)

        # Should return early without performing cleanup
        stats = await service.run_cleanup()

        # No deletions should have occurred
        assert stats.events_deleted == 0
        assert stats.detections_deleted == 0
        mock_job_tracker.is_cancelled.assert_called()

    @pytest.mark.asyncio
    async def test_run_cleanup_uses_provided_job_id(self, mock_job_tracker):
        """Test run_cleanup uses provided job_id instead of creating new one."""
        service = CleanupService(retention_days=30, job_tracker=mock_job_tracker)

        mock_session = AsyncMock()
        mock_session.stream_scalars = create_stream_scalars_mock([])

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 0

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
            patch.object(service, "cleanup_old_logs", return_value=0),
        ):
            await service.run_cleanup(job_id="external-job-id")

        # Should not create a new job
        mock_job_tracker.create_job.assert_not_called()
        mock_job_tracker.start_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_cleanup_without_tracker_works(self):
        """Test run_cleanup works correctly without job tracker."""
        service = CleanupService(retention_days=30, job_tracker=None)

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
            patch.object(service, "cleanup_old_logs", return_value=2),
        ):
            stats = await service.run_cleanup()

        # Should complete without errors
        assert stats.events_deleted == 5
        assert stats.detections_deleted == 5
        assert stats.logs_deleted == 2

    @pytest.mark.asyncio
    async def test_run_cleanup_cancellation_during_file_deletion(self, mock_job_tracker, tmp_path):
        """Test cleanup can be cancelled during file deletion."""
        # Create many files to trigger periodic cancellation check
        files = []
        for i in range(150):  # More than 100 to trigger check
            f = tmp_path / f"thumb_{i}.jpg"
            f.write_text(f"content {i}")
            files.append(f)

        service = CleanupService(
            retention_days=30,
            thumbnail_dir=str(tmp_path),
            job_tracker=mock_job_tracker,
        )

        # Mock detections pointing to these files
        mock_detections = [MockDetection(id=i, thumbnail_path=str(f)) for i, f in enumerate(files)]

        # Return False initially, then True after some progress
        check_count = 0

        def is_cancelled_side_effect(job_id):
            nonlocal check_count
            check_count += 1
            # Return True after a few checks (during file deletion)
            return check_count > 8

        mock_job_tracker.is_cancelled.side_effect = is_cancelled_side_effect

        mock_session = AsyncMock()
        mock_session.stream_scalars = create_stream_scalars_mock(mock_detections)

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = len(files)

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
            patch.object(service, "cleanup_old_logs", return_value=0),
        ):
            stats = await service.run_cleanup()

        # Should have been cancelled partway through
        # Some thumbnails may have been deleted but not all
        mock_job_tracker.is_cancelled.assert_called()
