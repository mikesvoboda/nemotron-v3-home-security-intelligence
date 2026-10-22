"""Tests for EventService soft delete, alert dismissal, and restore (B4.4 / 4n-trash.md)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.alert import AlertStatusEnum
from backend.services.event_service import EventService, get_event_service, reset_event_service

pytestmark = pytest.mark.unit


class TestEventServiceSoftDeleteAndAlerts:
    """Tests for soft_delete_event and alert dismissal when all covered events are in Trash."""

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
        deleted: bool = False,
    ) -> MagicMock:
        """Create a mock Event object."""
        event = MagicMock()
        event.id = event_id
        event.clip_path = clip_path
        event.is_deleted = deleted
        event.deleted_at = datetime.now(UTC) if deleted else None
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
    async def test_soft_delete_sets_deleted_at_without_deleting_files(
        self, mock_db_session: MagicMock
    ) -> None:
        """Soft delete sets deleted_at and does not schedule or delete files (4n-trash.md)."""
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

        ev_result = MagicMock()
        ev_result.scalar_one_or_none.return_value = event
        alert_result = MagicMock()
        alert_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.side_effect = [ev_result, alert_result]

        service = EventService()
        result = await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        assert event.deleted_at is not None
        assert result == event
        mock_db_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_soft_delete_dismisses_alert_when_all_events_in_trash(
        self, mock_db_session: MagicMock
    ) -> None:
        """An alert whose covered events are all in Trash is dismissed with reason."""
        event = self._create_mock_event(event_id=10)
        ev_result = MagicMock()
        ev_result.scalar_one_or_none.return_value = event

        alert = MagicMock()
        alert.id = "alert-1"
        alert.event_id = 10
        alert.last_event_id = 10
        alert.status = AlertStatusEnum.OPEN
        alert.alert_metadata = {"existing": True}
        ae1 = MagicMock()
        ae1.event_id = 10
        alert.alert_events = [ae1]

        alert_result = MagicMock()
        alert_result.scalars.return_value.all.return_value = [alert]
        mock_db_session.execute.side_effect = [ev_result, alert_result]

        service = EventService()
        await service.soft_delete_event(event_id=10, db=mock_db_session, cascade=True)

        assert alert.status == AlertStatusEnum.DISMISSED
        assert alert.alert_metadata == {
            "existing": True,
            "dismissed_reason": "events moved to Trash",
        }

    @pytest.mark.asyncio
    async def test_soft_delete_keeps_alert_open_when_folded_event_still_live(
        self, mock_db_session: MagicMock
    ) -> None:
        """An alert covering two events stays open when only one is moved to Trash."""
        event = self._create_mock_event(event_id=10)
        ev_result = MagicMock()
        ev_result.scalar_one_or_none.return_value = event

        alert = MagicMock()
        alert.id = "alert-2"
        alert.event_id = 10
        alert.last_event_id = 11
        alert.status = AlertStatusEnum.OPEN
        alert.alert_metadata = None
        ae1 = MagicMock(event_id=10)
        ae2 = MagicMock(event_id=11)
        alert.alert_events = [ae1, ae2]

        alert_result = MagicMock()
        alert_result.scalars.return_value.all.return_value = [alert]

        live_other_result = MagicMock()
        live_other_result.scalar_one_or_none.return_value = 11

        mock_db_session.execute.side_effect = [
            ev_result,
            alert_result,
            live_other_result,
        ]

        service = EventService()
        await service.soft_delete_event(event_id=10, db=mock_db_session, cascade=True)

        assert alert.status == AlertStatusEnum.OPEN
        assert alert.alert_metadata is None

    @pytest.mark.asyncio
    async def test_soft_delete_not_found_and_already_deleted(
        self, mock_db_session: MagicMock
    ) -> None:
        service = EventService()

        missing_res = MagicMock()
        missing_res.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = missing_res
        with pytest.raises(ValueError, match="Event not found: 404"):
            await service.soft_delete_event(event_id=404, db=mock_db_session)

        already = self._create_mock_event(event_id=409, deleted=True)
        already_res = MagicMock()
        already_res.scalar_one_or_none.return_value = already
        mock_db_session.execute.return_value = already_res
        with pytest.raises(ValueError, match="Event already deleted: 409"):
            await service.soft_delete_event(event_id=409, db=mock_db_session)


class TestEventServiceRestore:
    """Tests for restore_event."""

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_restore_clears_deleted_at(self, mock_db_session: MagicMock) -> None:
        event = MagicMock()
        event.id = 123
        event.is_deleted = True
        event.deleted_at = datetime.now(UTC)
        event.detections = [MagicMock()]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService()
        restored = await service.restore_event(event_id=123, db=mock_db_session, cascade=True)

        assert restored is event
        assert event.deleted_at is None
        mock_db_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_restore_not_found_and_not_deleted(self, mock_db_session: MagicMock) -> None:
        service = EventService()

        missing = MagicMock()
        missing.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = missing
        with pytest.raises(ValueError, match="Event not found: 404"):
            await service.restore_event(event_id=404, db=mock_db_session)

        live = MagicMock()
        live.id = 12
        live.is_deleted = False
        live.deleted_at = None
        live_res = MagicMock()
        live_res.scalar_one_or_none.return_value = live
        mock_db_session.execute.return_value = live_res
        with pytest.raises(ValueError, match="Event is not deleted: 12"):
            await service.restore_event(event_id=12, db=mock_db_session)


class TestEventServiceCollectFilePaths:
    """Tests for _collect_file_paths helper method."""

    def test_collect_all_file_paths(self) -> None:
        event = MagicMock()
        event.clip_path = "/path/to/clip.mp4"

        detection1 = MagicMock()
        detection1.file_path = "/path/to/det1.jpg"
        detection1.thumbnail_path = "/path/to/thumb1.jpg"

        detection2 = MagicMock()
        detection2.file_path = "/path/to/det2.jpg"
        detection2.thumbnail_path = None

        event.detections = [detection1, detection2]

        service = EventService()
        paths = service._collect_file_paths(event)

        assert paths == [
            "/path/to/clip.mp4",
            "/path/to/det1.jpg",
            "/path/to/thumb1.jpg",
            "/path/to/det2.jpg",
        ]

    def test_collect_file_paths_no_clip(self) -> None:
        event = MagicMock()
        event.clip_path = None

        detection = MagicMock()
        detection.file_path = "/path/to/det.jpg"
        detection.thumbnail_path = "/path/to/thumb.jpg"
        event.detections = [detection]

        service = EventService()
        assert service._collect_file_paths(event) == [
            "/path/to/det.jpg",
            "/path/to/thumb.jpg",
        ]

    def test_collect_file_paths_empty(self) -> None:
        event = MagicMock()
        event.clip_path = None
        event.detections = []

        service = EventService()
        assert service._collect_file_paths(event) == []


class TestEventServiceSingleton:
    """Tests for EventService singleton pattern."""

    def test_get_event_service_returns_same_instance(self) -> None:
        reset_event_service()
        service1 = get_event_service()
        service2 = get_event_service()
        assert service1 is service2

    def test_reset_event_service_clears_instance(self) -> None:
        reset_event_service()
        service1 = get_event_service()
        reset_event_service()
        service2 = get_event_service()
        assert service1 is not service2


class TestWp44EventServiceDeleteGaps:
    """Statement-shape, cascade-default, and tz contracts."""

    @pytest.fixture
    def mock_db_session(self) -> MagicMock:
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    def _mock_event(
        self, event_id: int = 1, clip_path: str | None = None, deleted: bool = False
    ) -> MagicMock:
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
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    @pytest.mark.asyncio
    async def test_soft_delete_fetch_statement_targets_the_requested_event(
        self, mock_db_session: MagicMock
    ) -> None:
        event = self._mock_event(event_id=123)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService()
        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert "WHERE events.id = 123" in sql
        assert "!=" not in sql

    @pytest.mark.asyncio
    async def test_soft_delete_alert_lookup_statement_filters_by_event_id(
        self, mock_db_session: MagicMock
    ) -> None:
        event = self._mock_event(event_id=123)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService()
        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        assert mock_db_session.execute.call_count == 2
        alert_stmt = mock_db_session.execute.call_args_list[1].args[0]
        sql = " ".join(str(alert_stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert sql.startswith("SELECT")
        assert "alerts.event_id = 123" in sql
        assert "alerts.id" in sql

    @pytest.mark.asyncio
    async def test_restore_fetch_statement_targets_the_requested_event(
        self, mock_db_session: MagicMock
    ) -> None:
        event = self._mock_event(event_id=123, deleted=True)
        mock_db_session.execute.return_value = self._mock_result(event)

        service = EventService()
        await service.restore_event(event_id=123, db=mock_db_session, cascade=True)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        assert len(stmt._with_options) == 3
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert "WHERE events.id = 123" in sql
        assert "events.reasoning" in sql
        assert "events.llm_prompt" in sql

    @pytest.mark.asyncio
    async def test_soft_delete_stamps_utc_aware_deleted_at(
        self, mock_db_session: MagicMock
    ) -> None:
        event = self._mock_event(event_id=123)
        mock_db_session.execute.return_value = self._mock_result(event)

        before = datetime.now(UTC)
        service = EventService()
        await service.soft_delete_event(event_id=123, db=mock_db_session)
        after = datetime.now(UTC)

        assert event.deleted_at is not None
        assert event.deleted_at.tzinfo == UTC
        assert before - timedelta(seconds=1) <= event.deleted_at <= after + timedelta(seconds=1)

    @pytest.mark.asyncio
    async def test_get_event_and_get_deleted_event_predicates(
        self, mock_db_session: MagicMock
    ) -> None:
        event = self._mock_event(event_id=55)
        mock_db_session.execute.return_value = self._mock_result(event)
        service = EventService()

        await service.get_event(55, mock_db_session, include_deleted=False)
        stmt_live = mock_db_session.execute.call_args_list[-1].args[0]
        sql_live = " ".join(str(stmt_live.compile(compile_kwargs={"literal_binds": True})).split())
        assert "events.id = 55" in sql_live
        assert "events.deleted_at IS NULL" in sql_live

        await service.get_event(55, mock_db_session, include_deleted=True)
        stmt_all = mock_db_session.execute.call_args_list[-1].args[0]
        sql_all = " ".join(str(stmt_all.compile(compile_kwargs={"literal_binds": True})).split())
        assert "events.id = 55" in sql_all
        assert "deleted_at IS NULL" not in sql_all

        await service.get_deleted_event(55, mock_db_session)
        stmt_del = mock_db_session.execute.call_args_list[-1].args[0]
        sql_del = " ".join(str(stmt_del.compile(compile_kwargs={"literal_binds": True})).split())
        assert "events.id = 55" in sql_del
        assert "events.deleted_at IS NOT NULL" in sql_del
