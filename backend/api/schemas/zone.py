"""Pydantic schemas for zone API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.zone import ZoneShape, ZoneType


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
        """Validate that coordinates are normalized and properly formatted."""
        for point in v:
            if len(point) != 2:
                raise ValueError("Each coordinate must have exactly 2 values [x, y]")
            x, y = point
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("Coordinates must be normalized (0-1 range)")
        return v


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
        """Validate that coordinates are normalized and properly formatted."""
        if v is None:
            return v
        for point in v:
            if len(point) != 2:
                raise ValueError("Each coordinate must have exactly 2 values [x, y]")
            x, y = point
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("Coordinates must be normalized (0-1 range)")
        return v


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
