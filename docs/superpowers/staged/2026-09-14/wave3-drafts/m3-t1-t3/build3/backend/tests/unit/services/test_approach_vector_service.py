"""Unit tests for ApproachVectorService (NEM-4936).

Tests cover approach vector calculation functionality including:
- Position calculations
- Direction and speed calculations
- Distance to zone boundary
- ETA estimation
- Point-in-polygon detection
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.approach_vector_service import ApproachVectorService


class TestApproachVectorServiceHelpers:
    """Tests for ApproachVectorService helper methods."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_db = AsyncMock()
        self.service = ApproachVectorService(self.mock_db)

    def test_calculate_polygon_centroid_simple_square(self) -> None:
        """Test centroid calculation for a simple square."""
        polygon = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        centroid = self.service._calculate_polygon_centroid(polygon)
        assert centroid == (0.5, 0.5)

    def test_calculate_polygon_centroid_triangle(self) -> None:
        """Test centroid calculation for a triangle."""
        polygon = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
        centroid = self.service._calculate_polygon_centroid(polygon)
        assert abs(centroid[0] - 0.5) < 0.01
        assert abs(centroid[1] - 0.333) < 0.01

    def test_calculate_polygon_centroid_empty(self) -> None:
        """Test centroid calculation for empty polygon returns default."""
        centroid = self.service._calculate_polygon_centroid([])
        assert centroid == (0.5, 0.5)

    def test_point_in_polygon_inside(self) -> None:
        """Test point-in-polygon for point inside."""
        polygon = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        assert self.service._point_in_polygon(0.5, 0.5, polygon) is True

    def test_point_in_polygon_outside(self) -> None:
        """Test point-in-polygon for point outside."""
        polygon = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        assert self.service._point_in_polygon(2.0, 2.0, polygon) is False

    def test_point_in_polygon_on_edge(self) -> None:
        """Test point-in-polygon for point on edge."""
        polygon = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        # Points on edge may return True or False depending on algorithm
        # This test just ensures no exception is raised
        result = self.service._point_in_polygon(0.5, 0.0, polygon)
        assert isinstance(result, bool)

    def test_point_in_polygon_insufficient_vertices(self) -> None:
        """Test point-in-polygon with insufficient vertices returns False."""
        polygon = [(0.0, 0.0), (1.0, 0.0)]  # Only 2 points
        assert self.service._point_in_polygon(0.5, 0.0, polygon) is False

    def test_point_to_segment_distance_perpendicular(self) -> None:
        """Test distance from point perpendicular to segment."""
        # Horizontal segment from (0,0) to (1,0), point at (0.5, 0.5)
        dist = self.service._point_to_segment_distance(0.5, 0.5, 0.0, 0.0, 1.0, 0.0)
        assert abs(dist - 0.5) < 0.001

    def test_point_to_segment_distance_endpoint(self) -> None:
        """Test distance from point to segment endpoint."""
        # Point closer to endpoint than perpendicular projection
        dist = self.service._point_to_segment_distance(2.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        assert abs(dist - 1.0) < 0.001

    def test_point_to_segment_distance_degenerate(self) -> None:
        """Test distance for degenerate segment (single point)."""
        dist = self.service._point_to_segment_distance(1.0, 1.0, 0.0, 0.0, 0.0, 0.0)
        # Distance should be sqrt(2)
        assert abs(dist - 1.414) < 0.01

    def test_distance_to_polygon_boundary_inside(self) -> None:
        """Test distance to polygon boundary when inside returns 0."""
        polygon = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        dist = self.service._distance_to_polygon_boundary(0.5, 0.5, polygon)
        assert dist == 0.0

    def test_distance_to_polygon_boundary_outside(self) -> None:
        """Test distance to polygon boundary when outside."""
        polygon = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        dist = self.service._distance_to_polygon_boundary(1.5, 0.5, polygon)
        assert abs(dist - 0.5) < 0.01


class TestApproachVectorCalculation:
    """Tests for approach vector calculation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_db = AsyncMock()
        self.service = ApproachVectorService(self.mock_db)

    def test_calculate_approach_vector_approaching(self) -> None:
        """Test approach vector for entity approaching zone."""
        # Create mock detections moving toward zone
        now = datetime.now(UTC)
        detections = [
            self._create_detection(100, 100, now - timedelta(seconds=2)),
            self._create_detection(150, 150, now),
        ]

        # Zone at center of image
        polygon = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]

        vector = self.service._calculate_approach_vector(
            detections=detections,
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )

        assert vector is not None
        assert vector["is_approaching"] is True
        assert vector["speed_normalized"] > 0
        assert vector["direction_degrees"] >= 0
        assert vector["direction_degrees"] < 360

    def test_calculate_approach_vector_moving_away(self) -> None:
        """Test approach vector for entity moving away from zone."""
        now = datetime.now(UTC)
        # Moving from (500, 500) to (100, 100) - away from center zone
        detections = [
            self._create_detection(500, 500, now - timedelta(seconds=2)),
            self._create_detection(100, 100, now),
        ]

        # Zone at center
        polygon = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]

        vector = self.service._calculate_approach_vector(
            detections=detections,
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )

        assert vector is not None
        assert vector["is_approaching"] is False
        assert vector["estimated_arrival_seconds"] is None

    def test_calculate_approach_vector_insufficient_detections(self) -> None:
        """Test approach vector with insufficient detections returns None."""
        now = datetime.now(UTC)
        detections = [self._create_detection(100, 100, now)]

        polygon = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]

        vector = self.service._calculate_approach_vector(
            detections=detections,
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )

        assert vector is None

    def test_calculate_approach_vector_zero_time_delta(self) -> None:
        """Test approach vector with zero time delta returns None."""
        now = datetime.now(UTC)
        detections = [
            self._create_detection(100, 100, now),
            self._create_detection(150, 150, now),  # Same timestamp
        ]

        polygon = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]

        vector = self.service._calculate_approach_vector(
            detections=detections,
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )

        assert vector is None

    def test_calculate_approach_vector_eta_calculation(self) -> None:
        """Test that ETA is calculated correctly for approaching entity."""
        now = datetime.now(UTC)
        # Moving at consistent speed toward zone
        detections = [
            self._create_detection(200, 200, now - timedelta(seconds=1)),
            self._create_detection(400, 400, now),
        ]

        # Zone far from current position
        polygon = [(0.8, 0.8), (0.9, 0.8), (0.9, 0.9), (0.8, 0.9)]

        vector = self.service._calculate_approach_vector(
            detections=detections,
            normalized_polygon=polygon,
            image_width=1920,
            image_height=1080,
        )

        assert vector is not None
        if vector["is_approaching"]:
            assert vector["estimated_arrival_seconds"] is not None
            assert vector["estimated_arrival_seconds"] > 0

    def _create_detection(self, bbox_x: int, bbox_y: int, timestamp: datetime) -> MagicMock:
        """Create a mock detection object."""
        detection = MagicMock()
        detection.bbox_x = bbox_x
        detection.bbox_y = bbox_y
        detection.bbox_width = 100
        detection.bbox_height = 200
        detection.detected_at = timestamp
        detection.object_type = "person"
        detection.track_id = 1
        return detection


class TestGetNormalizedPosition:
    """Tests for _get_normalized_position method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_db = AsyncMock()
        self.service = ApproachVectorService(self.mock_db)

    def test_get_normalized_position_center(self) -> None:
        """Test normalized position for detection at center."""
        detection = MagicMock()
        detection.bbox_x = 910  # (960 - 50) center x
        detection.bbox_y = 490  # (540 - 50) center y
        detection.bbox_width = 100
        detection.bbox_height = 100

        pos = self.service._get_normalized_position(detection, 1920, 1080)

        assert pos is not None
        assert abs(pos[0] - 0.5) < 0.01  # ~center x
        assert abs(pos[1] - 0.5) < 0.01  # ~center y

    def test_get_normalized_position_corner(self) -> None:
        """Test normalized position for detection at corner."""
        detection = MagicMock()
        detection.bbox_x = 0
        detection.bbox_y = 0
        detection.bbox_width = 100
        detection.bbox_height = 100

        pos = self.service._get_normalized_position(detection, 1920, 1080)

        assert pos is not None
        assert pos[0] < 0.1  # Near left edge
        assert pos[1] < 0.1  # Near top edge

    def test_get_normalized_position_no_bbox(self) -> None:
        """Test normalized position returns None for detection without bbox."""
        detection = MagicMock()
        detection.bbox_x = None
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        pos = self.service._get_normalized_position(detection, 1920, 1080)

        assert pos is None


class TestGetZoneApproachVectors:
    """Integration tests for get_zone_approach_vectors."""

    @pytest.mark.asyncio
    async def test_get_zone_approach_vectors_zone_not_found(self) -> None:
        """Test approach vectors returns empty list when zone not found."""
        mock_db = AsyncMock()
        service = ApproachVectorService(mock_db)

        # Mock _get_zone to return None
        with patch.object(service, "_get_zone", return_value=None):
            vectors = await service.get_zone_approach_vectors(zone_id=999)

        assert vectors == []

    @pytest.mark.asyncio
    async def test_get_zone_approach_vectors_invalid_polygon(self) -> None:
        """Test approach vectors returns empty list for invalid polygon."""
        mock_db = AsyncMock()
        service = ApproachVectorService(mock_db)

        mock_zone = MagicMock()
        mock_zone.polygon = [[0, 0]]  # Only 1 point - invalid
        mock_zone.camera_id = "test_camera"

        with patch.object(service, "_get_zone", return_value=mock_zone):
            vectors = await service.get_zone_approach_vectors(zone_id=1)

        assert vectors == []

    @pytest.mark.asyncio
    async def test_get_zone_approach_vectors_no_detections(self) -> None:
        """Test approach vectors returns empty list when no recent detections."""
        mock_db = AsyncMock()
        service = ApproachVectorService(mock_db)

        mock_zone = MagicMock()
        mock_zone.polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        mock_zone.camera_id = "test_camera"

        with (
            patch.object(service, "_get_zone", return_value=mock_zone),
            patch.object(service, "_get_active_dweller_track_ids", return_value=set()),
            patch.object(service, "_get_recent_detections", return_value=[]),
        ):
            vectors = await service.get_zone_approach_vectors(zone_id=1)

        assert vectors == []

    @pytest.mark.asyncio
    async def test_get_zone_approach_vectors_excludes_active_dwellers(self) -> None:
        """Test that entities already in zone are excluded."""
        mock_db = AsyncMock()
        service = ApproachVectorService(mock_db)

        mock_zone = MagicMock()
        mock_zone.polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        mock_zone.camera_id = "test_camera"

        now = datetime.now(UTC)
        # Detection with track_id=42 which is in zone
        detection = MagicMock()
        detection.track_id = 42
        detection.bbox_x = 50
        detection.bbox_y = 50
        detection.bbox_width = 10
        detection.bbox_height = 10
        detection.detected_at = now
        detection.object_type = "person"

        with (
            patch.object(service, "_get_zone", return_value=mock_zone),
            patch.object(
                service, "_get_active_dweller_track_ids", return_value={42}
            ),  # track 42 is in zone
            patch.object(service, "_get_recent_detections", return_value=[detection]),
        ):
            vectors = await service.get_zone_approach_vectors(zone_id=1)

        # Detection should be excluded because track_id 42 is in active_dwellers
        # _get_recent_detections should have excluded it, so vectors should be empty
        assert vectors == []
