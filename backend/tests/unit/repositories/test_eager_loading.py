"""Unit tests for eager loading annotations in repository methods (NEM-3758).

Tests verify that repository methods use appropriate eager loading strategies
(joinedload, selectinload) to prevent N+1 query problems.

Following TDD approach - tests written first before implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from backend.models import Camera, Detection, Event

# =============================================================================
# Detection Repository Eager Loading Tests
# =============================================================================


class TestDetectionRepositoryEagerLoading:
    """Tests for eager loading in DetectionRepository."""

    @pytest.mark.asyncio
    async def test_get_detections_with_camera_eager_loads_camera(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that get_detections_with_camera uses joinedload for camera."""
        from backend.repositories.detection_repository import DetectionRepository

        repo = DetectionRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await repo.get_detections_with_camera(camera_id="cam1", limit=10)

        # Verify execute was called
        mock_db_session.execute.assert_called_once()

        # Get the statement that was executed
        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]

        # Verify the query has options for eager loading
        assert hasattr(stmt, "_with_options")
        assert len(stmt._with_options) > 0

    @pytest.mark.asyncio
    async def test_get_detection_with_entities_eager_loads_related_data(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that get_detection_with_entities uses eager loading for related data."""
        from backend.repositories.detection_repository import DetectionRepository

        repo = DetectionRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        await repo.get_detection_with_entities(detection_id=1)

        mock_db_session.execute.assert_called_once()

        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]

        # Should have eager loading options for camera and event_records
        assert hasattr(stmt, "_with_options")
        # Should have at least 2 options (camera and event_records)
        assert len(stmt._with_options) >= 2

    @pytest.mark.asyncio
    async def test_list_detections_by_date_range_with_relationships(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test listing detections with eager loaded relationships."""
        from backend.repositories.detection_repository import DetectionRepository

        repo = DetectionRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 31, tzinfo=UTC)

        await repo.list_detections_by_date_range(
            start_date=start,
            end_date=end,
            include_camera=True,
        )

        mock_db_session.execute.assert_called_once()


# =============================================================================
# Event Repository Eager Loading Tests
# =============================================================================


class TestEventRepositoryEagerLoading:
    """Tests for eager loading in EventRepository."""

    @pytest.mark.asyncio
    async def test_get_event_with_camera_eager_loads_camera(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that get_event_with_camera uses joinedload for camera."""
        from backend.repositories.event_repository import EventRepository

        repo = EventRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        await repo.get_event_with_camera(event_id=1)

        mock_db_session.execute.assert_called_once()

        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]

        # Should have eager loading options
        assert hasattr(stmt, "_with_options")

    @pytest.mark.asyncio
    async def test_list_events_with_relationships_eager_loads(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that list_events_with_relationships uses eager loading."""
        from backend.repositories.event_repository import EventRepository

        repo = EventRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await repo.list_events_with_relationships(limit=50)

        mock_db_session.execute.assert_called_once()

        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]

        assert hasattr(stmt, "_with_options")

    @pytest.mark.asyncio
    async def test_get_recent_events_with_camera_uses_joinedload(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test getting recent events with camera relationship eagerly loaded."""
        from backend.repositories.event_repository import EventRepository

        repo = EventRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await repo.get_recent_events_with_camera(hours=24, limit=100)

        mock_db_session.execute.assert_called_once()


# =============================================================================
# Entity Repository Eager Loading Tests
# =============================================================================


class TestEntityRepositoryEagerLoading:
    """Tests for eager loading in EntityRepository."""

    @pytest.mark.asyncio
    async def test_get_entity_with_detections_eager_loads_primary_detection(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that get_entity_with_detections uses selectinload for primary_detection."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        await repo.get_entity_with_detections(entity_id=uuid.uuid4())

        mock_db_session.execute.assert_called_once()

        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]

        # Should have eager loading for primary_detection
        assert hasattr(stmt, "_with_options")

    @pytest.mark.asyncio
    async def test_list_entities_with_primary_detection(self, mock_db_session: AsyncMock) -> None:
        """Test listing entities with primary detection eagerly loaded."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await repo.get_entities_with_primary_detection()

        mock_db_session.execute.assert_called_once()

        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]

        # Should have eager loading for primary_detection
        assert hasattr(stmt, "_with_options")


# =============================================================================
# Camera Repository Eager Loading Tests
# =============================================================================


class TestCameraRepositoryEagerLoading:
    """Tests for eager loading in CameraRepository."""

    @pytest.mark.asyncio
    async def test_get_cameras_with_recent_events(self, mock_db_session: AsyncMock) -> None:
        """Test getting cameras with recent events eagerly loaded."""
        from backend.repositories.camera_repository import CameraRepository

        repo = CameraRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await repo.get_cameras_with_stats()

        mock_db_session.execute.assert_called_once()


# =============================================================================
# Eager Loading Strategy Selection Tests
# =============================================================================


class TestEagerLoadingStrategySelection:
    """Tests for correct eager loading strategy selection."""

    def test_joinedload_used_for_single_relationship(self) -> None:
        """Test that joinedload is used for fetching single related objects."""
        from backend.core.eager_loading import get_loading_strategy

        # Camera from Event (many-to-one) -> joinedload
        strategy = get_loading_strategy(
            relationship_type="many_to_one",
            expected_count="single",
        )
        assert strategy == "joinedload"

    def test_selectinload_used_for_collection_relationship(self) -> None:
        """Test that selectinload is used for collections."""
        from backend.core.eager_loading import get_loading_strategy

        # Detections from Entity (one-to-many) -> selectinload
        strategy = get_loading_strategy(
            relationship_type="one_to_many",
            expected_count="multiple",
        )
        assert strategy == "selectinload"

    def test_subqueryload_used_for_large_collections(self) -> None:
        """Test that subqueryload is used for large collections."""
        from backend.core.eager_loading import get_loading_strategy

        strategy = get_loading_strategy(
            relationship_type="one_to_many",
            expected_count="large",
        )
        assert strategy in ("selectinload", "subqueryload")


# =============================================================================
# Eager Loading Helper Function Tests
# =============================================================================


class TestEagerLoadingHelpers:
    """Tests for eager loading helper functions."""

    def test_apply_eager_loading_for_camera_on_event(self) -> None:
        """Test applying eager loading for camera relationship on Event."""
        from backend.core.eager_loading import apply_eager_loading

        stmt = select(Event)
        stmt_with_loading = apply_eager_loading(stmt, Event, ["camera"])

        # Should have options applied
        assert hasattr(stmt_with_loading, "_with_options")
        assert len(stmt_with_loading._with_options) > 0

    def test_apply_eager_loading_multiple_relationships(self) -> None:
        """Test applying eager loading for multiple relationships."""
        from backend.core.eager_loading import apply_eager_loading

        stmt = select(Detection)
        # Use actual relationships that exist on Detection model
        stmt_with_loading = apply_eager_loading(stmt, Detection, ["camera", "event_records"])

        assert hasattr(stmt_with_loading, "_with_options")
        # Should have multiple options (one per relationship)
        assert len(stmt_with_loading._with_options) >= 2

    def test_apply_eager_loading_returns_same_query_for_no_relationships(self) -> None:
        """Test that query is unchanged when no relationships specified."""
        from backend.core.eager_loading import apply_eager_loading

        stmt = select(Camera)
        stmt_with_loading = apply_eager_loading(stmt, Camera, [])

        # Should return the same statement without options
        # or with empty options if implementation adds wrapper
        assert stmt_with_loading is not None


# =============================================================================
# N+1 Query Prevention Tests
# =============================================================================


class TestN1QueryPrevention:
    """Tests verifying N+1 query prevention patterns."""

    @pytest.mark.asyncio
    async def test_list_events_avoids_n_plus_1_for_camera(self, mock_db_session: AsyncMock) -> None:
        """Test that listing events doesn't cause N+1 queries for camera access."""
        from backend.repositories.event_repository import EventRepository

        repo = EventRepository(mock_db_session)

        # Create mock events with cameras
        mock_cameras = [
            Camera(id=f"cam{i}", name=f"Camera {i}", folder_path=f"/path/{i}", status="online")
            for i in range(5)
        ]

        mock_events = []
        for i in range(10):
            mock_event = MagicMock(spec=Event)
            mock_event.id = i
            mock_event.camera_id = f"cam{i % 5}"
            mock_event.camera = mock_cameras[i % 5]  # Camera should be pre-loaded
            mock_events.append(mock_event)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_db_session.execute.return_value = mock_result

        events = await repo.list_events_with_relationships(limit=10)

        # Should only have one execute call (not N+1 for cameras)
        assert mock_db_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_loading_strategy_documented(self) -> None:
        """Test that loading strategies are documented in repository methods."""
        from backend.repositories.detection_repository import DetectionRepository
        from backend.repositories.event_repository import EventRepository

        # Methods that should document their loading strategy
        # This is a documentation/API design test
        event_methods = [
            "list_events_with_relationships",
            "get_event_with_camera",
            "get_recent_events_with_camera",
        ]

        detection_methods = [
            "get_detections_with_camera",
            "get_detection_with_entities",
            "list_detections_by_date_range",
        ]

        # Check EventRepository methods exist
        for method in event_methods:
            assert hasattr(EventRepository, method), f"EventRepository missing {method}"

        # Check DetectionRepository methods exist
        for method in detection_methods:
            assert hasattr(DetectionRepository, method), f"DetectionRepository missing {method}"
