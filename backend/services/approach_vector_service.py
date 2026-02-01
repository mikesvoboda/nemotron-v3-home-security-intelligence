"""Service for calculating approach vectors for zone intelligence (NEM-4936).

This module provides the ApproachVectorService class for analyzing entity movement
trajectories relative to zones. It calculates:
- Whether entities are approaching zones
- Direction and speed of movement
- Estimated time of arrival (ETA) to zone boundaries
- Urgency classification based on ETA

The service uses recent detection history to compute movement vectors,
implementing approach vector calculations similar to zone_service.py.

Example:
    async with get_session() as session:
        service = ApproachVectorService(session)

        # Get approach vectors for a zone
        vectors = await service.get_zone_approach_vectors(zone_id=1)

        for v in vectors:
            if v["is_approaching"]:
                print(f"Track {v['track_id']} ETA: {v['estimated_arrival_seconds']}s")
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select

from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.analytics_zone import PolygonZone
from backend.models.detection import Detection
from backend.models.dwell_time import DwellTimeRecord

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Configuration constants
DETECTION_LOOKBACK_SECONDS = 10  # Look back 10 seconds for trajectory
MIN_DETECTIONS_FOR_VECTOR = 2  # Need at least 2 points to calculate movement
DEFAULT_IMAGE_WIDTH = 1920
DEFAULT_IMAGE_HEIGHT = 1080


class ApproachVectorService:
    """Service for calculating entity approach vectors to zones.

    This service analyzes entity movement trajectories to determine if they
    are approaching specific zones and estimates arrival times.

    It uses detection history to compute movement vectors and leverages
    the zone_service spatial heuristics for approach calculations.

    Attributes:
        db: The async database session for operations.

    Example:
        async with get_session() as session:
            service = ApproachVectorService(session)

            vectors = await service.get_zone_approach_vectors(zone_id=1)
            approaching = [v for v in vectors if v["is_approaching"]]
            print(f"{len(approaching)} entities approaching zone")
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the approach vector service.

        Args:
            db: An async SQLAlchemy session for database operations.
        """
        self.db = db

    async def get_zone_approach_vectors(
        self,
        zone_id: int,
        image_width: int = DEFAULT_IMAGE_WIDTH,
        image_height: int = DEFAULT_IMAGE_HEIGHT,
    ) -> list[dict[str, Any]]:
        """Calculate approach vectors for all entities near a zone.

        Analyzes recent detection history to determine which tracked entities
        are approaching the zone, their direction, speed, and ETA.

        Args:
            zone_id: ID of the polygon zone to analyze.
            image_width: Width of the camera image in pixels.
            image_height: Height of the camera image in pixels.

        Returns:
            List of approach vector dictionaries containing:
            - track_id: Tracking ID of the entity
            - object_class: Classification (person, vehicle, etc.)
            - is_approaching: Whether moving toward the zone
            - direction_degrees: Direction of movement (0-360)
            - speed_normalized: Speed in normalized units/second
            - distance_to_zone: Distance to zone boundary
            - estimated_arrival_seconds: ETA (or None if not approaching)
            - current_position: Current position {x, y}
            - zone_centroid: Zone centroid {x, y}
        """
        # Get the zone with its coordinates
        zone = await self._get_zone(zone_id)
        if zone is None:
            logger.warning(f"Zone {zone_id} not found for approach vector calculation")
            return []

        # Get the zone polygon (pixel coordinates) and convert to normalized
        polygon = zone.polygon
        if not polygon or len(polygon) < 3:
            logger.warning(f"Zone {zone_id} has no valid polygon coordinates")
            return []

        # Convert polygon to normalized coordinates
        normalized_polygon = [(p[0] / image_width, p[1] / image_height) for p in polygon]

        # Get the zone centroid (normalized) for visualization
        zone_centroid = self._calculate_polygon_centroid(normalized_polygon)

        # Get entities currently NOT in the zone but recently detected nearby
        # We use active dwellers to know who's IN the zone (exclude them)
        active_in_zone = await self._get_active_dweller_track_ids(zone_id)

        # Get recent detections for this camera
        camera_id = zone.camera_id
        recent_detections = await self._get_recent_detections(
            camera_id=camera_id,
            exclude_track_ids=active_in_zone,
        )

        # Group detections by track_id
        tracks: dict[int, list[Detection]] = {}
        for detection in recent_detections:
            if detection.track_id is not None:
                if detection.track_id not in tracks:
                    tracks[detection.track_id] = []
                tracks[detection.track_id].append(detection)

        # Calculate approach vector for each track
        approach_vectors: list[dict[str, Any]] = []

        for track_id, detections in tracks.items():
            # Sort by timestamp ascending
            detections.sort(key=lambda d: d.detected_at)

            # Need at least 2 detections to calculate movement
            if len(detections) < MIN_DETECTIONS_FOR_VECTOR:
                continue

            # Calculate approach vector using local implementation
            vector = self._calculate_approach_vector(
                detections=detections,
                normalized_polygon=normalized_polygon,
                image_width=image_width,
                image_height=image_height,
            )

            if vector is None:
                continue

            # Get current position from last detection
            last_detection = detections[-1]
            current_position = self._get_normalized_position(
                last_detection, image_width, image_height
            )

            if current_position is None:
                continue

            # Get object class from last detection
            object_class = last_detection.object_type or "unknown"

            approach_vectors.append(
                {
                    "track_id": track_id,
                    "object_class": object_class,
                    "is_approaching": vector["is_approaching"],
                    "direction_degrees": vector["direction_degrees"],
                    "speed_normalized": vector["speed_normalized"],
                    "distance_to_zone": vector["distance_to_zone"],
                    "estimated_arrival_seconds": vector.get("estimated_arrival_seconds"),
                    "current_position": {"x": current_position[0], "y": current_position[1]},
                    "zone_centroid": {"x": zone_centroid[0], "y": zone_centroid[1]},
                }
            )

        logger.debug(
            f"Calculated {len(approach_vectors)} approach vectors for zone {zone_id}",
            extra={
                "zone_id": zone_id,
                "total_tracks": len(tracks),
                "approaching": sum(1 for v in approach_vectors if v["is_approaching"]),
            },
        )

        return approach_vectors

    def _calculate_polygon_centroid(
        self, polygon: list[tuple[float, float]]
    ) -> tuple[float, float]:
        """Calculate centroid of a polygon.

        Args:
            polygon: List of (x, y) normalized coordinate tuples.

        Returns:
            Tuple of (centroid_x, centroid_y).
        """
        if not polygon:
            return (0.5, 0.5)  # Default to center

        sum_x = sum(p[0] for p in polygon)
        sum_y = sum(p[1] for p in polygon)
        n = len(polygon)
        return (sum_x / n, sum_y / n)

    def _calculate_approach_vector(
        self,
        detections: list[Detection],
        normalized_polygon: list[tuple[float, float]],
        image_width: int,
        image_height: int,
    ) -> dict[str, Any] | None:
        """Calculate approach vector for a track toward a zone.

        Args:
            detections: List of detections sorted by time ascending.
            normalized_polygon: Zone polygon in normalized coordinates.
            image_width: Image width in pixels.
            image_height: Image height in pixels.

        Returns:
            Dictionary with approach vector data, or None if calculation fails.
        """
        if len(detections) < 2:
            return None

        # Get first and last positions
        first_pos = self._get_normalized_position(detections[0], image_width, image_height)
        last_pos = self._get_normalized_position(detections[-1], image_width, image_height)

        if first_pos is None or last_pos is None:
            return None

        # Calculate time difference
        time_delta = (detections[-1].detected_at - detections[0].detected_at).total_seconds()
        if time_delta <= 0:
            return None

        # Calculate movement vector
        dx = last_pos[0] - first_pos[0]
        dy = last_pos[1] - first_pos[1]

        # Calculate distance moved
        distance_moved = math.sqrt(dx * dx + dy * dy)

        # Calculate speed (normalized units per second)
        speed = distance_moved / time_delta

        # Calculate direction (degrees, 0=up, 90=right, 180=down, 270=left)
        # Note: In image coordinates, y increases downward
        direction_rad = math.atan2(dx, -dy)  # -dy because y is inverted
        direction_deg = math.degrees(direction_rad)
        if direction_deg < 0:
            direction_deg += 360

        # Calculate distance to zone boundary
        current_distance = self._distance_to_polygon_boundary(
            last_pos[0], last_pos[1], normalized_polygon
        )

        # Calculate previous distance to zone
        first_distance = self._distance_to_polygon_boundary(
            first_pos[0], first_pos[1], normalized_polygon
        )

        # Determine if approaching
        is_approaching = current_distance < first_distance

        # Estimate arrival time if approaching
        estimated_arrival: float | None = None
        if is_approaching and speed > 0 and current_distance > 0:
            estimated_arrival = current_distance / speed
        elif current_distance == 0:
            # Already in zone
            estimated_arrival = 0.0

        return {
            "is_approaching": is_approaching,
            "direction_degrees": direction_deg,
            "speed_normalized": speed,
            "distance_to_zone": current_distance,
            "estimated_arrival_seconds": estimated_arrival,
        }

    def _distance_to_polygon_boundary(
        self, x: float, y: float, polygon: list[tuple[float, float]]
    ) -> float:
        """Calculate minimum distance from point to polygon boundary.

        Args:
            x: X coordinate of point (normalized).
            y: Y coordinate of point (normalized).
            polygon: List of (x, y) vertices.

        Returns:
            Minimum distance to polygon boundary, 0 if inside.
        """
        # Check if point is inside polygon using ray casting
        if self._point_in_polygon(x, y, polygon):
            return 0.0

        # Calculate distance to each edge
        min_distance = float("inf")
        n = len(polygon)

        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            dist = self._point_to_segment_distance(x, y, x1, y1, x2, y2)
            min_distance = min(min_distance, dist)

        return min_distance

    def _point_in_polygon(self, x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
        """Check if point is inside polygon using ray casting.

        Args:
            x: X coordinate of point.
            y: Y coordinate of point.
            polygon: List of (x, y) vertices.

        Returns:
            True if point is inside polygon.
        """
        if len(polygon) < 3:
            return False

        n = len(polygon)
        inside = False

        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]

            if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside

            p1x, p1y = p2x, p2y

        return inside

    def _point_to_segment_distance(
        self, px: float, py: float, x1: float, y1: float, x2: float, y2: float
    ) -> float:
        """Calculate distance from point to line segment.

        Args:
            px, py: Point coordinates.
            x1, y1: First endpoint of segment.
            x2, y2: Second endpoint of segment.

        Returns:
            Distance from point to closest point on segment.
        """
        dx = x2 - x1
        dy = y2 - y1

        # Handle degenerate segment
        if dx == 0 and dy == 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

        # Calculate projection parameter t
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

        # Find closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        return math.sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)

    async def _get_zone(self, zone_id: int) -> PolygonZone | None:
        """Get a polygon zone by ID.

        Args:
            zone_id: ID of the zone to retrieve.

        Returns:
            PolygonZone if found, None otherwise.
        """
        result = await self.db.execute(select(PolygonZone).where(PolygonZone.id == zone_id))
        return result.scalar_one_or_none()

    async def _get_active_dweller_track_ids(self, zone_id: int) -> set[int]:
        """Get track IDs of entities currently inside a zone.

        Args:
            zone_id: ID of the zone.

        Returns:
            Set of track IDs currently in the zone.
        """
        result = await self.db.execute(
            select(DwellTimeRecord.track_id).where(
                and_(
                    DwellTimeRecord.zone_id == zone_id,
                    DwellTimeRecord.exit_time.is_(None),  # Still in zone
                )
            )
        )
        return {row[0] for row in result.all()}

    async def _get_recent_detections(
        self,
        camera_id: str,
        exclude_track_ids: set[int],
        lookback_seconds: int = DETECTION_LOOKBACK_SECONDS,
    ) -> Sequence[Detection]:
        """Get recent detections for a camera, excluding specified track IDs.

        Args:
            camera_id: Camera to get detections for.
            exclude_track_ids: Track IDs to exclude (entities already in zone).
            lookback_seconds: How far back to look for detections.

        Returns:
            Sequence of Detection objects.
        """
        cutoff = utc_now() - timedelta(seconds=lookback_seconds)

        query = (
            select(Detection)
            .where(
                and_(
                    Detection.camera_id == camera_id,
                    Detection.detected_at >= cutoff,
                    Detection.track_id.isnot(None),  # Must have tracking
                    Detection.bbox_x.isnot(None),  # Must have bounding box
                )
            )
            .order_by(Detection.detected_at.asc())
        )

        # Add exclusion filter if we have track IDs to exclude
        if exclude_track_ids:
            query = query.where(Detection.track_id.notin_(exclude_track_ids))

        result = await self.db.execute(query)
        return result.scalars().all()

    def _get_normalized_position(
        self,
        detection: Detection,
        image_width: int,
        image_height: int,
    ) -> tuple[float, float] | None:
        """Get normalized position from a detection's bounding box.

        Args:
            detection: Detection with bbox coordinates.
            image_width: Image width in pixels.
            image_height: Image height in pixels.

        Returns:
            Tuple of (x, y) normalized coordinates, or None if no bbox.
        """
        if (
            detection.bbox_x is None
            or detection.bbox_y is None
            or detection.bbox_width is None
            or detection.bbox_height is None
        ):
            return None

        # Calculate center of bounding box
        center_x = detection.bbox_x + detection.bbox_width / 2
        center_y = detection.bbox_y + detection.bbox_height / 2

        # Normalize to 0-1 range
        norm_x = max(0.0, min(1.0, center_x / image_width))
        norm_y = max(0.0, min(1.0, center_y / image_height))

        return (norm_x, norm_y)


def get_approach_vector_service(db: AsyncSession) -> ApproachVectorService:
    """Factory function to create an ApproachVectorService instance.

    Args:
        db: An async SQLAlchemy session.

    Returns:
        Configured ApproachVectorService instance.
    """
    return ApproachVectorService(db)
