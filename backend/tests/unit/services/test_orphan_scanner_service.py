"""Unit tests for the OrphanedFileScanner service.

This module contains comprehensive unit tests for the OrphanedFileScanner,
which identifies files on disk that have no corresponding database records.

Related Issues:
    - NEM-2387: Implement orphaned file cleanup background job

Test Organization:
    - OrphanedFile dataclass tests
    - ScanResult dataclass tests
    - Scanner initialization tests
    - File listing tests
    - File age calculation tests
    - Orphan detection tests
    - Full directory scan tests
    - Edge case tests
"""

import contextlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# Fixtures


@pytest.fixture(autouse=True)
def mock_settings_for_scanner_tests():
    """Set up minimal environment for tests.

    This fixture sets DATABASE_URL so get_settings() doesn't fail when
    OrphanedFileScanner is instantiated.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")

    # Only set DATABASE_URL if not already set
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
def scanner(tmp_path):
    """Create a scanner instance with a temporary base path."""
    from backend.services.orphan_scanner_service import OrphanedFileScanner

    return OrphanedFileScanner(base_path=tmp_path)


# =============================================================================
# OrphanedFile Dataclass Tests
# =============================================================================


class TestOrphanedFile:
    """Tests for the OrphanedFile dataclass."""

    def test_creation(self, tmp_path):
        """Test creating an OrphanedFile instance."""
        from backend.services.orphan_scanner_service import OrphanedFile

        test_file = tmp_path / "test.jpg"
        test_file.write_text("test")

        orphan = OrphanedFile(
            path=test_file,
            size_bytes=4,
            mtime=datetime.now(),
            age=timedelta(hours=24),
        )

        assert orphan.path == test_file
        assert orphan.size_bytes == 4
        assert isinstance(orphan.mtime, datetime)
        assert orphan.age == timedelta(hours=24)

    def test_to_dict(self, tmp_path):
        """Test converting OrphanedFile to dictionary."""
        from backend.services.orphan_scanner_service import OrphanedFile

        test_file = tmp_path / "test.jpg"
        test_file.write_text("test")
        now = datetime.now()

        orphan = OrphanedFile(
            path=test_file,
            size_bytes=4,
            mtime=now,
            age=timedelta(hours=24),
        )

        result = orphan.to_dict()

        assert result["path"] == str(test_file)
        assert result["size_bytes"] == 4
        assert result["mtime"] == now.isoformat()
        assert result["age_hours"] == 24.0


# =============================================================================
# ScanResult Dataclass Tests
# =============================================================================


class TestScanResult:
    """Tests for the ScanResult dataclass."""

    def test_initialization_with_defaults(self):
        """Test ScanResult initializes with zero values."""
        from backend.services.orphan_scanner_service import ScanResult

        result = ScanResult()

        assert result.scanned_files == 0
        assert result.orphaned_files == []
        assert result.total_orphaned_bytes == 0
        assert result.scan_errors == []
        assert result.scan_duration_seconds == 0.0

    def test_to_dict(self, tmp_path):
        """Test converting ScanResult to dictionary."""
        from backend.services.orphan_scanner_service import OrphanedFile, ScanResult

        test_file = tmp_path / "test.jpg"
        test_file.write_text("test")

        orphan = OrphanedFile(
            path=test_file,
            size_bytes=4,
            mtime=datetime.now(),
            age=timedelta(hours=24),
        )

        result = ScanResult(
            scanned_files=10,
            orphaned_files=[orphan],
            total_orphaned_bytes=4,
            scan_errors=["error 1"],
            scan_duration_seconds=1.5,
        )

        result_dict = result.to_dict()

        assert result_dict["scanned_files"] == 10
        assert result_dict["orphaned_count"] == 1
        assert result_dict["total_orphaned_bytes"] == 4
        assert result_dict["scan_errors"] == ["error 1"]
        assert result_dict["scan_duration_seconds"] == 1.5
        assert len(result_dict["orphaned_files"]) == 1


# =============================================================================
# Scanner Initialization Tests
# =============================================================================


class TestScannerInitialization:
    """Tests for OrphanedFileScanner initialization."""

    def test_default_initialization(self):
        """Test scanner initializes with settings defaults."""
        from backend.services.orphan_scanner_service import (
            SCANNABLE_EXTENSIONS,
            OrphanedFileScanner,
        )

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = "/export/foscam"

        with patch(
            "backend.services.orphan_scanner_service.get_settings",
            return_value=mock_settings,
        ):
            scanner = OrphanedFileScanner()

        assert scanner.base_path == Path("/export/foscam")
        assert scanner.extensions == SCANNABLE_EXTENSIONS

    def test_custom_initialization(self, tmp_path):
        """Test scanner with custom configuration."""
        from backend.services.orphan_scanner_service import OrphanedFileScanner

        custom_extensions = {".jpg", ".png"}
        scanner = OrphanedFileScanner(
            base_path=tmp_path,
            extensions=custom_extensions,
        )

        assert scanner.base_path == tmp_path
        assert scanner.extensions == custom_extensions


# =============================================================================
# File Listing Tests
# =============================================================================


class TestFileListing:
    """Tests for _list_files method."""

    def test_list_files_finds_images(self, tmp_path, scanner):
        """Test listing finds image files."""
        # Create test files
        (tmp_path / "image1.jpg").write_text("image 1")
        (tmp_path / "image2.png").write_text("image 2")
        (tmp_path / "other.txt").write_text("not an image")

        files = scanner._list_files(tmp_path)

        assert len(files) == 2
        extensions = {f.suffix for f in files}
        assert ".jpg" in extensions
        assert ".png" in extensions
        assert ".txt" not in extensions

    def test_list_files_finds_videos(self, tmp_path, scanner):
        """Test listing finds video files."""
        (tmp_path / "video1.mp4").write_text("video 1")
        (tmp_path / "video2.webm").write_text("video 2")

        files = scanner._list_files(tmp_path)

        assert len(files) == 2
        extensions = {f.suffix for f in files}
        assert ".mp4" in extensions
        assert ".webm" in extensions

    def test_list_files_recursive(self, tmp_path, scanner):
        """Test listing finds files in subdirectories."""
        # Create nested structure
        subdir = tmp_path / "camera1"
        subdir.mkdir()
        (tmp_path / "root.jpg").write_text("root")
        (subdir / "nested.jpg").write_text("nested")

        files = scanner._list_files(tmp_path)

        assert len(files) == 2

    def test_list_files_nonexistent_directory(self, scanner):
        """Test listing handles nonexistent directory."""
        files = scanner._list_files(Path("/nonexistent/path"))
        assert files == []

    def test_list_files_permission_error(self, tmp_path, scanner):
        """Test listing handles permission errors gracefully."""
        with patch("pathlib.Path.rglob", side_effect=PermissionError("Access denied")):
            files = scanner._list_files(tmp_path)
        assert files == []


# =============================================================================
# File Age Tests
# =============================================================================


class TestFileAge:
    """Tests for get_file_age method."""

    def test_get_file_age_recent_file(self, tmp_path, scanner):
        """Test age of recently created file."""
        test_file = tmp_path / "recent.jpg"
        test_file.write_text("recent")

        age = scanner.get_file_age(test_file)

        # Should be very recent (< 1 second)
        assert age.total_seconds() < 1

    def test_get_file_age_old_file(self, tmp_path, scanner):
        """Test age of file with modified mtime."""
        test_file = tmp_path / "old.jpg"
        test_file.write_text("old")

        # Set mtime to 48 hours ago
        old_time = datetime.now().timestamp() - (48 * 3600)
        os.utime(test_file, (old_time, old_time))

        age = scanner.get_file_age(test_file)

        # Should be approximately 48 hours
        assert age.total_seconds() >= 47 * 3600  # Allow some margin

    def test_get_file_age_nonexistent_file(self, scanner):
        """Test age raises for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            scanner.get_file_age(Path("/nonexistent/file.jpg"))


# =============================================================================
# File Info Tests
# =============================================================================


class TestGetFileInfo:
    """Tests for _get_file_info method."""

    def test_get_file_info_success(self, tmp_path, scanner):
        """Test getting file info successfully."""
        test_file = tmp_path / "test.jpg"
        test_file.write_text("test data")

        result = scanner._get_file_info(test_file)

        assert result is not None
        size, mtime, age = result
        assert size == 9  # "test data" is 9 bytes
        assert isinstance(mtime, datetime)
        assert isinstance(age, timedelta)

    def test_get_file_info_nonexistent(self, scanner):
        """Test getting info for nonexistent file returns None."""
        result = scanner._get_file_info(Path("/nonexistent/file.jpg"))
        assert result is None


# =============================================================================
# Referenced Paths Tests
# =============================================================================


class TestGetReferencedPaths:
    """Tests for _get_referenced_paths method."""

    @pytest.mark.asyncio
    async def test_get_referenced_paths_from_detections(self, scanner):
        """Test getting referenced paths from detection table."""
        mock_session = AsyncMock()

        # Mock detection query result
        detection_result = MagicMock()
        detection_result.all.return_value = [
            ("/path/to/image1.jpg", "/path/to/thumb1.jpg"),
            ("/path/to/image2.jpg", None),
        ]

        # Mock event query result
        event_result = MagicMock()
        event_result.all.return_value = [("/path/to/clip1.mp4",)]

        # Execute returns different results based on query
        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return detection_result
            return event_result

        mock_session.execute = mock_execute

        paths = await scanner._get_referenced_paths(mock_session)

        # Should include all paths from both queries
        assert len(paths) >= 3  # At least image1, thumb1, clip1

    @pytest.mark.asyncio
    async def test_get_referenced_paths_handles_none(self, scanner):
        """Test handling of None values in results."""
        mock_session = AsyncMock()

        # Mock detection query with None values
        detection_result = MagicMock()
        detection_result.all.return_value = [
            (None, None),
            ("/path/to/image.jpg", None),
        ]

        # Mock event query
        event_result = MagicMock()
        event_result.all.return_value = [(None,)]

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return detection_result
            return event_result

        mock_session.execute = mock_execute

        paths = await scanner._get_referenced_paths(mock_session)

        # Should only include the one valid path
        assert len(paths) == 1


# =============================================================================
# Directory Scan Tests
# =============================================================================


class TestScanDirectory:
    """Tests for scan_directory method."""

    @pytest.mark.asyncio
    async def test_scan_empty_directory(self, tmp_path, scanner):
        """Test scanning an empty directory."""
        result = await scanner.scan_directory(tmp_path)

        assert result.scanned_files == 0
        assert result.orphaned_files == []
        assert result.total_orphaned_bytes == 0

    @pytest.mark.asyncio
    async def test_scan_finds_orphans(self, tmp_path, scanner):
        """Test scanning finds orphaned files."""
        # Create test files
        (tmp_path / "orphan.jpg").write_text("orphan data")

        # Mock database to return empty set (all files are orphans)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch(
            "backend.services.orphan_scanner_service.get_session",
            mock_get_session,
        ):
            result = await scanner.scan_directory(tmp_path)

        assert result.scanned_files == 1
        assert len(result.orphaned_files) == 1
        assert result.total_orphaned_bytes > 0

    @pytest.mark.asyncio
    async def test_scan_excludes_referenced_files(self, tmp_path, scanner):
        """Test scanning excludes files that are in database."""
        # Create test file
        test_file = tmp_path / "referenced.jpg"
        test_file.write_text("referenced data")
        resolved_path = str(test_file.resolve())

        # Mock database to return this file as referenced
        mock_session = AsyncMock()

        detection_result = MagicMock()
        detection_result.all.return_value = [(resolved_path, None)]

        event_result = MagicMock()
        event_result.all.return_value = []

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return detection_result
            return event_result

        mock_session.execute = mock_execute

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch(
            "backend.services.orphan_scanner_service.get_session",
            mock_get_session,
        ):
            result = await scanner.scan_directory(tmp_path)

        assert result.scanned_files == 1
        assert len(result.orphaned_files) == 0  # File is referenced

    @pytest.mark.asyncio
    async def test_scan_uses_default_path(self, tmp_path):
        """Test scanning uses default base_path when none specified."""
        from backend.services.orphan_scanner_service import OrphanedFileScanner

        scanner = OrphanedFileScanner(base_path=tmp_path)
        (tmp_path / "test.jpg").write_text("test")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch(
            "backend.services.orphan_scanner_service.get_session",
            mock_get_session,
        ):
            # Call without explicit path - should use base_path
            result = await scanner.scan_directory()

        assert result.scanned_files == 1


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton management."""

    def test_get_orphan_scanner_returns_singleton(self):
        """Test get_orphan_scanner returns same instance."""
        from backend.services.orphan_scanner_service import (
            get_orphan_scanner,
            reset_orphan_scanner,
        )

        reset_orphan_scanner()

        scanner1 = get_orphan_scanner()
        scanner2 = get_orphan_scanner()

        assert scanner1 is scanner2

        reset_orphan_scanner()

    def test_reset_clears_singleton(self):
        """Test reset_orphan_scanner clears the singleton."""
        from backend.services.orphan_scanner_service import (
            get_orphan_scanner,
            reset_orphan_scanner,
        )

        scanner1 = get_orphan_scanner()
        reset_orphan_scanner()
        scanner2 = get_orphan_scanner()

        assert scanner1 is not scanner2

        reset_orphan_scanner()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_scan_handles_database_error(self, tmp_path, scanner):
        """Test scan handles database errors gracefully."""
        (tmp_path / "test.jpg").write_text("test")

        # Note: yield after raise is required for context manager syntax
        # The _always_raise flag ensures vulture doesn't report unreachable code
        _always_raise = True

        @contextlib.asynccontextmanager
        async def mock_get_session():
            if _always_raise:
                raise Exception("Database connection failed")
            yield

        with patch(
            "backend.services.orphan_scanner_service.get_session",
            mock_get_session,
        ):
            result = await scanner.scan_directory(tmp_path)

        assert result.scanned_files == 1
        assert len(result.scan_errors) > 0

    def test_list_files_handles_not_a_directory(self, tmp_path, scanner):
        """Test listing handles path that is not a directory."""
        test_file = tmp_path / "file.jpg"
        test_file.write_text("test")

        files = scanner._list_files(test_file)
        assert files == []

    @pytest.mark.asyncio
    async def test_scan_all_directories(self, tmp_path, scanner):
        """Test scan_all_directories calls scan_directory with base_path."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch(
            "backend.services.orphan_scanner_service.get_session",
            mock_get_session,
        ):
            result = await scanner.scan_all_directories()

        assert result.scanned_files >= 0  # Valid result
