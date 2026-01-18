"""Unit tests for events API eager loading optimization (NEM-1619).

Tests verify that the list_events endpoint uses joinedload to prevent N+1 queries
when accessing the camera relationship.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.responses import Response

from backend.models.camera import Camera
from backend.models.event import Event


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock Response object for deprecation header tests."""
    return MagicMock(spec=Response)


class TestListEventsEagerLoading:
    """Tests for list_events endpoint using joinedload for camera relationship."""

    @pytest.mark.asyncio
    async def test_list_events_uses_joinedload(self, mock_response: MagicMock):
        """Verify list_events uses joinedload to prevent N+1 for camera relationship.

        RED: This test should fail before adding joinedload to the query.
        GREEN: This test should pass after adding joinedload(Event.camera).
        """
        from backend.api.routes.events import list_events

        # Create mock camera
        mock_camera = Camera(id="cam1", name="Front Door", folder_path="/test", status="online")

        # Create mock events with camera relationship
        mock_events = []
        for i in range(3):
            mock_event = MagicMock(spec=Event)
            mock_event.id = i + 1
            mock_event.camera_id = "cam1"
            mock_event.camera = mock_camera  # Camera loaded via joinedload
            mock_event.batch_id = f"batch-{i + 1}"
            mock_event.started_at = datetime(2025, 12, 23, 12, i, 0, tzinfo=UTC)
            mock_event.ended_at = datetime(2025, 12, 23, 12, i + 1, 30, tzinfo=UTC)
            mock_event.risk_score = 50 + i * 10
            mock_event.risk_level = "medium"
            mock_event.summary = f"Test event {i + 1}"
            mock_event.reasoning = "Test reasoning"
            mock_event.detection_id_list = [1, 2, 3]
            mock_event.reviewed = False
            mock_event.object_types = "person,vehicle"
            mock_events.append(mock_event)

        # Create mock DB session
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock the execute calls
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_events_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_events
        mock_events_result.scalars.return_value = mock_scalars

        # Setup execute to return count first, then events
        mock_db.execute.side_effect = [mock_count_result, mock_events_result]

        # Call the function
        result = await list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            object_type=None,
            limit=50,
            offset=0,
            cursor=None,
            fields=None,
            db=mock_db,
        )

        # Verify the function executed successfully
        assert result is not None
        assert hasattr(result, "items")
        assert len(result.items) == 3

        # Verify that execute was called (for count and events queries)
        assert mock_db.execute.call_count == 2

        # Verify the query includes joinedload by inspecting the SQL statement
        # The second call is the events query
        events_query_call = mock_db.execute.call_args_list[1]
        query_statement = events_query_call[0][0]

        # Check that the query has options (joinedload) applied
        # This verifies eager loading is configured
        assert hasattr(query_statement, "_with_options")
        options = query_statement._with_options
        assert len(options) > 0

        # Verify it's a joinedload for the camera relationship
        option = options[0]
        assert isinstance(option, type(joinedload(Event.camera)))

    @pytest.mark.asyncio
    async def test_list_events_with_cursor_uses_joinedload(self, mock_response: MagicMock):
        """Verify list_events uses joinedload even with cursor-based pagination.

        Cursor-based pagination should still apply eager loading for the camera relationship.
        """
        from backend.api.pagination import CursorData, encode_cursor
        from backend.api.routes.events import list_events

        # Create cursor for pagination
        cursor_data = CursorData(id=10, created_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC))
        cursor = encode_cursor(cursor_data)

        # Create mock camera
        mock_camera = Camera(id="cam1", name="Front Door", folder_path="/test", status="online")

        # Create mock event
        mock_event = MagicMock(spec=Event)
        mock_event.id = 11
        mock_event.camera_id = "cam1"
        mock_event.camera = mock_camera
        mock_event.batch_id = "batch-11"
        mock_event.started_at = datetime(2025, 12, 23, 11, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 11, 1, 30, tzinfo=UTC)
        mock_event.risk_score = 60
        mock_event.risk_level = "medium"
        mock_event.summary = "Test event with cursor"
        mock_event.reasoning = "Test reasoning"
        mock_event.detection_id_list = [1, 2, 3]
        mock_event.reviewed = False
        mock_event.object_types = "person"

        # Create mock DB session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_event]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Call with cursor
        result = await list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            object_type=None,
            limit=50,
            offset=0,
            cursor=cursor,
            fields=None,
            db=mock_db,
        )

        # Verify the function executed successfully
        assert result is not None
        assert hasattr(result, "items")
        assert len(result.items) == 1

        # Verify query was executed
        assert mock_db.execute.call_count == 1

        # Verify the query includes joinedload
        query_call = mock_db.execute.call_args_list[0]
        query_statement = query_call[0][0]
        assert hasattr(query_statement, "_with_options")
        options = query_statement._with_options
        assert len(options) > 0

    @pytest.mark.asyncio
    async def test_list_events_with_filters_uses_joinedload(self, mock_response: MagicMock):
        """Verify list_events uses joinedload with various filters applied.

        Filters should not affect eager loading optimization.
        """
        from backend.api.routes.events import list_events

        # Create mock camera
        mock_camera = Camera(id="cam1", name="Front Door", folder_path="/test", status="online")

        # Create mock event matching filters
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"
        mock_event.camera = mock_camera
        mock_event.batch_id = "batch-1"
        mock_event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 12, 1, 30, tzinfo=UTC)
        mock_event.risk_score = 80
        mock_event.risk_level = "high"
        mock_event.summary = "High risk event"
        mock_event.reasoning = "Test reasoning"
        mock_event.detection_id_list = [1, 2, 3]
        mock_event.reviewed = False
        mock_event.object_types = "person"

        # Create mock DB session
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock count and events queries
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_events_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_event]
        mock_events_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_events_result]

        # Call with multiple filters
        result = await list_events(
            response=mock_response,
            camera_id="cam1",
            risk_level="high",
            start_date=datetime(2025, 12, 23, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2025, 12, 24, 0, 0, 0, tzinfo=UTC),
            reviewed=False,
            object_type="person",
            limit=50,
            offset=0,
            cursor=None,
            fields=None,
            db=mock_db,
        )

        # Verify the function executed successfully
        assert result is not None
        assert hasattr(result, "items")
        assert len(result.items) == 1

        # Verify queries were executed
        assert mock_db.execute.call_count == 2

        # Verify the events query includes joinedload
        events_query_call = mock_db.execute.call_args_list[1]
        query_statement = events_query_call[0][0]
        assert hasattr(query_statement, "_with_options")
        options = query_statement._with_options
        assert len(options) > 0

    @pytest.mark.asyncio
    async def test_list_events_camera_data_accessible(self, mock_response: MagicMock):
        """Verify that camera data is accessible in response without additional queries.

        This tests the functional aspect - that camera information is available
        in the loaded events without triggering lazy loading.
        """
        from backend.api.routes.events import list_events

        # Create mock camera
        mock_camera = Camera(id="cam1", name="Front Door", folder_path="/test", status="online")

        # Create mock event with camera relationship loaded
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"
        mock_event.camera = mock_camera  # Already loaded via joinedload
        mock_event.batch_id = "batch-1"
        mock_event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 12, 1, 30, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test event"
        mock_event.reasoning = "Test reasoning"
        mock_event.detection_id_list = [1, 2, 3]
        mock_event.reviewed = False
        mock_event.object_types = "person"

        # Create mock DB session
        mock_db = AsyncMock(spec=AsyncSession)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_events_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_event]
        mock_events_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_events_result]

        # Call the function
        result = await list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            object_type=None,
            limit=50,
            offset=0,
            cursor=None,
            fields=None,
            db=mock_db,
        )

        # Verify the response includes event data
        assert result is not None
        assert hasattr(result, "items")
        assert len(result.items) == 1

        # Verify camera_id is in the response
        event_data = result.items[0]
        assert event_data.camera_id == "cam1"

        # Verify no additional queries were made to load camera data
        # Only 2 queries should have been executed: count + events
        assert mock_db.execute.call_count == 2
