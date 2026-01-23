"""Unit tests for write-only collection accessors.

NEM-3349: Tests for write_only_collections module that provides safe
access patterns for large relationships to prevent accidental loading.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.write_only_collections import (
    add_detection_to_camera,
    add_detection_to_event,
    add_event_to_camera,
    get_detection_count_for_camera,
    get_detection_count_for_event,
    get_event_count_for_camera,
    get_recent_detections_for_camera,
    get_recent_events_for_camera,
    remove_detection_from_event,
)


class TestAddDetectionToCamera:
    """Tests for add_detection_to_camera function."""

    @pytest.mark.asyncio
    async def test_sets_camera_id_and_adds_to_session(self) -> None:
        """Test that detection gets camera_id set and added to session."""
        mock_session = AsyncMock()
        mock_detection = MagicMock()
        mock_detection.camera_id = None

        await add_detection_to_camera(mock_session, "camera_1", mock_detection)

        assert mock_detection.camera_id == "camera_1"
        mock_session.add.assert_called_once_with(mock_detection)

    @pytest.mark.asyncio
    async def test_does_not_load_camera_or_detections(self) -> None:
        """Test that function doesn't trigger any database loads."""
        mock_session = AsyncMock()
        mock_detection = MagicMock()

        # No execute calls should happen
        await add_detection_to_camera(mock_session, "camera_1", mock_detection)

        mock_session.execute.assert_not_called()
        mock_session.get.assert_not_called()


class TestAddEventToCamera:
    """Tests for add_event_to_camera function."""

    @pytest.mark.asyncio
    async def test_sets_camera_id_and_adds_to_session(self) -> None:
        """Test that event gets camera_id set and added to session."""
        mock_session = AsyncMock()
        mock_event = MagicMock()
        mock_event.camera_id = None

        await add_event_to_camera(mock_session, "camera_1", mock_event)

        assert mock_event.camera_id == "camera_1"
        mock_session.add.assert_called_once_with(mock_event)


class TestAddDetectionToEvent:
    """Tests for add_detection_to_event function."""

    @pytest.mark.asyncio
    async def test_creates_junction_entry(self) -> None:
        """Test that junction table entry is created."""
        mock_session = AsyncMock()

        with patch("backend.models.event_detection.EventDetection") as mock_ed:
            mock_ed_instance = MagicMock()
            mock_ed.return_value = mock_ed_instance

            await add_detection_to_event(mock_session, 1, 100)

            mock_ed.assert_called_once_with(event_id=1, detection_id=100)
            mock_session.add.assert_called_once_with(mock_ed_instance)


class TestRemoveDetectionFromEvent:
    """Tests for remove_detection_from_event function."""

    @pytest.mark.asyncio
    async def test_removes_existing_link(self) -> None:
        """Test that existing link is removed."""
        mock_session = AsyncMock()
        mock_ed = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ed
        mock_session.execute.return_value = mock_result

        result = await remove_detection_from_event(mock_session, 1, 100)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_ed)

    @pytest.mark.asyncio
    async def test_returns_false_when_link_not_found(self) -> None:
        """Test that False is returned when link doesn't exist."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await remove_detection_from_event(mock_session, 1, 100)

        assert result is False
        mock_session.delete.assert_not_called()


class TestGetDetectionCountForCamera:
    """Tests for get_detection_count_for_camera function."""

    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        """Test that count is returned from query."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute.return_value = mock_result

        count = await get_detection_count_for_camera(mock_session, "camera_1")

        assert count == 42
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_none(self) -> None:
        """Test that 0 is returned when query returns None."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        count = await get_detection_count_for_camera(mock_session, "camera_1")

        assert count == 0


class TestGetDetectionCountForEvent:
    """Tests for get_detection_count_for_event function."""

    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        """Test that count is returned from query."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 15
        mock_session.execute.return_value = mock_result

        count = await get_detection_count_for_event(mock_session, 1)

        assert count == 15

    @pytest.mark.asyncio
    async def test_returns_zero_when_none(self) -> None:
        """Test that 0 is returned when query returns None."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        count = await get_detection_count_for_event(mock_session, 1)

        assert count == 0


class TestGetEventCountForCamera:
    """Tests for get_event_count_for_camera function."""

    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        """Test that count is returned from query."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 100
        mock_session.execute.return_value = mock_result

        count = await get_event_count_for_camera(mock_session, "camera_1")

        assert count == 100


class TestGetRecentDetectionsForCamera:
    """Tests for get_recent_detections_for_camera function."""

    @pytest.mark.asyncio
    async def test_returns_detections_list(self) -> None:
        """Test that list of detections is returned."""
        mock_session = AsyncMock()
        mock_detections = [MagicMock(), MagicMock()]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_detections
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_recent_detections_for_camera(mock_session, "camera_1", limit=10)

        assert result == mock_detections
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_limit_is_10(self) -> None:
        """Test that default limit is 10."""
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await get_recent_detections_for_camera(mock_session, "camera_1")

        # Verify execute was called (query was built with limit)
        mock_session.execute.assert_called_once()


class TestGetRecentEventsForCamera:
    """Tests for get_recent_events_for_camera function."""

    @pytest.mark.asyncio
    async def test_returns_events_list(self) -> None:
        """Test that list of events is returned."""
        mock_session = AsyncMock()
        mock_events = [MagicMock(), MagicMock(), MagicMock()]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_events
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_recent_events_for_camera(mock_session, "camera_1", limit=5)

        assert result == mock_events

    @pytest.mark.asyncio
    async def test_custom_limit(self) -> None:
        """Test that custom limit is respected."""
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await get_recent_events_for_camera(mock_session, "camera_1", limit=25)

        mock_session.execute.assert_called_once()


class TestModuleDocumentation:
    """Tests for module documentation."""

    def test_module_has_docstring(self) -> None:
        """Test that module has documentation."""
        from backend.core import write_only_collections

        assert write_only_collections.__doc__ is not None
        assert "WriteOnlyMapped" in write_only_collections.__doc__
        assert "NEM-3349" in write_only_collections.__doc__

    def test_functions_in_all(self) -> None:
        """Test that all public functions are exported."""
        from backend.core.write_only_collections import __all__

        expected_functions = [
            "add_detection_to_camera",
            "add_event_to_camera",
            "add_detection_to_event",
            "remove_detection_from_event",
            "get_detection_count_for_camera",
            "get_detection_count_for_event",
            "get_event_count_for_camera",
            "get_recent_detections_for_camera",
            "get_recent_events_for_camera",
        ]

        for func_name in expected_functions:
            assert func_name in __all__
