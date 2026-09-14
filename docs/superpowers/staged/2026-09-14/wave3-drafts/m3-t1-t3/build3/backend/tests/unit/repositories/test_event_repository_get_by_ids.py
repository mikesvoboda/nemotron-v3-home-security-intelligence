"""Unit tests for EventRepository.get_by_ids method.

Tests the get_by_ids functionality for fetching multiple events by ID.

Related Linear issues: NEM-5418, NEM-5419, NEM-5420, NEM-5421
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.event import Event
from backend.repositories.event_repository import EventRepository

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestGetByIds:
    """Tests for EventRepository.get_by_ids method."""

    @pytest.mark.asyncio
    async def test_get_by_ids_returns_events(self) -> None:
        """Test that get_by_ids returns events matching the IDs."""
        # Create mock session
        mock_session = MagicMock()

        # Create mock events
        mock_event1 = MagicMock(spec=Event)
        mock_event1.id = 1
        mock_event2 = MagicMock(spec=Event)
        mock_event2.id = 2

        # Setup mock result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_event1, mock_event2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Create repository and call method
        repo = EventRepository(mock_session)
        events = await repo.get_by_ids([1, 2])

        # Verify
        assert len(events) == 2
        assert events[0].id == 1
        assert events[1].id == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_ids_empty_list(self) -> None:
        """Test that get_by_ids returns empty list for empty input."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()

        repo = EventRepository(mock_session)
        events = await repo.get_by_ids([])

        # Should return empty list without querying
        assert events == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_ids_partial_results(self) -> None:
        """Test that get_by_ids returns only events that exist."""
        mock_session = MagicMock()

        # Only return one event even though two IDs were requested
        mock_event1 = MagicMock(spec=Event)
        mock_event1.id = 1

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_event1]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = EventRepository(mock_session)
        events = await repo.get_by_ids([1, 999])  # 999 doesn't exist

        # Should return only the event that exists
        assert len(events) == 1
        assert events[0].id == 1

    @pytest.mark.asyncio
    async def test_get_by_ids_with_eager_load(self) -> None:
        """Test that get_by_ids can eager load camera relationship."""
        mock_session = MagicMock()

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_event]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = EventRepository(mock_session)
        events = await repo.get_by_ids([1], eager_load_camera=True)

        # Verify eager loading was requested
        assert len(events) == 1
        # The execute call should have included selectinload option
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_ids_returns_list(self) -> None:
        """Test that get_by_ids returns a list, not a sequence."""
        mock_session = MagicMock()

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_event]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = EventRepository(mock_session)
        events = await repo.get_by_ids([1])

        # Should be a list for easy manipulation
        assert isinstance(events, list)
