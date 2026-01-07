"""Zone service for detection-zone intersection calculations.

This module provides utility functions for determining if detection
bounding boxes overlap with defined camera zones, as well as spatial
heuristics for enhanced detection analysis including dwell time tracking,
line crossing detection, and approach vector calculation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.zone import Zone

if TYPE_CHECKING:
    from backend.models.detection import Detection


@dataclass(slots=True)
class ApproachVector:
    """Result of approach vector calculation.

    Attributes:
        is_approaching: True if the detection is moving toward the zone
        direction_degrees: Direction of movement in degrees (0=up, 90=right, 180=down, 270=left)
        speed_normalized: Speed of movement in normalized units per second
        distance_to_zone: Current distance to zone centroid (normalized units)
        estimated_arrival_seconds: Estimated time to reach zone if approaching (None if not approaching)
    """

    is_approaching: bool
    direction_degrees: float
    speed_normalized: float
    distance_to_zone: float
    estimated_arrival_seconds: float | None


def point_in_zone(x: float, y: float, zone: Zone) -> bool:
    """Check if a normalized point is inside a zone.

    Uses the ray casting algorithm for polygon point-in-polygon testing.
    This works for both rectangles and arbitrary polygons.

    Args:
        x: Normalized x coordinate (0-1 range)
        y: Normalized y coordinate (0-1 range)
        zone: Zone object with coordinates

    Returns:
        True if the point is inside the zone, False otherwise
    """
    if not zone.enabled:
        return False

    coordinates = zone.coordinates
    if not coordinates or len(coordinates) < 3:
        return False

    # Ray casting algorithm
    n = len(coordinates)
    inside = False

    p1x, p1y = coordinates[0]
    for i in range(1, n + 1):
        p2x, p2y = coordinates[i % n]

        if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or x <= xinters:
                inside = not inside

        p1x, p1y = p2x, p2y

    return inside


def bbox_center(
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
    image_width: int,
    image_height: int,
) -> tuple[float, float]:
    """Calculate the normalized center point of a bounding box.

    Args:
        bbox_x: X coordinate of bounding box top-left corner (pixels)
        bbox_y: Y coordinate of bounding box top-left corner (pixels)
        bbox_width: Width of bounding box (pixels)
        bbox_height: Height of bounding box (pixels)
        image_width: Width of the image (pixels)
        image_height: Height of the image (pixels)

    Returns:
        Tuple of (normalized_x, normalized_y) coordinates (0-1 range)

    Raises:
        ValueError: If image dimensions are not positive, or if bbox
            coordinates are negative, or if bbox dimensions are not positive.
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")

    if bbox_x < 0 or bbox_y < 0:
        raise ValueError("Bounding box coordinates must be non-negative")

    if bbox_width <= 0 or bbox_height <= 0:
        raise ValueError("Bounding box dimensions must be positive")

    center_x = bbox_x + bbox_width / 2
    center_y = bbox_y + bbox_height / 2

    normalized_x = center_x / image_width
    normalized_y = center_y / image_height

    # Clamp to 0-1 range
    normalized_x = max(0.0, min(1.0, normalized_x))
    normalized_y = max(0.0, min(1.0, normalized_y))

    return normalized_x, normalized_y


def detection_in_zone(
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
    image_width: int,
    image_height: int,
    zone: Zone,
) -> bool:
    """Check if a detection bounding box center is inside a zone.

    Uses the center point of the bounding box for zone membership.

    Args:
        bbox_x: X coordinate of bounding box top-left corner (pixels)
        bbox_y: Y coordinate of bounding box top-left corner (pixels)
        bbox_width: Width of bounding box (pixels)
        bbox_height: Height of bounding box (pixels)
        image_width: Width of the image (pixels)
        image_height: Height of the image (pixels)
        zone: Zone object to check against

    Returns:
        True if the detection center is inside the zone, False otherwise
    """
    if not zone.enabled:
        return False

    center_x, center_y = bbox_center(
        bbox_x, bbox_y, bbox_width, bbox_height, image_width, image_height
    )

    return point_in_zone(center_x, center_y, zone)


async def get_zones_for_detection(
    camera_id: str,
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
    image_width: int,
    image_height: int,
    db: AsyncSession,
) -> list[Zone]:
    """Return list of zones that a detection bounding box overlaps with.

    Queries all enabled zones for the camera and checks if the detection
    center falls within each zone. Results are ordered by priority (descending).

    Args:
        camera_id: ID of the camera the detection is from
        bbox_x: X coordinate of bounding box top-left corner (pixels)
        bbox_y: Y coordinate of bounding box top-left corner (pixels)
        bbox_width: Width of bounding box (pixels)
        bbox_height: Height of bounding box (pixels)
        image_width: Width of the image (pixels)
        image_height: Height of the image (pixels)
        db: Database session

    Returns:
        List of Zone objects that the detection overlaps with, sorted by priority
    """
    # Query enabled zones for this camera
    result = await db.execute(
        select(Zone)
        .where(Zone.camera_id == camera_id, Zone.enabled == True)  # noqa: E712
        .order_by(Zone.priority.desc())
    )
    zones = result.scalars().all()

    # Calculate detection center
    center_x, center_y = bbox_center(
        bbox_x, bbox_y, bbox_width, bbox_height, image_width, image_height
    )

    # Find all zones containing the detection center
    matching_zones = []
    for zone in zones:
        if point_in_zone(center_x, center_y, zone):
            matching_zones.append(zone)

    return matching_zones


def get_highest_priority_zone(zones: list[Zone]) -> Zone | None:
    """Get the highest priority zone from a list.

    Args:
        zones: List of Zone objects

    Returns:
        Zone with highest priority, or None if list is empty
    """
    if not zones:
        return None

    return max(zones, key=lambda z: z.priority)


def zones_to_context(zones: list[Zone]) -> dict[str, list[str]]:
    """Convert zones to a context dictionary for risk analysis.

    Creates a structured representation of zone information that can be
    included in risk analysis prompts for the LLM.

    Args:
        zones: List of Zone objects

    Returns:
        Dictionary with zone type as key and list of zone names as value
    """
    context: dict[str, list[str]] = {}

    for zone in zones:
        zone_type = zone.zone_type.value
        if zone_type not in context:
            context[zone_type] = []
        context[zone_type].append(zone.name)

    return context


# =============================================================================
# Spatial Heuristics Functions
# =============================================================================


def _get_detection_center(
    detection: Detection, image_width: int, image_height: int
) -> tuple[float, float] | None:
    """Get the normalized center point of a detection.

    Args:
        detection: Detection object with bbox coordinates
        image_width: Width of the image in pixels
        image_height: Height of the image in pixels

    Returns:
        Tuple of (normalized_x, normalized_y) or None if detection has no bbox
    """
    if (
        detection.bbox_x is None
        or detection.bbox_y is None
        or detection.bbox_width is None
        or detection.bbox_height is None
    ):
        return None

    return bbox_center(
        detection.bbox_x,
        detection.bbox_y,
        detection.bbox_width,
        detection.bbox_height,
        image_width,
        image_height,
    )


def _get_zone_centroid(zone: Zone) -> tuple[float, float] | None:
    """Calculate the centroid of a zone polygon.

    Args:
        zone: Zone object with coordinates

    Returns:
        Tuple of (centroid_x, centroid_y) or None if zone has no coordinates
    """
    coordinates = zone.coordinates
    if not coordinates or len(coordinates) < 3:
        return None

    # Calculate centroid as average of all vertices
    sum_x = sum(coord[0] for coord in coordinates)
    sum_y = sum(coord[1] for coord in coordinates)
    n = len(coordinates)

    return (sum_x / n, sum_y / n)


def _distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points.

    Args:
        p1: First point (x, y)
        p2: Second point (x, y)

    Returns:
        Euclidean distance between the points
    """
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def _distance_to_zone_boundary(x: float, y: float, zone: Zone) -> float:
    """Calculate minimum distance from a point to zone boundary.

    Uses point-to-line-segment distance for each edge of the zone polygon.

    Args:
        x: X coordinate of point
        y: Y coordinate of point
        zone: Zone object with coordinates

    Returns:
        Minimum distance to zone boundary (0 if point is inside zone)
    """
    coordinates = zone.coordinates
    if not coordinates or len(coordinates) < 3:
        return float("inf")

    # If point is inside zone, distance is 0
    if point_in_zone(x, y, zone):
        return 0.0

    min_distance = float("inf")
    n = len(coordinates)

    for i in range(n):
        # Get edge from vertex i to vertex (i+1) % n
        x1, y1 = coordinates[i]
        x2, y2 = coordinates[(i + 1) % n]

        # Calculate distance from point to line segment
        dist = _point_to_segment_distance(x, y, x1, y1, x2, y2)
        min_distance = min(min_distance, dist)

    return min_distance


def _point_to_segment_distance(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Calculate distance from point (px, py) to line segment (x1,y1)-(x2,y2).

    Args:
        px, py: Point coordinates
        x1, y1: First endpoint of segment
        x2, y2: Second endpoint of segment

    Returns:
        Distance from point to closest point on segment
    """
    # Vector from segment start to point
    dx = x2 - x1
    dy = y2 - y1

    # Handle degenerate segment (single point)
    if dx == 0 and dy == 0:
        return _distance((px, py), (x1, y1))

    # Calculate projection parameter t
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

    # Find closest point on segment
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return _distance((px, py), (closest_x, closest_y))


def calculate_dwell_time(
    detections: list[Detection],
    zone: Zone,
    image_width: int = 1920,
    image_height: int = 1080,
) -> float:
    """Calculate how long a detection has remained in a zone continuously.

    Analyzes a list of detections (ordered by time) to determine the continuous
    dwell time within a zone. The dwell time is calculated from the first detection
    in the zone until a detection leaves the zone or the list ends.

    Args:
        detections: List of Detection objects, ordered by detected_at ascending.
                   Should represent the same tracked object over time.
        zone: Zone to check dwell time in
        image_width: Width of the image in pixels (default 1920)
        image_height: Height of the image in pixels (default 1080)

    Returns:
        Total continuous dwell time in seconds. Returns 0.0 if:
        - No detections in list
        - Zone is disabled
        - Object never entered the zone
        - Detections have no valid bounding boxes
    """
    if not detections or not zone.enabled:
        return 0.0

    if len(detections) < 2:
        # Need at least 2 detections to calculate time difference
        # Check if single detection is in zone
        if len(detections) == 1:
            center = _get_detection_center(detections[0], image_width, image_height)
            if center and point_in_zone(center[0], center[1], zone):
                # Single detection in zone, but no time span
                return 0.0
        return 0.0

    # Find continuous period(s) in zone
    dwell_start = None
    total_dwell = 0.0

    for detection in detections:
        center = _get_detection_center(detection, image_width, image_height)
        if center is None:
            continue

        is_in_zone = point_in_zone(center[0], center[1], zone)

        if is_in_zone:
            if dwell_start is None:
                # Start tracking dwell time
                dwell_start = detection.detected_at
        elif dwell_start is not None:
            # Object left zone, calculate dwell time
            dwell_end = detection.detected_at
            dwell_seconds = (dwell_end - dwell_start).total_seconds()
            total_dwell += dwell_seconds
            dwell_start = None

    # If still in zone at end of detections, add remaining dwell time
    if dwell_start is not None and detections:
        # Find last valid detection
        for detection in reversed(detections):
            if detection.detected_at is not None:
                dwell_seconds = (detection.detected_at - dwell_start).total_seconds()
                total_dwell += dwell_seconds
                break

    return total_dwell


def detect_line_crossing(
    prev_detection: Detection,
    curr_detection: Detection,
    zone: Zone,
    image_width: int = 1920,
    image_height: int = 1080,
) -> bool:
    """Detect if a detection crossed from outside to inside a zone.

    Determines if movement between two consecutive detections represents
    a boundary crossing event (entering the zone from outside).

    Args:
        prev_detection: Previous detection (earlier in time)
        curr_detection: Current detection (later in time)
        zone: Zone to check for crossing into
        image_width: Width of the image in pixels (default 1920)
        image_height: Height of the image in pixels (default 1080)

    Returns:
        True if the detection crossed from outside the zone to inside.
        False if:
        - Zone is disabled
        - Either detection has no valid bounding box
        - Detection was already inside the zone
        - Detection moved but stayed outside
        - Detection exited the zone (opposite direction)
    """
    if not zone.enabled:
        return False

    prev_center = _get_detection_center(prev_detection, image_width, image_height)
    curr_center = _get_detection_center(curr_detection, image_width, image_height)

    if prev_center is None or curr_center is None:
        return False

    prev_in_zone = point_in_zone(prev_center[0], prev_center[1], zone)
    curr_in_zone = point_in_zone(curr_center[0], curr_center[1], zone)

    # Line crossing occurs when: was outside, now inside
    return not prev_in_zone and curr_in_zone


def detect_line_exit(
    prev_detection: Detection,
    curr_detection: Detection,
    zone: Zone,
    image_width: int = 1920,
    image_height: int = 1080,
) -> bool:
    """Detect if a detection crossed from inside to outside a zone.

    Determines if movement between two consecutive detections represents
    a boundary crossing event (exiting the zone from inside).

    Args:
        prev_detection: Previous detection (earlier in time)
        curr_detection: Current detection (later in time)
        zone: Zone to check for crossing out of
        image_width: Width of the image in pixels (default 1920)
        image_height: Height of the image in pixels (default 1080)

    Returns:
        True if the detection crossed from inside the zone to outside.
        False otherwise.
    """
    if not zone.enabled:
        return False

    prev_center = _get_detection_center(prev_detection, image_width, image_height)
    curr_center = _get_detection_center(curr_detection, image_width, image_height)

    if prev_center is None or curr_center is None:
        return False

    prev_in_zone = point_in_zone(prev_center[0], prev_center[1], zone)
    curr_in_zone = point_in_zone(curr_center[0], curr_center[1], zone)

    # Line exit occurs when: was inside, now outside
    return prev_in_zone and not curr_in_zone


def calculate_approach_vector(
    detections: list[Detection],
    zone: Zone,
    image_width: int = 1920,
    image_height: int = 1080,
) -> ApproachVector | None:
    """Calculate if and how a detection is approaching a zone.

    Analyzes movement trajectory from a list of detections to determine
    if the object is moving toward the zone and at what speed/direction.

    Args:
        detections: List of Detection objects, ordered by detected_at ascending.
                   Needs at least 2 detections to calculate movement.
        zone: Target zone to check approach toward
        image_width: Width of the image in pixels (default 1920)
        image_height: Height of the image in pixels (default 1080)

    Returns:
        ApproachVector with movement analysis, or None if:
        - Less than 2 valid detections
        - Zone is disabled or has no valid coordinates
        - Detections have no valid bounding boxes
        - Time difference is zero (can't calculate speed)
    """
    if not zone.enabled or len(detections) < 2:
        return None

    zone_centroid = _get_zone_centroid(zone)
    if zone_centroid is None:
        return None

    # Find first and last valid detections with centers
    first_detection = None
    first_center = None
    last_detection = None
    last_center = None

    for detection in detections:
        center = _get_detection_center(detection, image_width, image_height)
        if center is not None:
            if first_detection is None:
                first_detection = detection
                first_center = center
            last_detection = detection
            last_center = center

    if (
        first_center is None
        or last_center is None
        or first_detection is None
        or last_detection is None
    ):
        return None

    # Calculate time difference
    time_delta = (last_detection.detected_at - first_detection.detected_at).total_seconds()
    if time_delta <= 0:
        return None

    # Calculate movement vector
    dx = last_center[0] - first_center[0]
    dy = last_center[1] - first_center[1]

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

    # Calculate current distance to zone
    # Use distance to boundary if outside, 0 if inside
    current_distance = _distance_to_zone_boundary(last_center[0], last_center[1], zone)

    # Determine if approaching
    # Compare distance from first position to zone vs last position to zone
    first_distance = _distance_to_zone_boundary(first_center[0], first_center[1], zone)
    is_approaching = current_distance < first_distance

    # Estimate arrival time if approaching
    estimated_arrival: float | None = None
    if is_approaching and speed > 0 and current_distance > 0:
        # Simple linear estimate
        estimated_arrival = current_distance / speed
    elif current_distance == 0:
        # Already in zone
        estimated_arrival = 0.0

    return ApproachVector(
        is_approaching=is_approaching,
        direction_degrees=direction_deg,
        speed_normalized=speed,
        distance_to_zone=current_distance,
        estimated_arrival_seconds=estimated_arrival,
    )
