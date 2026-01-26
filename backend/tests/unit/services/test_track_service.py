"""Unit tests for TrackService.

Tests the track service's trajectory management, metrics calculation,
and CRUD operations using mocked dependencies.

Run with: uv run pytest backend/tests/unit/services/test_track_service.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.track import MovementMetrics, TrackHistoryResponse, TrackListResponse
from backend.services.track_service import (
    DEFAULT_MAX_TRAJECTORY_POINTS,
    DEFAULT_TRACK_RETENTION_HOURS,
    TrackService,
    configure_track_service,
    get_track_service,
    reset_track_service,
)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_track():
    """Create a mock track object."""
    track = MagicMock()
    track.id = 1
    track.track_id = 42
    track.camera_id = "front_door"
    track.object_class = "person"
    track.first_seen = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
    track.last_seen = datetime(2026, 1, 26, 12, 0, 27, tzinfo=UTC)
    track.trajectory = [
        {"x": 100.0, "y": 200.0, "timestamp": "2026-01-26T12:00:00+00:00"},
        {"x": 150.5, "y": 220.3, "timestamp": "2026-01-26T12:00:05+00:00"},
        {"x": 210.2, "y": 245.8, "timestamp": "2026-01-26T12:00:10+00:00"},
    ]
    track.total_distance = 125.5
    track.avg_speed = 12.55
    track.reid_embedding = None
    return track


@pytest.fixture
def sample_trajectory():
    """Create a sample trajectory for testing."""
    return [
        {"x": 100.0, "y": 200.0, "timestamp": "2026-01-26T12:00:00+00:00"},
        {"x": 150.0, "y": 250.0, "timestamp": "2026-01-26T12:00:05+00:00"},
        {"x": 200.0, "y": 300.0, "timestamp": "2026-01-26T12:00:10+00:00"},
    ]


class TestTrackServiceInit:
    """Test TrackService initialization."""

    def test_init_with_defaults(self, mock_session):
        """Test initialization with default values."""
        service = TrackService(mock_session)

        assert service.db == mock_session
        assert service.max_trajectory_points == DEFAULT_MAX_TRAJECTORY_POINTS
        assert service.track_retention_hours == DEFAULT_TRACK_RETENTION_HOURS

    def test_init_with_custom_values(self, mock_session):
        """Test initialization with custom configuration."""
        service = TrackService(
            mock_session,
            max_trajectory_points=200,
            track_retention_hours=48,
        )

        assert service.max_trajectory_points == 200
        assert service.track_retention_hours == 48


class TestCalculateMetrics:
    """Test the calculate_metrics static method."""

    def test_empty_trajectory_returns_zeros(self):
        """Test that empty trajectory returns zero metrics."""
        metrics = TrackService.calculate_metrics([])

        assert metrics.total_distance == 0.0
        assert metrics.avg_speed == 0.0
        assert metrics.direction is None
        assert metrics.duration_seconds == 0.0

    def test_single_point_returns_zeros(self):
        """Test that single point trajectory returns zero metrics."""
        trajectory = [{"x": 100.0, "y": 200.0, "timestamp": "2026-01-26T12:00:00+00:00"}]
        metrics = TrackService.calculate_metrics(trajectory)

        assert metrics.total_distance == 0.0
        assert metrics.avg_speed == 0.0
        assert metrics.direction is None
        assert metrics.duration_seconds == 0.0

    def test_two_points_calculates_distance(self, sample_trajectory):
        """Test distance calculation with two points."""
        # Use first two points: (100, 200) -> (150, 250)
        # Distance = sqrt(50^2 + 50^2) = sqrt(5000) = 70.71
        trajectory = sample_trajectory[:2]
        metrics = TrackService.calculate_metrics(trajectory)

        assert metrics.total_distance == pytest.approx(70.71, rel=0.01)
        assert metrics.duration_seconds == 5.0

    def test_calculates_average_speed(self, sample_trajectory):
        """Test average speed calculation."""
        # Full trajectory: 10 seconds, ~141.42 pixels total
        metrics = TrackService.calculate_metrics(sample_trajectory)

        # avg_speed = total_distance / duration
        expected_speed = metrics.total_distance / 10.0
        assert metrics.avg_speed == pytest.approx(expected_speed, rel=0.01)

    def test_calculates_direction_right(self):
        """Test direction calculation for rightward movement."""
        trajectory = [
            {"x": 0.0, "y": 0.0, "timestamp": "2026-01-26T12:00:00+00:00"},
            {"x": 100.0, "y": 0.0, "timestamp": "2026-01-26T12:00:10+00:00"},
        ]
        metrics = TrackService.calculate_metrics(trajectory)

        # Moving right = 0 degrees
        assert metrics.direction == pytest.approx(0.0, abs=0.1)

    def test_calculates_direction_down(self):
        """Test direction calculation for downward movement."""
        trajectory = [
            {"x": 0.0, "y": 0.0, "timestamp": "2026-01-26T12:00:00+00:00"},
            {"x": 0.0, "y": 100.0, "timestamp": "2026-01-26T12:00:10+00:00"},
        ]
        metrics = TrackService.calculate_metrics(trajectory)

        # Moving down = 90 degrees
        assert metrics.direction == pytest.approx(90.0, abs=0.1)

    def test_calculates_direction_diagonal(self, sample_trajectory):
        """Test direction calculation for diagonal movement."""
        metrics = TrackService.calculate_metrics(sample_trajectory)

        # Movement from (100, 200) to (200, 300) = 45 degrees diagonal
        assert metrics.direction == pytest.approx(45.0, abs=0.1)

    def test_calculates_direction_left(self):
        """Test direction calculation for leftward movement."""
        trajectory = [
            {"x": 100.0, "y": 0.0, "timestamp": "2026-01-26T12:00:00+00:00"},
            {"x": 0.0, "y": 0.0, "timestamp": "2026-01-26T12:00:10+00:00"},
        ]
        metrics = TrackService.calculate_metrics(trajectory)

        # Moving left = 180 degrees
        assert metrics.direction == pytest.approx(180.0, abs=0.1)

    def test_calculates_direction_up(self):
        """Test direction calculation for upward movement."""
        trajectory = [
            {"x": 0.0, "y": 100.0, "timestamp": "2026-01-26T12:00:00+00:00"},
            {"x": 0.0, "y": 0.0, "timestamp": "2026-01-26T12:00:10+00:00"},
        ]
        metrics = TrackService.calculate_metrics(trajectory)

        # Moving up = 270 degrees
        assert metrics.direction == pytest.approx(270.0, abs=0.1)

    def test_handles_datetime_objects(self):
        """Test that datetime objects work as timestamps."""
        trajectory = [
            {"x": 0.0, "y": 0.0, "timestamp": datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)},
            {"x": 100.0, "y": 0.0, "timestamp": datetime(2026, 1, 26, 12, 0, 10, tzinfo=UTC)},
        ]
        metrics = TrackService.calculate_metrics(trajectory)

        assert metrics.total_distance == 100.0
        assert metrics.duration_seconds == 10.0

    def test_total_distance_sums_segments(self):
        """Test that total distance is sum of all segment distances."""
        # L-shaped path: right then down
        trajectory = [
            {"x": 0.0, "y": 0.0, "timestamp": "2026-01-26T12:00:00+00:00"},
            {"x": 100.0, "y": 0.0, "timestamp": "2026-01-26T12:00:05+00:00"},
            {"x": 100.0, "y": 100.0, "timestamp": "2026-01-26T12:00:10+00:00"},
        ]
        metrics = TrackService.calculate_metrics(trajectory)

        # Total: 100 (right) + 100 (down) = 200
        assert metrics.total_distance == pytest.approx(200.0, rel=0.01)


class TestCreateOrUpdateTrack:
    """Test create_or_update_track method."""

    @pytest.mark.asyncio
    async def test_creates_new_track_when_not_exists(self, mock_session):
        """Test that a new track is created when none exists."""
        service = TrackService(mock_session)
        timestamp = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)

        # Mock no existing track
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await service.create_or_update_track(
            track_id=42,
            camera_id="front_door",
            object_class="person",
            position=(640.5, 480.2),
            timestamp=timestamp,
        )

        # Verify track was added
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called()
        mock_session.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_updates_existing_track_with_new_position(self, mock_session, mock_track):
        """Test that existing track is updated with new position."""
        service = TrackService(mock_session)
        new_timestamp = datetime(2026, 1, 26, 12, 0, 30, tzinfo=UTC)

        # Mock existing track found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        original_trajectory_len = len(mock_track.trajectory)

        await service.create_or_update_track(
            track_id=42,
            camera_id="front_door",
            object_class="person",
            position=(300.0, 400.0),
            timestamp=new_timestamp,
        )

        # Verify trajectory was updated (appended)
        assert len(mock_track.trajectory) == original_trajectory_len + 1
        assert mock_track.last_seen == new_timestamp
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_prunes_trajectory_when_exceeds_limit(self, mock_session):
        """Test that trajectory is pruned when it exceeds max points."""
        service = TrackService(mock_session, max_trajectory_points=3)
        timestamp = datetime(2026, 1, 26, 12, 0, 30, tzinfo=UTC)

        # Create mock track with trajectory at limit
        mock_track = MagicMock()
        mock_track.trajectory = [
            {"x": 100.0, "y": 100.0, "timestamp": "2026-01-26T12:00:00+00:00"},
            {"x": 150.0, "y": 150.0, "timestamp": "2026-01-26T12:00:05+00:00"},
            {"x": 200.0, "y": 200.0, "timestamp": "2026-01-26T12:00:10+00:00"},
        ]
        mock_track.last_seen = datetime(2026, 1, 26, 12, 0, 10, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        await service.create_or_update_track(
            track_id=42,
            camera_id="front_door",
            object_class="person",
            position=(250.0, 250.0),
            timestamp=timestamp,
        )

        # Should still be at max (3), not 4
        assert len(mock_track.trajectory) == 3
        # Oldest point should have been pruned, newest added
        assert mock_track.trajectory[-1]["x"] == 250.0

    @pytest.mark.asyncio
    async def test_updates_reid_embedding_if_provided(self, mock_session, mock_track):
        """Test that re-id embedding is updated when provided."""
        service = TrackService(mock_session)
        timestamp = datetime(2026, 1, 26, 12, 0, 30, tzinfo=UTC)
        embedding = b"\x00\x01\x02\x03"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        await service.create_or_update_track(
            track_id=42,
            camera_id="front_door",
            object_class="person",
            position=(300.0, 400.0),
            timestamp=timestamp,
            reid_embedding=embedding,
        )

        assert mock_track.reid_embedding == embedding


class TestGetTrack:
    """Test get_track method."""

    @pytest.mark.asyncio
    async def test_returns_track_when_found(self, mock_session, mock_track):
        """Test that track is returned when found."""
        service = TrackService(mock_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        result = await service.get_track(track_id=42, camera_id="front_door")

        assert result == mock_track

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session):
        """Test that None is returned when track not found."""
        service = TrackService(mock_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_track(track_id=999, camera_id="front_door")

        assert result is None


class TestGetTrackHistory:
    """Test get_track_history method."""

    @pytest.mark.asyncio
    async def test_returns_history_response_when_found(self, mock_session, mock_track):
        """Test that TrackHistoryResponse is returned when track found."""
        service = TrackService(mock_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_track
        mock_session.execute.return_value = mock_result

        result = await service.get_track_history(track_id=42, camera_id="front_door")

        assert result is not None
        assert isinstance(result, TrackHistoryResponse)
        assert result.track_id == 42
        assert result.camera_id == "front_door"
        assert len(result.trajectory) == len(mock_track.trajectory)
        assert isinstance(result.metrics, MovementMetrics)

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session):
        """Test that None is returned when track not found."""
        service = TrackService(mock_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_track_history(track_id=999, camera_id="front_door")

        assert result is None


class TestGetTracksByCamera:
    """Test get_tracks_by_camera method."""

    @pytest.mark.asyncio
    async def test_returns_paginated_response(self, mock_session, mock_track):
        """Test that paginated TrackListResponse is returned."""
        service = TrackService(mock_session)

        # Mock count query result
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        # Mock tracks query result
        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = [mock_track]

        mock_session.execute.side_effect = [count_result, tracks_result]

        result = await service.get_tracks_by_camera(
            camera_id="front_door",
            page=1,
            page_size=50,
        )

        assert isinstance(result, TrackListResponse)
        assert result.total == 1
        assert result.page == 1
        assert result.page_size == 50
        assert len(result.tracks) == 1

    @pytest.mark.asyncio
    async def test_applies_time_filters(self, mock_session):
        """Test that time filters are applied to query."""
        service = TrackService(mock_session)
        start_time = datetime(2026, 1, 26, 11, 0, 0, tzinfo=UTC)
        end_time = datetime(2026, 1, 26, 13, 0, 0, tzinfo=UTC)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, tracks_result]

        await service.get_tracks_by_camera(
            camera_id="front_door",
            start_time=start_time,
            end_time=end_time,
        )

        # Verify execute was called with filters
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_applies_object_class_filter(self, mock_session):
        """Test that object_class filter is applied."""
        service = TrackService(mock_session)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, tracks_result]

        await service.get_tracks_by_camera(
            camera_id="front_door",
            object_class="person",
        )

        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_validates_pagination_parameters(self, mock_session):
        """Test that invalid pagination parameters are corrected."""
        service = TrackService(mock_session)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        tracks_result = MagicMock()
        tracks_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, tracks_result]

        # Invalid page and page_size
        result = await service.get_tracks_by_camera(
            camera_id="front_door",
            page=-1,
            page_size=2000,
        )

        # Should be corrected to valid values
        assert result.page == 1  # Minimum 1
        assert result.page_size == 1000  # Maximum 1000


class TestPruneOldTracks:
    """Test prune_old_tracks method."""

    @pytest.mark.asyncio
    async def test_deletes_old_tracks(self, mock_session):
        """Test that old tracks are deleted."""
        service = TrackService(mock_session, track_retention_hours=24)

        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        deleted_count = await service.prune_old_tracks()

        assert deleted_count == 5
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_custom_retention_hours(self, mock_session):
        """Test that custom retention_hours is used."""
        service = TrackService(mock_session, track_retention_hours=24)

        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        deleted_count = await service.prune_old_tracks(retention_hours=48)

        assert deleted_count == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_tracks_deleted(self, mock_session):
        """Test that 0 is returned when no tracks are deleted."""
        service = TrackService(mock_session)

        mock_result = MagicMock()
        mock_result.rowcount = None
        mock_session.execute.return_value = mock_result

        deleted_count = await service.prune_old_tracks()

        assert deleted_count == 0


class TestFactoryFunctions:
    """Test factory and configuration functions."""

    def test_get_track_service_returns_instance(self, mock_session):
        """Test that get_track_service returns a TrackService instance."""
        service = get_track_service(mock_session)

        assert isinstance(service, TrackService)
        assert service.db == mock_session

    def test_configure_track_service_updates_defaults(self, mock_session):
        """Test that configure_track_service updates default values."""
        reset_track_service()

        configure_track_service(
            max_trajectory_points=200,
            track_retention_hours=48,
        )

        service = get_track_service(mock_session)

        assert service.max_trajectory_points == 200
        assert service.track_retention_hours == 48

        # Clean up
        reset_track_service()

    def test_reset_track_service_restores_defaults(self, mock_session):
        """Test that reset_track_service restores default values."""
        configure_track_service(
            max_trajectory_points=200,
            track_retention_hours=48,
        )

        reset_track_service()

        service = get_track_service(mock_session)

        assert service.max_trajectory_points == DEFAULT_MAX_TRAJECTORY_POINTS
        assert service.track_retention_hours == DEFAULT_TRACK_RETENTION_HOURS
