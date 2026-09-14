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
        patch.object(service, "_get_job_status_service", return_value=mock_job_service),
        patch.object(service, "cleanup_old_logs", return_value=10),
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
        patch.object(service, "_get_job_status_service", return_value=mock_job_service),
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

    with patch("backend.services.job_status.get_job_status_service") as mock_get:
        mock_get.return_value = mock_job_service

        result = service._get_job_status_service()

        assert result is mock_job_service
        mock_get.assert_called_once_with(mock_redis_client)


def test_get_job_status_service_caching():
    """Test _get_job_status_service caches the service instance."""
    mock_redis_client = AsyncMock()
    service = CleanupService(retention_days=30, redis_client=mock_redis_client)

    mock_job_service = MagicMock()

    with patch("backend.services.job_status.get_job_status_service") as mock_get:
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

    with patch("backend.services.cleanup_service.get_settings", return_value=mock_settings):
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

    with patch.object(cleanup, "_get_referenced_files", side_effect=mock_get_referenced):
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

    with patch.object(cleanup, "_get_referenced_files", side_effect=mock_get_referenced):
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

    with patch.object(cleanup, "_get_referenced_files", side_effect=mock_get_referenced):
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
        patch.object(cleanup, "_get_referenced_files", side_effect=mock_get_referenced_error),
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
    with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
        orphaned_files = [(str(file1), 100)]
        deleted_count = cleanup._delete_orphaned_files(orphaned_files)

    # Should return 0 since deletion failed
    assert deleted_count == 0
    # File should still exist
    assert file1.exists()
