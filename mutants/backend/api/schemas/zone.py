"""Pydantic schemas for zone API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.zone import ZoneShape, ZoneType

# Expose validation functions for testing
__all__ = [
    "ZoneCreate",
    "ZoneListResponse",
    "ZoneResponse",
    "ZoneUpdate",
    "_has_duplicate_consecutive_points",
    "_is_self_intersecting",
    "_polygon_area",
    "_validate_polygon_geometry",
]


def _ccw(a: list[float], b: list[float], c: list[float]) -> float:
    """Return cross product sign for counter-clockwise test.

    Positive if counter-clockwise, negative if clockwise, zero if collinear.
    """
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(p1: list[float], p2: list[float], p3: list[float], p4: list[float]) -> bool:
    """Check if line segments (p1,p2) and (p3,p4) intersect properly.

    Returns True only for proper intersection (not touching at endpoints).
    Uses the orientation method for robust intersection detection.
    """
    d1 = _ccw(p3, p4, p1)
    d2 = _ccw(p3, p4, p2)
    d3 = _ccw(p1, p2, p3)
    d4 = _ccw(p1, p2, p4)

    # Check for proper crossing (signs must differ)
    return ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    )


def _is_self_intersecting(coords: list[list[float]]) -> bool:
    """Check if a polygon self-intersects.

    Checks all non-adjacent edges for intersection.
    Adjacent edges share a vertex and are allowed to "touch".
    """
    n = len(coords)
    if n < 4:
        # A triangle cannot self-intersect
        return False

    # Check all pairs of non-adjacent edges
    for i in range(n):
        p1 = coords[i]
        p2 = coords[(i + 1) % n]

        # Check against non-adjacent edges
        # Skip adjacent edges (i-1 and i+1)
        for j in range(i + 2, n):
            # Skip the edge that wraps around and is adjacent to edge i
            if i == 0 and j == n - 1:
                continue

            p3 = coords[j]
            p4 = coords[(j + 1) % n]

            if _segments_intersect(p1, p2, p3, p4):
                return True

    return False


def _has_duplicate_consecutive_points(coords: list[list[float]], tolerance: float = 1e-9) -> bool:
    """Check if polygon has duplicate consecutive points.

    Returns True if any two consecutive points are essentially the same.
    """
    n = len(coords)
    for i in range(n):
        p1 = coords[i]
        p2 = coords[(i + 1) % n]
        if abs(p1[0] - p2[0]) < tolerance and abs(p1[1] - p2[1]) < tolerance:
            return True
    return False


def _polygon_area(coords: list[list[float]]) -> float:
    """Calculate the signed area of a polygon using the shoelace formula.

    Positive for counter-clockwise, negative for clockwise.
    """
    n = len(coords)
    if n < 3:
        return 0.0

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return area / 2.0


def _validate_polygon_geometry(coords: list[list[float]]) -> list[list[float]]:
    """Validate that coordinates form a valid polygon.

    Checks:
    1. Each point has exactly 2 values [x, y]
    2. All values are normalized (0-1 range)
    3. No duplicate consecutive points
    4. Polygon has positive area (not degenerate)
    5. Polygon does not self-intersect

    Args:
        coords: List of [x, y] coordinate pairs

    Returns:
        The validated coordinates

    Raises:
        ValueError: If any validation fails
    """
    # Check point format and normalization
    for point in coords:
        if len(point) != 2:
            raise ValueError("Each coordinate must have exactly 2 values [x, y]")
        x, y = point
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Coordinates must be normalized (0-1 range)")

    # Check for duplicate consecutive points
    if _has_duplicate_consecutive_points(coords):
        raise ValueError("Polygon has duplicate consecutive points")

    # Check polygon has positive area (not degenerate)
    area = abs(_polygon_area(coords))
    if area < 1e-10:
        raise ValueError("Polygon has zero or near-zero area (degenerate shape)")

    # Check for self-intersection
    if _is_self_intersecting(coords):
        raise ValueError("Polygon edges must not intersect (self-intersecting shape)")

    return coords


class ZoneCreate(BaseModel):
    """Schema for creating a new zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Door",
                "zone_type": "entry_point",
                "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
                "shape": "rectangle",
                "color": "#3B82F6",
                "enabled": True,
                "priority": 1,
            }
        }
    )

    name: str = Field(..., min_length=1, max_length=255, description="Zone name")
    zone_type: ZoneType = Field(default=ZoneType.OTHER, description="Type of zone")
    coordinates: list[list[float]] = Field(
        ...,
        description="Array of normalized [x, y] points (0-1 range)",
        min_length=3,  # Minimum 3 points for a polygon
    )
    shape: ZoneShape = Field(default=ZoneShape.RECTANGLE, description="Shape of the zone")
    color: str = Field(
        default="#3B82F6",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for UI display",
    )
    enabled: bool = Field(default=True, description="Whether zone is active")
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Priority for overlapping zones (higher = more important)",
    )

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: list[list[float]]) -> list[list[float]]:
        """Validate that coordinates form a valid polygon."""
        return _validate_polygon_geometry(v)


class ZoneUpdate(BaseModel):
    """Schema for updating an existing zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Door - Updated",
                "enabled": False,
            }
        }
    )

    name: str | None = Field(None, min_length=1, max_length=255, description="Zone name")
    zone_type: ZoneType | None = Field(None, description="Type of zone")
    coordinates: list[list[float]] | None = Field(
        None,
        description="Array of normalized [x, y] points (0-1 range)",
        min_length=3,
    )
    shape: ZoneShape | None = Field(None, description="Shape of the zone")
    color: str | None = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for UI display",
    )
    enabled: bool | None = Field(None, description="Whether zone is active")
    priority: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Priority for overlapping zones (higher = more important)",
    )

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: list[list[float]] | None) -> list[list[float]] | None:
        """Validate that coordinates form a valid polygon."""
        if v is None:
            return v
        return _validate_polygon_geometry(v)


class ZoneResponse(BaseModel):
    """Schema for zone response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "camera_id": "front_door",
                "name": "Front Door",
                "zone_type": "entry_point",
                "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
                "shape": "rectangle",
                "color": "#3B82F6",
                "enabled": True,
                "priority": 1,
                "created_at": "2025-12-23T10:00:00Z",
                "updated_at": "2025-12-23T12:00:00Z",
            }
        },
    )

    id: str = Field(..., description="Zone UUID")
    camera_id: str = Field(..., description="Camera ID this zone belongs to")
    name: str = Field(..., description="Zone name")
    zone_type: ZoneType = Field(..., description="Type of zone")
    coordinates: list[list[float]] = Field(
        ..., description="Array of normalized [x, y] points (0-1 range)"
    )
    shape: ZoneShape = Field(..., description="Shape of the zone")
    color: str = Field(..., description="Hex color for UI display")
    enabled: bool = Field(..., description="Whether zone is active")
    priority: int = Field(..., description="Priority for overlapping zones")
    created_at: datetime = Field(..., description="Timestamp when zone was created")
    updated_at: datetime = Field(..., description="Timestamp when zone was last updated")


class ZoneListResponse(BaseModel):
    """Schema for zone list response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zones": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "camera_id": "front_door",
                        "name": "Front Door",
                        "zone_type": "entry_point",
                        "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
                        "shape": "rectangle",
                        "color": "#3B82F6",
                        "enabled": True,
                        "priority": 1,
                        "created_at": "2025-12-23T10:00:00Z",
                        "updated_at": "2025-12-23T12:00:00Z",
                    }
                ],
                "count": 1,
            }
        }
    )

    zones: list[ZoneResponse] = Field(..., description="List of zones")
    count: int = Field(..., description="Total number of zones")
