"""Zone service for detection-zone intersection calculations.

This module provides utility functions for determining if detection
bounding boxes overlap with defined camera zones.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.zone import Zone


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
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")

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
