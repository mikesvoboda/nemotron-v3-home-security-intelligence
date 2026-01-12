"""Tests for FileCleanupService cascade file deletion.

Related Linear issue: NEM-2384

Tests cover:
- Getting all files associated with an event
- Deleting event files with result tracking
- Batch deletion for retention cleanup
- Missing files don't cause failures
- File system errors are tracked but don't fail operations
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.file_cleanup_service import (
    BatchCleanupResult,
    FileCleanupResult,
    FileCleanupService,
    get_file_cleanup_service,
    reset_file_cleanup_service,
)


class TestFileCleanupResult:
    """Tests for FileCleanupResult dataclass."""

    def test_create_result_with_defaults(self) -> None:
        """Test creating a result with default values."""
        result = FileCleanupResult(event_id=123)

        assert result.event_id == 123
        assert result.deleted == []
        assert result.missing == []
        assert result.failed == []
        assert result.total_bytes_freed == 0

    def test_success_property_no_failures(self) -> None:
        """Test success property returns True when no failures."""
        result = FileCleanupResult(event_id=123)
        result.deleted = ["/path/to/file.jpg"]
        result.missing = ["/path/to/missing.jpg"]

        assert result.success is True

    def test_success_property_with_failures(self) -> None:
        """Test success property returns False when failures exist."""
        result = FileCleanupResult(event_id=123)
        result.failed = [("/path/to/file.jpg", "Permission denied")]

        assert result.success is False

    def test_total_files_property(self) -> None:
        """Test total_files property counts all files."""
        result = FileCleanupResult(event_id=123)
        result.deleted = ["/a.jpg", "/b.jpg"]
        result.missing = ["/c.jpg"]
        result.failed = [("/d.jpg", "error")]

        assert result.total_files == 4

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        result = FileCleanupResult(event_id=123)
        result.deleted = ["/a.jpg"]
        result.missing = ["/b.jpg"]
        result.failed = [("/c.jpg", "Permission denied")]
        result.total_bytes_freed = 1024

        data = result.to_dict()

        assert data["event_id"] == "123"
        assert data["deleted_count"] == 1
        assert data["missing_count"] == 1
        assert data["failed_count"] == 1
        assert data["total_bytes_freed"] == 1024
        assert data["success"] is False
        assert data["failed_files"] == [("/c.jpg", "Permission denied")]


class TestBatchCleanupResult:
    """Tests for BatchCleanupResult dataclass."""

    def test_create_result_with_defaults(self) -> None:
        """Test creating a batch result with default values."""
        result = BatchCleanupResult()

        assert result.event_ids == []
        assert result.total_deleted == 0
        assert result.total_missing == 0
        assert result.total_failed == 0
        assert result.total_bytes_freed == 0
        assert result.per_event_results == []

    def test_success_property_no_failures(self) -> None:
        """Test success property returns True when no failures."""
        result = BatchCleanupResult()
        result.total_deleted = 5
        result.total_missing = 2

        assert result.success is True

    def test_success_property_with_failures(self) -> None:
        """Test success property returns False when failures exist."""
        result = BatchCleanupResult()
        result.total_failed = 1

        assert result.success is False

    def test_events_processed_property(self) -> None:
        """Test events_processed property counts events."""
        result = BatchCleanupResult()
        result.event_ids = [1, 2, 3]

        assert result.events_processed == 3

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        result = BatchCleanupResult()
        result.event_ids = [1, 2]
        result.total_deleted = 10
        result.total_missing = 3
        result.total_failed = 1
        result.total_bytes_freed = 2048

        data = result.to_dict()

        assert data["events_processed"] == 2
        assert data["total_deleted"] == 10
        assert data["total_missing"] == 3
        assert data["total_failed"] == 1
        assert data["total_bytes_freed"] == 2048
        assert data["success"] is False


class TestFileCleanupServiceGetEventFiles:
    """Tests for FileCleanupService.get_event_files method."""

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    def _create_mock_event(
        self,
        event_id: int = 1,
        clip_path: str | None = None,
        detections: list | None = None,
    ) -> MagicMock:
        """Create a mock Event object."""
        event = MagicMock()
        event.id = event_id
        event.clip_path = clip_path
        event.detections = detections or []
        return event

    def _create_mock_detection(
        self,
        detection_id: int = 1,
        file_path: str | None = None,
        thumbnail_path: str | None = None,
    ) -> MagicMock:
        """Create a mock Detection object."""
        detection = MagicMock()
        detection.id = detection_id
        detection.file_path = file_path
        detection.thumbnail_path = thumbnail_path
        return detection

    @pytest.mark.asyncio
    async def test_get_event_files_all_paths(self, mock_db_session: MagicMock) -> None:
        """Test getting all file paths from event with detections."""
        detection = self._create_mock_detection(
            detection_id=1,
            file_path="/export/foscam/front_door/snap_001.jpg",
            thumbnail_path="/export/foscam/front_door/thumb_1.jpg",
        )
        event = self._create_mock_event(
            event_id=123,
            clip_path="/export/foscam/front_door/clip_123.mp4",
            detections=[detection],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        paths = await service.get_event_files(event_id=123, db=mock_db_session)

        assert len(paths) == 3
        path_strs = [str(p) for p in paths]
        assert "/export/foscam/front_door/clip_123.mp4" in path_strs
        assert "/export/foscam/front_door/snap_001.jpg" in path_strs
        assert "/export/foscam/front_door/thumb_1.jpg" in path_strs

    @pytest.mark.asyncio
    async def test_get_event_files_event_not_found(self, mock_db_session: MagicMock) -> None:
        """Test getting files when event doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        paths = await service.get_event_files(event_id=999, db=mock_db_session)

        assert paths == []

    @pytest.mark.asyncio
    async def test_get_event_files_no_clip_path(self, mock_db_session: MagicMock) -> None:
        """Test getting files when event has no clip."""
        detection = self._create_mock_detection(
            detection_id=1,
            file_path="/export/foscam/front_door/snap_001.jpg",
            thumbnail_path="/export/foscam/front_door/thumb_1.jpg",
        )
        event = self._create_mock_event(
            event_id=123,
            clip_path=None,
            detections=[detection],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        paths = await service.get_event_files(event_id=123, db=mock_db_session)

        assert len(paths) == 2

    @pytest.mark.asyncio
    async def test_get_event_files_no_detections(self, mock_db_session: MagicMock) -> None:
        """Test getting files when event has no detections."""
        event = self._create_mock_event(
            event_id=123,
            clip_path="/export/foscam/front_door/clip_123.mp4",
            detections=[],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        paths = await service.get_event_files(event_id=123, db=mock_db_session)

        assert len(paths) == 1
        assert str(paths[0]).endswith("clip_123.mp4")

    @pytest.mark.asyncio
    async def test_get_event_files_multiple_detections(self, mock_db_session: MagicMock) -> None:
        """Test getting files from multiple detections."""
        detection1 = self._create_mock_detection(
            detection_id=1,
            file_path="/export/foscam/front_door/snap_001.jpg",
            thumbnail_path="/export/foscam/front_door/thumb_1.jpg",
        )
        detection2 = self._create_mock_detection(
            detection_id=2,
            file_path="/export/foscam/front_door/snap_002.jpg",
            thumbnail_path=None,  # No thumbnail
        )
        event = self._create_mock_event(
            event_id=123,
            clip_path=None,
            detections=[detection1, detection2],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        paths = await service.get_event_files(event_id=123, db=mock_db_session)

        assert len(paths) == 3  # 2 file_paths + 1 thumbnail_path


class TestFileCleanupServiceDeleteEventFiles:
    """Tests for FileCleanupService.delete_event_files method."""

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    def _create_mock_event(
        self,
        event_id: int = 1,
        clip_path: str | None = None,
        detections: list | None = None,
    ) -> MagicMock:
        """Create a mock Event object."""
        event = MagicMock()
        event.id = event_id
        event.clip_path = clip_path
        event.detections = detections or []
        return event

    def _create_mock_detection(
        self,
        detection_id: int = 1,
        file_path: str | None = None,
        thumbnail_path: str | None = None,
    ) -> MagicMock:
        """Create a mock Detection object."""
        detection = MagicMock()
        detection.id = detection_id
        detection.file_path = file_path
        detection.thumbnail_path = thumbnail_path
        return detection

    @pytest.mark.asyncio
    async def test_delete_event_files_success(self, mock_db_session: MagicMock) -> None:
        """Test successfully deleting event files."""
        # Create temp files with content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            f1.write(b"test image content")
            temp1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
            f2.write(b"test thumbnail content")
            temp2 = f2.name

        try:
            detection = self._create_mock_detection(
                detection_id=1,
                file_path=temp1,
                thumbnail_path=temp2,
            )
            event = self._create_mock_event(
                event_id=123,
                clip_path=None,
                detections=[detection],
            )

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = event
            mock_db_session.execute.return_value = mock_result

            service = FileCleanupService()
            result = await service.delete_event_files(event_id=123, db=mock_db_session)

            assert result.success is True
            assert len(result.deleted) == 2
            assert len(result.failed) == 0
            assert result.total_bytes_freed > 0

            # Verify files were deleted
            assert not Path(temp1).exists()
            assert not Path(temp2).exists()
        finally:
            Path(temp1).unlink(missing_ok=True)
            Path(temp2).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_delete_event_files_missing_files(self, mock_db_session: MagicMock) -> None:
        """Test that missing files don't cause failures."""
        detection = self._create_mock_detection(
            detection_id=1,
            file_path="/nonexistent/snap_001.jpg",
            thumbnail_path="/nonexistent/thumb_1.jpg",
        )
        event = self._create_mock_event(
            event_id=123,
            clip_path=None,
            detections=[detection],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        result = await service.delete_event_files(event_id=123, db=mock_db_session)

        assert result.success is True  # No failures
        assert len(result.deleted) == 0
        assert len(result.missing) == 2
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_delete_event_files_no_files(self, mock_db_session: MagicMock) -> None:
        """Test deleting when event has no files."""
        event = self._create_mock_event(
            event_id=123,
            clip_path=None,
            detections=[],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        result = await service.delete_event_files(event_id=123, db=mock_db_session)

        assert result.success is True
        assert result.total_files == 0

    @pytest.mark.asyncio
    async def test_delete_event_files_event_not_found(self, mock_db_session: MagicMock) -> None:
        """Test deleting when event doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        result = await service.delete_event_files(event_id=999, db=mock_db_session)

        assert result.success is True  # No failures
        assert result.total_files == 0

    @pytest.mark.asyncio
    async def test_delete_event_files_mixed_success(self, mock_db_session: MagicMock) -> None:
        """Test deleting mix of existing and missing files."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            temp_path = f.name

        try:
            detection = self._create_mock_detection(
                detection_id=1,
                file_path=temp_path,
                thumbnail_path="/nonexistent/thumb.jpg",
            )
            event = self._create_mock_event(
                event_id=123,
                clip_path=None,
                detections=[detection],
            )

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = event
            mock_db_session.execute.return_value = mock_result

            service = FileCleanupService()
            result = await service.delete_event_files(event_id=123, db=mock_db_session)

            assert result.success is True
            assert len(result.deleted) == 1
            assert len(result.missing) == 1
            assert not Path(temp_path).exists()
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestFileCleanupServiceDeleteFilesBatch:
    """Tests for FileCleanupService.delete_files_batch method."""

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    def _create_mock_event(
        self,
        event_id: int = 1,
        clip_path: str | None = None,
        detections: list | None = None,
    ) -> MagicMock:
        """Create a mock Event object."""
        event = MagicMock()
        event.id = event_id
        event.clip_path = clip_path
        event.detections = detections or []
        return event

    def _create_mock_detection(
        self,
        detection_id: int = 1,
        file_path: str | None = None,
        thumbnail_path: str | None = None,
    ) -> MagicMock:
        """Create a mock Detection object."""
        detection = MagicMock()
        detection.id = detection_id
        detection.file_path = file_path
        detection.thumbnail_path = thumbnail_path
        return detection

    @pytest.mark.asyncio
    async def test_batch_delete_success(self, mock_db_session: MagicMock) -> None:
        """Test successfully deleting files for multiple events."""
        # Create temp files for two events
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            temp1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
            temp2 = f2.name

        try:
            detection1 = self._create_mock_detection(detection_id=1, file_path=temp1)
            event1 = self._create_mock_event(event_id=1, detections=[detection1])

            detection2 = self._create_mock_detection(detection_id=2, file_path=temp2)
            event2 = self._create_mock_event(event_id=2, detections=[detection2])

            # Mock returns different events for different queries
            call_count = 0

            async def mock_execute(stmt):
                nonlocal call_count
                result = MagicMock()
                if call_count == 0:
                    result.scalar_one_or_none.return_value = event1
                else:
                    result.scalar_one_or_none.return_value = event2
                call_count += 1
                return result

            mock_db_session.execute = mock_execute

            service = FileCleanupService()
            result = await service.delete_files_batch(event_ids=[1, 2], db=mock_db_session)

            assert result.success is True
            assert result.events_processed == 2
            assert result.total_deleted == 2
            assert len(result.per_event_results) == 2
        finally:
            Path(temp1).unlink(missing_ok=True)
            Path(temp2).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_batch_delete_empty_list(self, mock_db_session: MagicMock) -> None:
        """Test batch delete with empty event list."""
        service = FileCleanupService()
        result = await service.delete_files_batch(event_ids=[], db=mock_db_session)

        assert result.success is True
        assert result.events_processed == 0
        assert result.total_deleted == 0

    @pytest.mark.asyncio
    async def test_batch_delete_aggregates_stats(self, mock_db_session: MagicMock) -> None:
        """Test that batch delete properly aggregates statistics."""
        # Create files for event 1
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            temp_path = f.name

        try:
            detection = self._create_mock_detection(detection_id=1, file_path=temp_path)
            event1 = self._create_mock_event(event_id=1, detections=[detection])

            # Event 2 has missing files
            detection2 = self._create_mock_detection(
                detection_id=2, file_path="/nonexistent/file.jpg"
            )
            event2 = self._create_mock_event(event_id=2, detections=[detection2])

            call_count = 0

            async def mock_execute(stmt):
                nonlocal call_count
                result = MagicMock()
                if call_count == 0:
                    result.scalar_one_or_none.return_value = event1
                else:
                    result.scalar_one_or_none.return_value = event2
                call_count += 1
                return result

            mock_db_session.execute = mock_execute

            service = FileCleanupService()
            result = await service.delete_files_batch(event_ids=[1, 2], db=mock_db_session)

            assert result.events_processed == 2
            assert result.total_deleted == 1  # Only one file existed
            assert result.total_missing == 1  # One file was missing
            assert result.total_failed == 0
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestFileCleanupServiceDeleteFilesByPaths:
    """Tests for FileCleanupService.delete_files_by_paths method."""

    @pytest.mark.asyncio
    async def test_delete_files_by_paths_success(self) -> None:
        """Test deleting files directly by paths."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            temp1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
            temp2 = f2.name

        try:
            service = FileCleanupService()
            result = await service.delete_files_by_paths(file_paths=[temp1, temp2], event_id=123)

            assert result.success is True
            assert len(result.deleted) == 2
            assert result.event_id == 123
            assert not Path(temp1).exists()
            assert not Path(temp2).exists()
        finally:
            Path(temp1).unlink(missing_ok=True)
            Path(temp2).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_delete_files_by_paths_empty_list(self) -> None:
        """Test deleting empty file list."""
        service = FileCleanupService()
        result = await service.delete_files_by_paths(file_paths=[])

        assert result.success is True
        assert result.total_files == 0

    @pytest.mark.asyncio
    async def test_delete_files_by_paths_filters_empty_paths(self) -> None:
        """Test that empty/None paths are filtered out."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            temp_path = f.name

        try:
            service = FileCleanupService()
            result = await service.delete_files_by_paths(
                file_paths=[temp_path, "", None]  # type: ignore[list-item]
            )

            assert len(result.deleted) == 1
            assert not Path(temp_path).exists()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_delete_files_by_paths_nonexistent(self) -> None:
        """Test deleting non-existent files marks them as missing."""
        service = FileCleanupService()
        result = await service.delete_files_by_paths(file_paths=["/nonexistent/file.jpg"])

        assert result.success is True
        assert len(result.deleted) == 0
        assert len(result.missing) == 1


class TestFileCleanupServiceDeleteSingleFile:
    """Tests for FileCleanupService._delete_single_file method."""

    def test_delete_single_file_success(self) -> None:
        """Test successfully deleting a single file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            temp_path = f.name
            f.write(b"test content")

        try:
            service = FileCleanupService()
            deleted, error, bytes_freed = service._delete_single_file(Path(temp_path))

            assert deleted is True
            assert error is None
            assert bytes_freed > 0
            assert not Path(temp_path).exists()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_delete_single_file_missing(self) -> None:
        """Test deleting a missing file returns False without error."""
        service = FileCleanupService()
        deleted, error, bytes_freed = service._delete_single_file(Path("/nonexistent/file.jpg"))

        assert deleted is False
        assert error is None
        assert bytes_freed == 0

    def test_delete_single_file_permission_error(self) -> None:
        """Test that permission errors are captured."""
        service = FileCleanupService()

        # Mock Path.exists() to return True but unlink() to fail
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = MagicMock(st_size=1024)
                with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
                    deleted, error, bytes_freed = service._delete_single_file(
                        Path("/protected/file.jpg")
                    )

        assert deleted is False
        assert "Permission denied" in error
        assert bytes_freed == 0


class TestFileCleanupServiceCollectEventFilePaths:
    """Tests for FileCleanupService._collect_event_file_paths method."""

    def _create_mock_event(
        self,
        clip_path: str | None = None,
        detections: list | None = None,
    ) -> MagicMock:
        """Create a mock Event object."""
        event = MagicMock()
        event.clip_path = clip_path
        event.detections = detections or []
        return event

    def _create_mock_detection(
        self,
        file_path: str | None = None,
        thumbnail_path: str | None = None,
    ) -> MagicMock:
        """Create a mock Detection object."""
        detection = MagicMock()
        detection.file_path = file_path
        detection.thumbnail_path = thumbnail_path
        return detection

    def test_collect_all_paths(self) -> None:
        """Test collecting all file paths from event and detections."""
        detection1 = self._create_mock_detection(
            file_path="/export/foscam/front/snap_001.jpg",
            thumbnail_path="/export/foscam/front/thumb_1.jpg",
        )
        detection2 = self._create_mock_detection(
            file_path="/export/foscam/front/snap_002.jpg",
            thumbnail_path=None,
        )
        event = self._create_mock_event(
            clip_path="/export/foscam/front/clip_123.mp4",
            detections=[detection1, detection2],
        )

        service = FileCleanupService()
        paths = service._collect_event_file_paths(event)

        assert "/export/foscam/front/clip_123.mp4" in paths
        assert "/export/foscam/front/snap_001.jpg" in paths
        assert "/export/foscam/front/thumb_1.jpg" in paths
        assert "/export/foscam/front/snap_002.jpg" in paths
        assert len(paths) == 4

    def test_collect_paths_no_clip(self) -> None:
        """Test collecting paths when event has no clip."""
        detection = self._create_mock_detection(
            file_path="/export/foscam/front/snap_001.jpg",
            thumbnail_path="/export/foscam/front/thumb_1.jpg",
        )
        event = self._create_mock_event(clip_path=None, detections=[detection])

        service = FileCleanupService()
        paths = service._collect_event_file_paths(event)

        assert len(paths) == 2

    def test_collect_paths_empty(self) -> None:
        """Test collecting paths when event has no files."""
        event = self._create_mock_event(clip_path=None, detections=[])

        service = FileCleanupService()
        paths = service._collect_event_file_paths(event)

        assert len(paths) == 0


class TestFileCleanupServiceResolvePath:
    """Tests for FileCleanupService._resolve_path method."""

    def test_resolve_absolute_path(self) -> None:
        """Test resolving an absolute path."""
        service = FileCleanupService()
        path = service._resolve_path("/export/foscam/front/snap_001.jpg")

        assert str(path) == "/export/foscam/front/snap_001.jpg"

    def test_resolve_relative_path_with_base(self) -> None:
        """Test resolving a relative path with base path."""
        service = FileCleanupService(base_path="/export/foscam")
        path = service._resolve_path("front/snap_001.jpg")

        assert str(path) == "/export/foscam/front/snap_001.jpg"

    def test_resolve_relative_path_without_base(self) -> None:
        """Test resolving a relative path without base path."""
        service = FileCleanupService()
        path = service._resolve_path("front/snap_001.jpg")

        # Path remains relative
        assert str(path) == "front/snap_001.jpg"

    def test_resolve_absolute_path_ignores_base(self) -> None:
        """Test that absolute paths ignore base path."""
        service = FileCleanupService(base_path="/other/base")
        path = service._resolve_path("/export/foscam/front/snap_001.jpg")

        assert str(path) == "/export/foscam/front/snap_001.jpg"


class TestFileCleanupServiceSingleton:
    """Tests for FileCleanupService singleton pattern."""

    def test_get_file_cleanup_service_returns_same_instance(self) -> None:
        """Test that get_file_cleanup_service returns the same instance."""
        reset_file_cleanup_service()
        service1 = get_file_cleanup_service()
        service2 = get_file_cleanup_service()

        assert service1 is service2

    def test_reset_file_cleanup_service_clears_instance(self) -> None:
        """Test that reset_file_cleanup_service clears the singleton."""
        reset_file_cleanup_service()
        service1 = get_file_cleanup_service()
        reset_file_cleanup_service()
        service2 = get_file_cleanup_service()

        assert service1 is not service2


class TestFileCleanupServiceInitialization:
    """Tests for FileCleanupService initialization."""

    def test_init_without_base_path(self) -> None:
        """Test initialization without base path."""
        service = FileCleanupService()

        assert service._base_path is None

    def test_init_with_base_path(self) -> None:
        """Test initialization with base path."""
        service = FileCleanupService(base_path="/export/foscam")

        assert service._base_path == Path("/export/foscam")

    def test_init_with_string_base_path(self) -> None:
        """Test initialization with string base path."""
        service = FileCleanupService(base_path="/export/foscam")

        assert isinstance(service._base_path, Path)
        assert str(service._base_path) == "/export/foscam"
