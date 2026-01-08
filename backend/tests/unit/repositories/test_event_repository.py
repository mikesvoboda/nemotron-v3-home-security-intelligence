"""Tests for EventRepository event-specific operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.event import Event
from backend.repositories.event_repository import EventRepository


class TestEventRepository:
    """Test suite for EventRepository operations."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def event_repository(self, mock_session: AsyncMock) -> EventRepository:
        """Create an event repository instance."""
        return EventRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_by_id_with_camera_returns_event_with_camera(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test get_by_id_with_camera returns event with camera loaded."""
        event = Event(
            id=1, batch_id="batch_123", camera_id="front_door", started_at=datetime.now(UTC)
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_session.execute.return_value = mock_result

        result = await event_repository.get_by_id_with_camera(1)

        assert result == event

    @pytest.mark.asyncio
    async def test_get_by_id_with_camera_returns_none_when_not_found(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test get_by_id_with_camera returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await event_repository.get_by_id_with_camera(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_camera_id_returns_events(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_camera_id returns events for camera."""
        events = [
            Event(id=1, batch_id="b1", camera_id="cam1", started_at=datetime.now(UTC)),
            Event(id=2, batch_id="b2", camera_id="cam1", started_at=datetime.now(UTC)),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result

        result = await event_repository.find_by_camera_id("cam1")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_find_by_risk_level_returns_matching_events(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_risk_level returns events with matching risk level."""
        events = [
            Event(
                id=1,
                batch_id="b1",
                camera_id="cam1",
                started_at=datetime.now(UTC),
                risk_level="high",
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result

        result = await event_repository.find_by_risk_level("high")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_unreviewed_returns_unreviewed_events(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_unreviewed returns only unreviewed events."""
        events = [
            Event(
                id=1, batch_id="b1", camera_id="cam1", started_at=datetime.now(UTC), reviewed=False
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result

        result = await event_repository.find_unreviewed()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_by_batch_id_returns_events(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_batch_id returns events with matching batch ID."""
        events = [Event(id=1, batch_id="batch_123", camera_id="cam1", started_at=datetime.now(UTC))]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result

        result = await event_repository.find_by_batch_id("batch_123")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_by_time_range_returns_events_in_range(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_time_range returns events within time range."""
        now = datetime.now(UTC)
        events = [Event(id=1, batch_id="b1", camera_id="cam1", started_at=now)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)

        result = await event_repository.find_by_time_range(start_time, end_time)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_high_risk_returns_high_score_events(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_high_risk returns events with high risk scores."""
        events = [
            Event(
                id=1, batch_id="b1", camera_id="cam1", started_at=datetime.now(UTC), risk_score=85
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result

        result = await event_repository.find_high_risk(min_score=70)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_mark_reviewed_returns_true_when_updated(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test mark_reviewed returns True when event is updated."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        result = await event_repository.mark_reviewed(1)

        assert result is True
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_reviewed_with_notes(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test mark_reviewed includes notes when provided."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        result = await event_repository.mark_reviewed(1, notes="Reviewed")

        assert result is True

    @pytest.mark.asyncio
    async def test_mark_reviewed_returns_false_when_not_found(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test mark_reviewed returns False when event not found."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        result = await event_repository.mark_reviewed(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_count_unreviewed_returns_count(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test count_unreviewed returns number of unreviewed events."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 15
        mock_session.execute.return_value = mock_result

        result = await event_repository.count_unreviewed()

        assert result == 15

    @pytest.mark.asyncio
    async def test_count_by_camera_returns_count(
        self, event_repository: EventRepository, mock_session: AsyncMock
    ) -> None:
        """Test count_by_camera returns event count for camera."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result

        result = await event_repository.count_by_camera("front_door")

        assert result == 42
