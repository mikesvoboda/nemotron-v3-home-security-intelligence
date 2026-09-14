"""Unit tests for event clustering endpoint (NEM-3620).

Tests the GET /api/events/clusters endpoint that groups events by temporal proximity.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.events import get_event_clusters
from backend.api.schemas.event_cluster import (
    ClusterEventSummary,
    ClusterRiskLevels,
    EventCluster,
    EventClustersResponse,
)
from backend.models.event import Event


def create_mock_event(
    event_id: int,
    camera_id: str,
    started_at: datetime,
    risk_score: int | None = 50,
    risk_level: str | None = "medium",
    summary: str | None = "Test event",
    object_types: str | None = "person",
) -> Mock:
    """Create a mock Event object for testing."""
    mock = Mock(spec=Event)
    mock.id = event_id
    mock.camera_id = camera_id
    mock.started_at = started_at
    mock.risk_score = risk_score
    mock.risk_level = risk_level
    mock.summary = summary
    mock.object_types = object_types
    mock.deleted_at = None
    return mock


class TestEventClustersSchemas:
    """Tests for event clustering Pydantic schemas."""

    def test_cluster_risk_levels_defaults(self):
        """Test ClusterRiskLevels initializes with zeros."""
        risk_levels = ClusterRiskLevels()
        assert risk_levels.critical == 0
        assert risk_levels.high == 0
        assert risk_levels.medium == 0
        assert risk_levels.low == 0

    def test_cluster_risk_levels_with_values(self):
        """Test ClusterRiskLevels with custom values."""
        risk_levels = ClusterRiskLevels(critical=1, high=2, medium=3, low=4)
        assert risk_levels.critical == 1
        assert risk_levels.high == 2
        assert risk_levels.medium == 3
        assert risk_levels.low == 4

    def test_cluster_event_summary(self):
        """Test ClusterEventSummary schema."""
        now = datetime.now(UTC)
        summary = ClusterEventSummary(
            id=1,
            camera_id="front_door",
            started_at=now,
            risk_score=75,
            risk_level="high",
            summary="Person at door",
        )
        assert summary.id == 1
        assert summary.camera_id == "front_door"
        assert summary.risk_score == 75
        assert summary.risk_level == "high"

    def test_cluster_event_summary_optional_fields(self):
        """Test ClusterEventSummary with optional fields as None."""
        now = datetime.now(UTC)
        summary = ClusterEventSummary(
            id=1,
            camera_id="front_door",
            started_at=now,
        )
        assert summary.risk_score is None
        assert summary.risk_level is None
        assert summary.summary is None

    def test_event_cluster_schema(self):
        """Test EventCluster schema."""
        now = datetime.now(UTC)
        cluster = EventCluster(
            cluster_id="test-uuid",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            event_count=3,
            cameras=["front_door", "back_door"],
            risk_levels=ClusterRiskLevels(high=2, medium=1),
            object_types={"person": 2, "vehicle": 1},
            events=[
                ClusterEventSummary(id=1, camera_id="front_door", started_at=now),
            ],
        )
        assert cluster.event_count == 3
        assert "front_door" in cluster.cameras
        assert cluster.risk_levels.high == 2
        assert cluster.object_types["person"] == 2

    def test_event_cluster_auto_generates_id(self):
        """Test EventCluster generates UUID if not provided."""
        now = datetime.now(UTC)
        cluster = EventCluster(
            start_time=now,
            end_time=now,
            event_count=1,
            cameras=["cam1"],
            risk_levels=ClusterRiskLevels(),
            events=[],
        )
        assert cluster.cluster_id is not None
        assert len(cluster.cluster_id) == 36  # UUID format

    def test_event_clusters_response(self):
        """Test EventClustersResponse schema."""
        response = EventClustersResponse(
            clusters=[],
            total_clusters=0,
            unclustered_events=5,
        )
        assert response.total_clusters == 0
        assert response.unclustered_events == 5


class TestGetEventClustersEndpoint:
    """Tests for GET /api/events/clusters endpoint."""

    @pytest.mark.asyncio
    async def test_clusters_validates_date_range(self):
        """Test that invalid date range raises HTTPException."""
        mock_db = AsyncMock(spec=AsyncSession)

        # start_date after end_date should raise
        with pytest.raises(HTTPException) as exc_info:
            await get_event_clusters(
                start_date=datetime(2026, 1, 25, 12, 0, 0, tzinfo=UTC),
                end_date=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
                camera_id=None,
                time_window_minutes=5,
                min_cluster_size=2,
                db=mock_db,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_clusters_empty_result(self):
        """Test that empty event list returns empty clusters."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock the execute to return empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        assert response.total_clusters == 0
        assert response.unclustered_events == 0
        assert len(response.clusters) == 0

    @pytest.mark.asyncio
    async def test_clusters_single_event_unclustered(self):
        """Test that single events are counted as unclustered."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Create a single event
        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time),
        ]

        # Mock the execute
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        # Single event doesn't meet min_cluster_size=2
        assert response.total_clusters == 0
        assert response.unclustered_events == 1

    @pytest.mark.asyncio
    async def test_clusters_same_camera_within_window(self):
        """Test events from same camera within window are clustered together."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Create events within 5 minute window from same camera
        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time, risk_level="high"),
            create_mock_event(
                2, "front_door", base_time + timedelta(minutes=2), risk_level="medium"
            ),
            create_mock_event(3, "front_door", base_time + timedelta(minutes=4), risk_level="low"),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        assert response.total_clusters == 1
        assert response.unclustered_events == 0
        assert len(response.clusters) == 1

        cluster = response.clusters[0]
        assert cluster.event_count == 3
        assert "front_door" in cluster.cameras
        assert len(cluster.cameras) == 1
        assert cluster.risk_levels.high == 1
        assert cluster.risk_levels.medium == 1
        assert cluster.risk_levels.low == 1

    @pytest.mark.asyncio
    async def test_clusters_same_camera_outside_window(self):
        """Test events from same camera outside window create separate clusters."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Create events with 10 minute gap (outside 5 min window)
        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time),
            create_mock_event(2, "front_door", base_time + timedelta(minutes=1)),
            create_mock_event(3, "front_door", base_time + timedelta(minutes=15)),
            create_mock_event(4, "front_door", base_time + timedelta(minutes=16)),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        # Should have 2 clusters (first 2 events, then events 3-4)
        assert response.total_clusters == 2
        assert response.unclustered_events == 0
        assert len(response.clusters) == 2

    @pytest.mark.asyncio
    async def test_clusters_cross_camera_correlation(self):
        """Test events from different cameras within 2 min are clustered."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Events from different cameras within 2 minute window
        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time),
            create_mock_event(2, "back_door", base_time + timedelta(minutes=1)),
            create_mock_event(3, "side_door", base_time + timedelta(seconds=90)),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        # All events should be in one cluster due to cross-camera correlation
        assert response.total_clusters == 1
        assert response.unclustered_events == 0

        cluster = response.clusters[0]
        assert cluster.event_count == 3
        assert set(cluster.cameras) == {"front_door", "back_door", "side_door"}

    @pytest.mark.asyncio
    async def test_clusters_object_types_aggregation(self):
        """Test that object types are properly aggregated in clusters."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time, object_types="person"),
            create_mock_event(
                2, "front_door", base_time + timedelta(minutes=1), object_types="vehicle"
            ),
            create_mock_event(
                3, "front_door", base_time + timedelta(minutes=2), object_types="person,vehicle"
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        cluster = response.clusters[0]
        assert cluster.object_types["person"] == 2
        assert cluster.object_types["vehicle"] == 2

    @pytest.mark.asyncio
    async def test_clusters_respects_min_cluster_size(self):
        """Test that min_cluster_size parameter is respected."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            # First group: 2 events (meets default min_cluster_size=2)
            create_mock_event(1, "front_door", base_time),
            create_mock_event(2, "front_door", base_time + timedelta(minutes=1)),
            # Second group: 4 events
            create_mock_event(3, "back_door", base_time + timedelta(minutes=20)),
            create_mock_event(4, "back_door", base_time + timedelta(minutes=21)),
            create_mock_event(5, "back_door", base_time + timedelta(minutes=22)),
            create_mock_event(6, "back_door", base_time + timedelta(minutes=23)),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # With min_cluster_size=3, first group (2 events) doesn't qualify
        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=3,
            db=mock_db,
        )

        assert response.total_clusters == 1  # Only second group qualifies
        assert response.unclustered_events == 2  # First group's events

    @pytest.mark.asyncio
    async def test_clusters_custom_time_window(self):
        """Test custom time window parameter."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time),
            create_mock_event(2, "front_door", base_time + timedelta(minutes=8)),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # With 10-minute window, events 8 minutes apart should cluster
        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=10,
            min_cluster_size=2,
            db=mock_db,
        )

        assert response.total_clusters == 1
        assert response.clusters[0].event_count == 2

    @pytest.mark.asyncio
    async def test_clusters_events_without_risk_level(self):
        """Test handling events with null risk_level."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time, risk_level=None),
            create_mock_event(2, "front_door", base_time + timedelta(minutes=1), risk_level="high"),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        cluster = response.clusters[0]
        # Only one event has risk_level="high", null should not be counted
        assert cluster.risk_levels.high == 1
        assert cluster.risk_levels.critical == 0
        assert cluster.risk_levels.medium == 0
        assert cluster.risk_levels.low == 0

    @pytest.mark.asyncio
    async def test_clusters_events_without_object_types(self):
        """Test handling events with null object_types."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time, object_types=None),
            create_mock_event(
                2, "front_door", base_time + timedelta(minutes=1), object_types="person"
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        cluster = response.clusters[0]
        assert cluster.object_types.get("person", 0) == 1

    @pytest.mark.asyncio
    async def test_clusters_event_summaries_included(self):
        """Test that event summaries are included in cluster response."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "front_door", base_time, summary="First event"),
            create_mock_event(
                2, "front_door", base_time + timedelta(minutes=1), summary="Second event"
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        cluster = response.clusters[0]
        assert len(cluster.events) == 2
        assert cluster.events[0].id == 1
        assert cluster.events[0].summary == "First event"
        assert cluster.events[1].id == 2
        assert cluster.events[1].summary == "Second event"

    @pytest.mark.asyncio
    async def test_clusters_time_range_boundaries(self):
        """Test cluster start_time and end_time are set correctly."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        end_time = base_time + timedelta(minutes=4)
        events = [
            create_mock_event(1, "front_door", base_time),
            create_mock_event(2, "front_door", base_time + timedelta(minutes=2)),
            create_mock_event(3, "front_door", end_time),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        cluster = response.clusters[0]
        assert cluster.start_time == base_time
        assert cluster.end_time == end_time

    @pytest.mark.asyncio
    async def test_clusters_camera_filter(self):
        """Test camera_id filter is applied to query."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id="front_door",
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        # Verify execute was called (query was built)
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_clusters_cameras_sorted_alphabetically(self):
        """Test that camera list in cluster is sorted alphabetically."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        events = [
            create_mock_event(1, "zebra_cam", base_time),
            create_mock_event(2, "alpha_cam", base_time + timedelta(seconds=30)),
            create_mock_event(3, "mike_cam", base_time + timedelta(seconds=60)),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        response = await get_event_clusters(
            start_date=datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 1, 25, 23, 59, 59, tzinfo=UTC),
            camera_id=None,
            time_window_minutes=5,
            min_cluster_size=2,
            db=mock_db,
        )

        cluster = response.clusters[0]
        assert cluster.cameras == ["alpha_cam", "mike_cam", "zebra_cam"]
