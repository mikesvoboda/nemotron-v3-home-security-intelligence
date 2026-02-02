"""Pydantic schemas for analytics zone API endpoints.

Analytics zones for line crossing and polygon-based intrusion detection:
- Line zones: Track directional crossings (in/out counts)
- Polygon zones: Monitor occupancy within defined areas
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolygonZoneType(StrEnum):
    """Type classification for polygon zones."""

    RESTRICTED = "restricted"  # No entry allowed, high severity alerts
    MONITORED = "monitored"  # General monitoring area
    ENTRY = "entry"  # Entry/exit point (e.g., doors, gates)


class IntrusionSeverity(StrEnum):
    """Severity level for intrusion events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CrossingDirection(StrEnum):
    """Direction of line crossing."""

    IN = "in"
    OUT = "out"


# ============================================================================
# Line Zone Schemas
# ============================================================================


class LineZoneBase(BaseModel):
    """Base schema for line zone data.

    Line zones detect directional crossings across a defined line segment.
    Used for counting entries/exits and triggering alerts on boundary crossings.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Door Entry Line",
                "start_x": 100,
                "start_y": 200,
                "end_x": 400,
                "end_y": 200,
                "alert_on_cross": True,
                "target_classes": ["person"],
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Descriptive name for the line zone",
    )
    start_x: int = Field(..., ge=0, description="X coordinate of line start point (pixels)")
    start_y: int = Field(..., ge=0, description="Y coordinate of line start point (pixels)")
    end_x: int = Field(..., ge=0, description="X coordinate of line end point (pixels)")
    end_y: int = Field(..., ge=0, description="Y coordinate of line end point (pixels)")
    alert_on_cross: bool = Field(
        default=True,
        description="Whether to generate alerts when objects cross this line",
    )
    target_classes: list[str] = Field(
        default_factory=lambda: ["person"],
        description="Object classes to track for this line (e.g., person, car, dog)",
    )

    @field_validator("target_classes")
    @classmethod
    def validate_target_classes(cls, v: list[str]) -> list[str]:
        """Validate that target_classes is not empty and contains valid strings."""
        if not v:
            raise ValueError("target_classes must contain at least one class")
        # Strip and lowercase for consistency
        return [cls_name.strip().lower() for cls_name in v if cls_name.strip()]


class LineZoneCreate(LineZoneBase):
    """Schema for creating a new line zone.

    Requires camera_id to associate the zone with a specific camera.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "name": "Front Door Entry Line",
                "start_x": 100,
                "start_y": 200,
                "end_x": 400,
                "end_y": 200,
                "alert_on_cross": True,
                "target_classes": ["person"],
            }
        }
    )

    camera_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID of the camera this line zone belongs to",
    )


class LineZoneUpdate(BaseModel):
    """Schema for updating an existing line zone.

    All fields are optional; only provided fields are updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Entry Line",
                "alert_on_cross": False,
            }
        }
    )

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Descriptive name for the line zone",
    )
    start_x: int | None = Field(None, ge=0, description="X coordinate of line start point")
    start_y: int | None = Field(None, ge=0, description="Y coordinate of line start point")
    end_x: int | None = Field(None, ge=0, description="X coordinate of line end point")
    end_y: int | None = Field(None, ge=0, description="Y coordinate of line end point")
    alert_on_cross: bool | None = Field(
        None,
        description="Whether to generate alerts when objects cross this line",
    )
    target_classes: list[str] | None = Field(
        None,
        description="Object classes to track for this line",
    )

    @field_validator("target_classes")
    @classmethod
    def validate_target_classes(cls, v: list[str] | None) -> list[str] | None:
        """Validate that target_classes is not empty and contains valid strings."""
        if v is None:
            return v
        if not v:
            raise ValueError("target_classes must contain at least one class")
        return [cls_name.strip().lower() for cls_name in v if cls_name.strip()]


class LineZoneResponse(LineZoneBase):
    """Response schema for a line zone.

    Includes computed counts from crossing events.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "name": "Front Door Entry Line",
                "start_x": 100,
                "start_y": 200,
                "end_x": 400,
                "end_y": 200,
                "alert_on_cross": True,
                "target_classes": ["person"],
                "in_count": 42,
                "out_count": 38,
                "created_at": "2026-01-26T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique line zone identifier")
    camera_id: str = Field(..., description="ID of the camera this line zone belongs to")
    in_count: int = Field(default=0, ge=0, description="Total number of inbound crossings")
    out_count: int = Field(default=0, ge=0, description="Total number of outbound crossings")
    created_at: datetime = Field(..., description="Timestamp when the zone was created")


class LineZoneListResponse(BaseModel):
    """Paginated list of line zones."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zones": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "name": "Front Door Entry Line",
                        "start_x": 100,
                        "start_y": 200,
                        "end_x": 400,
                        "end_y": 200,
                        "alert_on_cross": True,
                        "target_classes": ["person"],
                        "in_count": 42,
                        "out_count": 38,
                        "created_at": "2026-01-26T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    zones: list[LineZoneResponse] = Field(..., description="List of line zones")
    total: int = Field(..., ge=0, description="Total number of line zones")


# ============================================================================
# Polygon Zone Schemas
# ============================================================================


class PolygonZoneBase(BaseModel):
    """Base schema for polygon zone data.

    Polygon zones monitor activity within defined areas.
    Supports various zone types for different monitoring scenarios.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Restricted Area",
                "polygon": [[100, 100], [400, 100], [400, 300], [100, 300]],
                "zone_type": "monitored",
                "alert_threshold": 0,
                "target_classes": ["person"],
                "color": "#FF0000",
                "is_active": True,
                "loitering_threshold_seconds": 60.0,
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Descriptive name for the polygon zone",
    )
    polygon: list[list[int]] = Field(
        ...,
        min_length=3,
        description="List of [x, y] points defining the polygon (minimum 3 points)",
    )
    zone_type: PolygonZoneType = Field(
        default=PolygonZoneType.MONITORED,
        description="Type of zone: restricted, monitored, or entry",
    )
    alert_threshold: int = Field(
        default=0,
        ge=0,
        description="Number of objects that trigger an alert (0 = any entry alerts)",
    )
    target_classes: list[str] = Field(
        default_factory=lambda: ["person"],
        description="Object classes to monitor in this zone",
    )
    color: str = Field(
        default="#FF0000",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for UI display",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the zone is actively monitoring",
    )
    loitering_threshold_seconds: float = Field(
        default=60.0,
        ge=0,
        le=3600,
        description="Loitering threshold in seconds (0-3600). "
        "Objects present longer than this trigger loitering alerts.",
    )

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, v: list[list[int]]) -> list[list[int]]:
        """Validate polygon geometry."""
        if len(v) < 3:
            raise ValueError("Polygon must have at least 3 points")

        for i, point in enumerate(v):
            if len(point) != 2:
                raise ValueError(f"Point {i} must have exactly 2 values [x, y]")
            if point[0] < 0 or point[1] < 0:
                raise ValueError(f"Point {i} coordinates must be non-negative")

        return v

    @field_validator("target_classes")
    @classmethod
    def validate_target_classes(cls, v: list[str]) -> list[str]:
        """Validate that target_classes is not empty and contains valid strings."""
        if not v:
            raise ValueError("target_classes must contain at least one class")
        return [cls_name.strip().lower() for cls_name in v if cls_name.strip()]


class PolygonZoneCreate(PolygonZoneBase):
    """Schema for creating a new polygon zone.

    Requires camera_id to associate the zone with a specific camera.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "name": "Restricted Area",
                "polygon": [[100, 100], [400, 100], [400, 300], [100, 300]],
                "zone_type": "restricted",
                "alert_threshold": 1,
                "target_classes": ["person"],
                "color": "#FF0000",
                "is_active": True,
                "loitering_threshold_seconds": 60.0,
            }
        }
    )

    camera_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID of the camera this polygon zone belongs to",
    )


class PolygonZoneUpdate(BaseModel):
    """Schema for updating an existing polygon zone.

    All fields are optional; only provided fields are updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Restricted Area",
                "alert_threshold": 2,
                "is_active": False,
                "loitering_threshold_seconds": 120.0,
            }
        }
    )

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Descriptive name for the polygon zone",
    )
    polygon: list[list[int]] | None = Field(
        None,
        min_length=3,
        description="List of [x, y] points defining the polygon",
    )
    zone_type: PolygonZoneType | None = Field(
        None,
        description="Type of zone: restricted, monitored, or entry",
    )
    alert_threshold: int | None = Field(
        None,
        ge=0,
        description="Number of objects that trigger an alert",
    )
    target_classes: list[str] | None = Field(
        None,
        description="Object classes to monitor in this zone",
    )
    color: str | None = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for UI display",
    )
    is_active: bool | None = Field(
        None,
        description="Whether the zone is actively monitoring",
    )
    loitering_threshold_seconds: float | None = Field(
        None,
        ge=0,
        le=3600,
        description="Loitering threshold in seconds (0-3600). "
        "Objects present longer than this trigger loitering alerts.",
    )

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, v: list[list[int]] | None) -> list[list[int]] | None:
        """Validate polygon geometry."""
        if v is None:
            return v

        if len(v) < 3:
            raise ValueError("Polygon must have at least 3 points")

        for i, point in enumerate(v):
            if len(point) != 2:
                raise ValueError(f"Point {i} must have exactly 2 values [x, y]")
            if point[0] < 0 or point[1] < 0:
                raise ValueError(f"Point {i} coordinates must be non-negative")

        return v

    @field_validator("target_classes")
    @classmethod
    def validate_target_classes(cls, v: list[str] | None) -> list[str] | None:
        """Validate that target_classes is not empty and contains valid strings."""
        if v is None:
            return v
        if not v:
            raise ValueError("target_classes must contain at least one class")
        return [cls_name.strip().lower() for cls_name in v if cls_name.strip()]


class PolygonZoneResponse(PolygonZoneBase):
    """Response schema for a polygon zone.

    Includes current occupancy count.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "name": "Restricted Area",
                "polygon": [[100, 100], [400, 100], [400, 300], [100, 300]],
                "zone_type": "restricted",
                "alert_threshold": 1,
                "target_classes": ["person"],
                "color": "#FF0000",
                "is_active": True,
                "loitering_threshold_seconds": 60.0,
                "current_count": 0,
                "created_at": "2026-01-26T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique polygon zone identifier")
    camera_id: str = Field(..., description="ID of the camera this zone belongs to")
    current_count: int = Field(default=0, ge=0, description="Current object count in zone")
    created_at: datetime = Field(..., description="Timestamp when the zone was created")


class PolygonZoneListResponse(BaseModel):
    """Paginated list of polygon zones."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zones": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "name": "Restricted Area",
                        "polygon": [[100, 100], [400, 100], [400, 300], [100, 300]],
                        "zone_type": "restricted",
                        "alert_threshold": 1,
                        "target_classes": ["person"],
                        "color": "#FF0000",
                        "is_active": True,
                        "loitering_threshold_seconds": 60.0,
                        "current_count": 0,
                        "created_at": "2026-01-26T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    zones: list[PolygonZoneResponse] = Field(..., description="List of polygon zones")
    total: int = Field(..., ge=0, description="Total number of polygon zones")


# ============================================================================
# Event Schemas
# ============================================================================


class LineCrossingEvent(BaseModel):
    """Event triggered when an object crosses a line zone.

    Captures the moment and direction of crossing for analytics and alerting.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "line_zone_id": 1,
                "track_id": 42,
                "direction": "in",
                "object_class": "person",
                "timestamp": "2026-01-26T12:30:45Z",
                "camera_id": "front_door",
            }
        }
    )

    line_zone_id: int = Field(..., description="ID of the line zone that was crossed")
    track_id: int = Field(..., description="Tracker-assigned ID of the crossing object")
    direction: Literal["in", "out"] = Field(
        ..., description="Direction of crossing relative to line normal"
    )
    object_class: str = Field(..., description="Class of the object that crossed (e.g., person)")
    timestamp: datetime = Field(..., description="Timestamp of the crossing event")
    camera_id: str = Field(..., description="ID of the camera where crossing occurred")


class IntrusionEvent(BaseModel):
    """Event triggered when objects enter a polygon zone.

    Used for security monitoring and occupancy alerting.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "zone_name": "Restricted Area",
                "track_ids": [42, 43],
                "object_count": 2,
                "timestamp": "2026-01-26T12:30:45Z",
                "camera_id": "front_door",
                "severity": "high",
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone with intrusion")
    zone_name: str = Field(..., description="Name of the zone for display purposes")
    track_ids: list[int] = Field(..., description="List of tracker IDs for objects in the zone")
    object_count: int = Field(..., ge=1, description="Number of objects detected in zone")
    timestamp: datetime = Field(..., description="Timestamp of the intrusion event")
    camera_id: str = Field(..., description="ID of the camera where intrusion occurred")
    severity: IntrusionSeverity = Field(
        ..., description="Severity level based on zone type and count"
    )


# ============================================================================
# Entity Distribution Schemas (NEM-4937)
# ============================================================================


class EntityTypeCount(BaseModel):
    """Count of entities by type within a zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_type": "person",
                "count": 42,
                "percentage": 65.5,
            }
        }
    )

    entity_type: str = Field(..., description="Entity type (e.g., person, vehicle, car)")
    count: int = Field(..., ge=0, description="Number of entities of this type")
    percentage: float = Field(..., ge=0, le=100, description="Percentage of total entities")


class ZoneEntityDistribution(BaseModel):
    """Entity distribution for a single zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "zone_name": "Front Yard",
                "total_entities": 64,
                "entity_types": [
                    {"entity_type": "person", "count": 42, "percentage": 65.63},
                    {"entity_type": "vehicle", "count": 15, "percentage": 23.44},
                    {"entity_type": "dog", "count": 7, "percentage": 10.94},
                ],
            }
        }
    )

    zone_id: int = Field(..., description="Zone ID")
    zone_name: str = Field(..., description="Zone name for display")
    total_entities: int = Field(..., ge=0, description="Total number of entities in this zone")
    entity_types: list[EntityTypeCount] = Field(
        ..., description="Breakdown of entity types in this zone"
    )


class ZoneEntityDistributionResponse(BaseModel):
    """Response containing entity distribution across multiple zones."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zones": [
                    {
                        "zone_id": 1,
                        "zone_name": "Front Yard",
                        "total_entities": 64,
                        "entity_types": [
                            {"entity_type": "person", "count": 42, "percentage": 65.63},
                            {"entity_type": "vehicle", "count": 15, "percentage": 23.44},
                            {"entity_type": "dog", "count": 7, "percentage": 10.94},
                        ],
                    }
                ],
                "grand_total": 64,
                "start_time": "2026-01-31T00:00:00Z",
                "end_time": "2026-01-31T23:59:59Z",
            }
        }
    )

    zones: list[ZoneEntityDistribution] = Field(..., description="Entity distribution per zone")
    grand_total: int = Field(..., ge=0, description="Total entities across all zones")
    start_time: datetime = Field(..., description="Start of the query time window")
    end_time: datetime = Field(..., description="End of the query time window")


# ============================================================================
# Approach Vector Schemas (NEM-4936)
# ============================================================================


class ApproachUrgency(StrEnum):
    """Urgency level based on ETA to zone."""

    IMMINENT = "imminent"  # ETA < 3 seconds (red)
    APPROACHING = "approaching"  # ETA 3-10 seconds (yellow)
    DISTANT = "distant"  # ETA > 10 seconds (green)
    NOT_APPROACHING = "not_approaching"  # Moving away or stationary


class ApproachVectorData(BaseModel):
    """Approach vector data for a single entity approaching a zone.

    Contains movement trajectory analysis including direction, speed, and ETA.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "track_id": 42,
                "object_class": "person",
                "is_approaching": True,
                "direction_degrees": 45.0,
                "speed_normalized": 0.05,
                "distance_to_zone": 0.15,
                "estimated_arrival_seconds": 3.0,
                "urgency": "imminent",
                "current_position": {"x": 0.35, "y": 0.40},
                "zone_centroid": {"x": 0.50, "y": 0.50},
            }
        }
    )

    track_id: int = Field(..., description="Tracking ID of the approaching entity")
    object_class: str = Field(..., description="Object classification (person, vehicle, etc.)")
    is_approaching: bool = Field(..., description="Whether entity is moving toward the zone")
    direction_degrees: float = Field(
        ...,
        ge=0,
        lt=360,
        description="Direction of movement in degrees (0=up, 90=right, 180=down, 270=left)",
    )
    speed_normalized: float = Field(
        ...,
        ge=0,
        description="Speed of movement in normalized units per second",
    )
    distance_to_zone: float = Field(
        ...,
        ge=0,
        description="Current distance to zone boundary (normalized units, 0 = inside zone)",
    )
    estimated_arrival_seconds: float | None = Field(
        None,
        ge=0,
        description="Estimated time to reach zone in seconds (None if not approaching)",
    )
    urgency: ApproachUrgency = Field(
        ...,
        description="Urgency level based on ETA (imminent/approaching/distant/not_approaching)",
    )
    current_position: dict[str, float] = Field(
        ...,
        description="Current position as {x, y} in normalized coordinates (0-1)",
    )
    zone_centroid: dict[str, float] = Field(
        ...,
        description="Zone centroid as {x, y} in normalized coordinates",
    )


class ZoneApproachVectorsResponse(BaseModel):
    """Response containing approach vectors for a zone.

    Provides real-time movement analysis for all tracked entities
    approaching a specific zone.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "zone_name": "Front Door",
                "approach_vectors": [
                    {
                        "track_id": 42,
                        "object_class": "person",
                        "is_approaching": True,
                        "direction_degrees": 45.0,
                        "speed_normalized": 0.05,
                        "distance_to_zone": 0.15,
                        "estimated_arrival_seconds": 3.0,
                        "urgency": "imminent",
                        "current_position": {"x": 0.35, "y": 0.40},
                        "zone_centroid": {"x": 0.50, "y": 0.50},
                    }
                ],
                "total_approaching": 1,
                "imminent_count": 1,
                "timestamp": "2026-01-31T12:00:00Z",
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone")
    zone_name: str = Field(..., description="Zone name for display")
    approach_vectors: list[ApproachVectorData] = Field(
        ...,
        description="Approach vectors for all tracked entities",
    )
    total_approaching: int = Field(
        ...,
        ge=0,
        description="Total number of entities approaching the zone",
    )
    imminent_count: int = Field(
        ...,
        ge=0,
        description="Number of entities with imminent arrival (ETA < 3s)",
    )
    timestamp: datetime = Field(..., description="Timestamp of the analysis")


class CameraApproachVectorsResponse(BaseModel):
    """Response containing approach vectors for all zones on a camera.

    Aggregates approach vector data across all zones for a single camera,
    enabling efficient visualization of approaching entities.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "zones": [
                    {
                        "zone_id": 1,
                        "zone_name": "Front Door",
                        "approach_vectors": [
                            {
                                "track_id": 42,
                                "object_class": "person",
                                "is_approaching": True,
                                "direction_degrees": 45.0,
                                "speed_normalized": 0.05,
                                "distance_to_zone": 0.15,
                                "estimated_arrival_seconds": 3.0,
                                "urgency": "imminent",
                                "current_position": {"x": 0.35, "y": 0.40},
                                "zone_centroid": {"x": 0.50, "y": 0.50},
                            }
                        ],
                        "total_approaching": 1,
                        "imminent_count": 1,
                        "timestamp": "2026-01-31T12:00:00Z",
                    }
                ],
                "total_zones": 1,
                "total_approaching_entities": 1,
            }
        }
    )

    camera_id: str = Field(..., description="Camera ID")
    zones: list[ZoneApproachVectorsResponse] = Field(
        ...,
        description="Approach vectors for each zone",
    )
    total_zones: int = Field(..., ge=0, description="Total number of zones analyzed")
    total_approaching_entities: int = Field(
        ...,
        ge=0,
        description="Total approaching entities across all zones",
    )


# Export all schemas
__all__ = [  # noqa: RUF022
    # Enums
    "ApproachUrgency",
    "CrossingDirection",
    "IntrusionSeverity",
    "PolygonZoneType",
    # Line zone schemas
    "LineZoneBase",
    "LineZoneCreate",
    "LineZoneListResponse",
    "LineZoneResponse",
    "LineZoneUpdate",
    # Polygon zone schemas
    "PolygonZoneBase",
    "PolygonZoneCreate",
    "PolygonZoneListResponse",
    "PolygonZoneResponse",
    "PolygonZoneUpdate",
    # Event schemas
    "IntrusionEvent",
    "LineCrossingEvent",
    # Entity distribution schemas (NEM-4937)
    "EntityTypeCount",
    "ZoneEntityDistribution",
    "ZoneEntityDistributionResponse",
    # Approach vector schemas (NEM-4936)
    "ApproachVectorData",
    "CameraApproachVectorsResponse",
    "ZoneApproachVectorsResponse",
]
