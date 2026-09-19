"""Tests for EventService cascade file deletion.

Related Linear issue: NEM-2259

Tests cover:
- Soft delete schedules file deletion with delay
- Hard delete immediately deletes files
- Batch deletions clean up all associated files
- File system errors are logged but don't block DB deletion
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.event_service import EventService, get_event_service, reset_event_service
from backend.services.file_service import FileService


class TestEventServiceSoftDeleteFileDeletion:
    """Tests for file deletion scheduling during soft delete."""

    @pytest.fixture
    def mock_file_service(self) -> MagicMock:
        """Create a mock FileService."""
        service = MagicMock(spec=FileService)
        service.schedule_deletion = AsyncMock(return_value="test-job-id")
        service.cancel_deletion_by_event_id = AsyncMock(return_value=1)
        service.delete_files_immediately = AsyncMock(return_value=(2, 2))
        return service

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
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
        event.is_deleted = False
        event.deleted_at = None
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
    async def test_soft_delete_schedules_file_deletion(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test that soft delete schedules file deletion with FileService."""
        # Create mock event with clip path and detections
        detection = self._create_mock_detection(
            detection_id=1,
            file_path="/path/to/detection.jpg",
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = self._create_mock_event(
            event_id=123,
            clip_path="/path/to/clip.mp4",
            detections=[detection],
        )

        # Set up mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        # Create service with mock file service
        service = EventService(file_service=mock_file_service)

        # Execute soft delete
        result = await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        # Verify file deletion was scheduled
        mock_file_service.schedule_deletion.assert_called_once()
        call_args = mock_file_service.schedule_deletion.call_args

        # Verify file paths were collected
        file_paths = call_args.kwargs["file_paths"]
        assert "/path/to/clip.mp4" in file_paths
        assert "/path/to/detection.jpg" in file_paths
        assert "/path/to/thumb.jpg" in file_paths
        assert call_args.kwargs["event_id"] == 123

        # Verify event was soft deleted
        assert event.deleted_at is not None
        assert result == event

    @pytest.mark.asyncio
    async def test_soft_delete_no_cascade_skips_file_deletion(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test that soft delete without cascade doesn't schedule file deletion."""
        event = self._create_mock_event(
            event_id=123,
            clip_path="/path/to/clip.mp4",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)

        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=False)

        # File deletion should NOT be scheduled when cascade=False
        mock_file_service.schedule_deletion.assert_not_called()

    @pytest.mark.asyncio
    async def test_soft_delete_with_no_files(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test soft delete when event has no files."""
        event = self._create_mock_event(
            event_id=123,
            clip_path=None,
            detections=[],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)

        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        # No files to schedule for deletion
        mock_file_service.schedule_deletion.assert_not_called()


class TestEventServiceHardDeleteFileDeletion:
    """Tests for immediate file deletion during hard delete."""

    @pytest.fixture
    def mock_file_service(self) -> MagicMock:
        """Create a mock FileService."""
        service = MagicMock(spec=FileService)
        service.schedule_deletion = AsyncMock(return_value="test-job-id")
        service.cancel_deletion_by_event_id = AsyncMock(return_value=1)
        service.delete_files_immediately = AsyncMock(return_value=(3, 0))  # 3 deleted, 0 failed
        return service

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.delete = AsyncMock()
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
        event.is_deleted = False
        event.deleted_at = None
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
    async def test_hard_delete_immediately_deletes_files(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test that hard delete immediately deletes files without scheduling."""
        detection = self._create_mock_detection(
            detection_id=1,
            file_path="/path/to/detection.jpg",
            thumbnail_path="/path/to/thumb.jpg",
        )
        event = self._create_mock_event(
            event_id=123,
            clip_path="/path/to/clip.mp4",
            detections=[detection],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)

        files_deleted, files_failed = await service.hard_delete_event(
            event_id=123, db=mock_db_session
        )

        # Verify immediate deletion was called (not scheduled)
        mock_file_service.delete_files_immediately.assert_called_once()
        call_args = mock_file_service.delete_files_immediately.call_args

        file_paths = call_args.kwargs["file_paths"]
        assert "/path/to/clip.mp4" in file_paths
        assert "/path/to/detection.jpg" in file_paths
        assert "/path/to/thumb.jpg" in file_paths

        # Should NOT schedule deletion for hard delete
        mock_file_service.schedule_deletion.assert_not_called()

        # Verify return values
        assert files_deleted == 3
        assert files_failed == 0  # No failures reported

    @pytest.mark.asyncio
    async def test_hard_delete_with_no_files(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test hard delete when event has no files."""
        event = self._create_mock_event(
            event_id=123,
            clip_path=None,
            detections=[],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)

        files_deleted, files_failed = await service.hard_delete_event(
            event_id=123, db=mock_db_session
        )

        # No files to delete
        mock_file_service.delete_files_immediately.assert_not_called()
        assert files_deleted == 0
        assert files_failed == 0

    @pytest.mark.asyncio
    async def test_hard_delete_file_errors_dont_block_deletion(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test that file system errors are logged but don't block DB deletion."""
        event = self._create_mock_event(
            event_id=123,
            clip_path="/path/to/clip.mp4",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        # Simulate file deletion failure
        mock_file_service.delete_files_immediately = AsyncMock(return_value=(0, 1))

        service = EventService(file_service=mock_file_service)

        files_deleted, files_failed = await service.hard_delete_event(
            event_id=123, db=mock_db_session
        )

        # Should report the failure
        assert files_deleted == 0
        assert files_failed == 1

        # DB deletion should still proceed (the event is returned)
        # The hard_delete_event method collects files and deletes them,
        # but the actual DB deletion happens in the caller

    @pytest.mark.asyncio
    async def test_hard_delete_event_not_found(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test hard delete when event doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)

        with pytest.raises(ValueError, match="Event not found"):
            await service.hard_delete_event(event_id=999, db=mock_db_session)


class TestEventServiceRestoreFileDeletion:
    """Tests for cancelling scheduled file deletion during restore."""

    @pytest.fixture
    def mock_file_service(self) -> MagicMock:
        """Create a mock FileService."""
        service = MagicMock(spec=FileService)
        service.cancel_deletion_by_event_id = AsyncMock(return_value=2)
        return service

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_restore_cancels_pending_file_deletions(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test that restore cancels any pending file deletions."""
        event = MagicMock()
        event.id = 123
        event.is_deleted = True
        event.deleted_at = datetime.now(UTC)
        event.detections = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)

        await service.restore_event(event_id=123, db=mock_db_session, cascade=True)

        # Verify file deletion cancellation was called
        mock_file_service.cancel_deletion_by_event_id.assert_called_once_with(123)

        # Verify event was restored
        assert event.deleted_at is None


class TestEventServiceCollectFilePaths:
    """Tests for _collect_file_paths helper method."""

    def test_collect_all_file_paths(self) -> None:
        """Test collecting all file paths from event and detections."""
        event = MagicMock()
        event.clip_path = "/path/to/clip.mp4"

        detection1 = MagicMock()
        detection1.file_path = "/path/to/det1.jpg"
        detection1.thumbnail_path = "/path/to/thumb1.jpg"

        detection2 = MagicMock()
        detection2.file_path = "/path/to/det2.jpg"
        detection2.thumbnail_path = None  # No thumbnail

        event.detections = [detection1, detection2]

        service = EventService()
        paths = service._collect_file_paths(event)

        assert "/path/to/clip.mp4" in paths
        assert "/path/to/det1.jpg" in paths
        assert "/path/to/thumb1.jpg" in paths
        assert "/path/to/det2.jpg" in paths
        assert len(paths) == 4

    def test_collect_file_paths_no_clip(self) -> None:
        """Test collecting paths when event has no clip."""
        event = MagicMock()
        event.clip_path = None

        detection = MagicMock()
        detection.file_path = "/path/to/det.jpg"
        detection.thumbnail_path = "/path/to/thumb.jpg"

        event.detections = [detection]

        service = EventService()
        paths = service._collect_file_paths(event)

        assert "/path/to/det.jpg" in paths
        assert "/path/to/thumb.jpg" in paths
        assert len(paths) == 2

    def test_collect_file_paths_empty(self) -> None:
        """Test collecting paths when event has no files."""
        event = MagicMock()
        event.clip_path = None
        event.detections = []

        service = EventService()
        paths = service._collect_file_paths(event)

        assert len(paths) == 0


class TestFileServiceImmediateDeletion:
    """Tests for FileService.delete_files_immediately method."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.zrem = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_delete_files_immediately_success(self, mock_redis: MagicMock) -> None:
        """Test successfully deleting files immediately."""
        # Create temp files
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            temp1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            temp2 = f2.name

        try:
            assert Path(temp1).exists()
            assert Path(temp2).exists()

            service = FileService(redis_client=mock_redis)
            deleted, failed = await service.delete_files_immediately(file_paths=[temp1, temp2])

            assert deleted == 2
            assert failed == 0
            assert not Path(temp1).exists()
            assert not Path(temp2).exists()
        finally:
            Path(temp1).unlink(missing_ok=True)
            Path(temp2).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_delete_files_immediately_nonexistent(self, mock_redis: MagicMock) -> None:
        """Test deleting non-existent files counts as success."""
        service = FileService(redis_client=mock_redis)
        deleted, failed = await service.delete_files_immediately(
            file_paths=["/nonexistent/file1.jpg", "/nonexistent/file2.jpg"]
        )

        # Non-existent files are counted as "deleted" (no file to delete)
        assert deleted == 0
        assert failed == 0

    @pytest.mark.asyncio
    async def test_delete_files_immediately_mixed(self, mock_redis: MagicMock) -> None:
        """Test deleting mix of existing and non-existent files."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            service = FileService(redis_client=mock_redis)
            deleted, failed = await service.delete_files_immediately(
                file_paths=[temp_path, "/nonexistent/file.jpg"]
            )

            assert deleted == 1  # Only the existing file was deleted
            assert failed == 0
            assert not Path(temp_path).exists()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_delete_files_immediately_empty_list(self, mock_redis: MagicMock) -> None:
        """Test deleting empty file list."""
        service = FileService(redis_client=mock_redis)
        deleted, failed = await service.delete_files_immediately(file_paths=[])

        assert deleted == 0
        assert failed == 0

    @pytest.mark.asyncio
    async def test_delete_files_immediately_with_empty_paths(self, mock_redis: MagicMock) -> None:
        """Test that empty/None paths are filtered out."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            service = FileService(redis_client=mock_redis)
            deleted, failed = await service.delete_files_immediately(
                file_paths=[temp_path, "", None]  # type: ignore[list-item]
            )

            assert deleted == 1
            assert failed == 0
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestEventServiceSingleton:
    """Tests for EventService singleton pattern."""

    def test_get_event_service_returns_same_instance(self) -> None:
        """Test that get_event_service returns the same instance."""
        reset_event_service()
        service1 = get_event_service()
        service2 = get_event_service()

        assert service1 is service2

    def test_reset_event_service_clears_instance(self) -> None:
        """Test that reset_event_service clears the singleton."""
        reset_event_service()
        service1 = get_event_service()
        reset_event_service()
        service2 = get_event_service()

        assert service1 is not service2


# =============================================================================
# WP4.4 kill tests — surviving-mutant clusters (triage dossier:
# .wp25-feed/wp44-triage/event_service.md, clusters C1/C2 flips, C5-C9)
# =============================================================================


class TestWp44EventServiceDeleteGaps:
    """Statement-shape, cascade-default, and tz contracts the mocks hide."""

    @pytest.fixture
    def mock_file_service(self) -> MagicMock:
        """Create a mock FileService."""
        service = MagicMock(spec=FileService)
        service.schedule_deletion = AsyncMock(return_value="test-job-id")
        service.cancel_deletion_by_event_id = AsyncMock(return_value=1)
        service.delete_files_immediately = AsyncMock(return_value=(2, 2))
        return service

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    def _mock_event(
        self, event_id: int = 1, clip_path: str | None = None, deleted: bool = False
    ) -> MagicMock:
        """Create a mock Event object."""
        event = MagicMock()
        event.id = event_id
        event.clip_path = clip_path
        event.is_deleted = deleted
        event.deleted_at = datetime.now(UTC) if deleted else None
        event.detections = []
        return event

    def _mock_result(self, event: MagicMock | None) -> MagicMock:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        return mock_result

    @pytest.mark.asyncio
    async def test_soft_delete_fetch_statement_targets_the_requested_event(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Pinned SQL contract: the event lookup filters Event.id == event_id exactly.

        Kills soft_delete_event mutmut_7 (== -> !=) and pins the where/select/
        execute-shape family (mutmut_2/_3/_5/_9) invisible to the
        statement-blind execute mock.
        """
        event = self._mock_event(event_id=123)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert "WHERE events.id = 123" in sql
        assert "!=" not in sql
        assert "WHERE NULL" not in sql.upper()

    @pytest.mark.asyncio
    async def test_soft_delete_alert_count_statement_filters_by_event_id(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Cascade branch must count alerts for THIS event (Alert.event_id == event_id).

        Kills soft_delete_event mutmut_22 (== -> !=); alert_count is otherwise
        log-only so no existing test inspects the statement.
        """
        event = self._mock_event(event_id=123)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        assert mock_db_session.execute.call_count == 2  # event fetch, then alert count
        alert_stmt = mock_db_session.execute.call_args_list[1].args[0]
        sql = " ".join(str(alert_stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert sql.startswith("SELECT")
        assert "WHERE alerts.event_id = 123" in sql
        assert "!=" not in sql
        # select(None) renders 'SELECT NULL AS anon_1 FROM alerts ...' — pin the
        # real alerts.* projection (kills soft_19/_20/_21/_24 shape family)
        assert "alerts.id" in sql
        assert "NULL AS" not in sql.upper()

    @pytest.mark.asyncio
    async def test_restore_fetch_statement_targets_the_requested_event(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Restore lookup must filter Event.id == event_id exactly.

        Kills restore_event mutmut_14 (== -> !=), invisible to the
        statement-blind execute mock (mirrors the soft-delete pin).
        """
        event = self._mock_event(event_id=123, deleted=True)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.restore_event(event_id=123, db=mock_db_session, cascade=True)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert "WHERE events.id = 123" in sql
        assert "!=" not in sql
        assert "WHERE NULL" not in sql.upper()

    @pytest.mark.asyncio
    async def test_hard_delete_fetch_statement_eagerly_loads_and_filters(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Hard-delete lookup: selectinload(detections) + exact id predicate.

        Kills hard_delete_event mutmut_6 (== -> !=) and the statement-shape
        family hard_1/_2/_4/_8 (whole-stmt/where/select/execute -> None).
        """
        event = self._mock_event(event_id=123)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.hard_delete_event(event_id=123, db=mock_db_session)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        assert len(stmt._with_options) == 1  # selectinload(Event.detections)
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert "FROM events" in sql
        assert "WHERE events.id = 123" in sql
        assert "!=" not in sql
        assert "WHERE NULL" not in sql.upper()

    @pytest.mark.asyncio
    async def test_restore_event_fetch_eagerly_loads_detections_and_deferred_columns(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Restore fetch must eagerly load detections, reasoning and llm_prompt.

        Kills restore_event mutmut_7 (selectinload removed: _with_options 3->2),
        _8 (undefer reasoning: column drops from SELECT list), _9 (undefer
        llm_prompt) and re-kills _10/_2/_3 via the statement capture.
        """
        event = self._mock_event(event_id=123, deleted=True)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.restore_event(event_id=123, db=mock_db_session, cascade=True)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        # loader options are opaque Load objects that do not affect SQL text —
        # pin the count (original: selectinload + 2 undefer = 3).
        assert len(stmt._with_options) == 3
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert "events.reasoning" in sql
        assert "events.llm_prompt" in sql

    @pytest.mark.asyncio
    async def test_soft_delete_default_cascade_schedules_file_deletion(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """cascade defaults to True: omitting it must still schedule file deletion.

        Kills soft_delete_event mutmut_1 (keyword default True -> False).
        """
        event = self._mock_event(event_id=123, clip_path="/path/to/clip.mp4")
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.soft_delete_event(event_id=123, db=mock_db_session)  # cascade omitted

        mock_file_service.schedule_deletion.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_without_cascade_skips_file_deletion_cancel(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """restore_event(cascade=False) leaves scheduled deletions untouched.

        Kills restore_event mutmut_24 (`cascade and deleted_at is not None`
        -> `or`, which made non-cascade restores cancel pending deletions).
        """
        event = self._mock_event(event_id=123, deleted=True)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.restore_event(event_id=123, db=mock_db_session, cascade=False)

        assert event.deleted_at is None
        mock_file_service.cancel_deletion_by_event_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_restore_default_cascade_cancels_pending_file_deletions(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """cascade defaults to True: omitting it must still cancel deletions.

        Kills restore_event mutmut_1 (keyword default True -> False).
        """
        event = self._mock_event(event_id=123, deleted=True)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        await service.restore_event(event_id=123, db=mock_db_session)  # cascade omitted

        mock_file_service.cancel_deletion_by_event_id.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_soft_delete_stamps_utc_aware_deleted_at(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """deleted_at must be timezone-aware (UTC): naive timestamps break
        retention comparisons downstream.

        Kills soft_delete_event mutmut_13 (datetime.now(UTC) -> now(None));
        existing tests only assert `is not None`.
        """
        event = self._mock_event(event_id=123)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService(file_service=mock_file_service)
        result = await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        assert result.deleted_at is not None
        assert result.deleted_at.tzinfo is not None, "deleted_at must be timezone-aware"
        assert result.deleted_at.utcoffset() == timedelta(0)
