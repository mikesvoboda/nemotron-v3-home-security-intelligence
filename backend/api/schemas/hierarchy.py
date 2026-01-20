"""Pydantic schemas for household hierarchy API endpoints.

This module provides schemas for managing the organizational hierarchy:
- Household (top-level organization unit)
- Property (physical locations within a household)
- Area (logical zones within a property)

Implements NEM-3131: Phase 6.1 - Create Household CRUD API endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# Household Schemas
# =============================================================================


def _validate_name(v: str, max_length: int = 100) -> str:
    """Validate and sanitize name fields.

    Args:
        v: The name string to validate
        max_length: Maximum allowed length

    Returns:
        The validated and sanitized name (with leading/trailing whitespace stripped)

    Raises:
        ValueError: If name is empty, whitespace-only, or contains control characters
    """
    # Strip leading/trailing whitespace
    stripped = v.strip()

    # Check if name is effectively empty after stripping
    if not stripped:
        raise ValueError("Name cannot be empty or whitespace-only")

    # Check length
    if len(stripped) > max_length:
        raise ValueError(f"Name cannot exceed {max_length} characters")

    # Check for forbidden control characters (null, tab, newline, etc.)
    import re

    forbidden_chars = re.compile(r"[\x00-\x1f\x7f]")
    if forbidden_chars.search(v):
        raise ValueError(
            "Name contains forbidden characters (control characters like null, tab, or newline)"
        )

    return stripped


class HouseholdCreate(BaseModel):
    """Schema for creating a new household.

    A household is the top-level organizational unit that groups members,
    vehicles, and properties together.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Svoboda Family",
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Household name (e.g., 'Svoboda Family')",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize household name."""
        return _validate_name(v, max_length=100)


class HouseholdUpdate(BaseModel):
    """Schema for updating an existing household.

    All fields are optional; only provided fields will be updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Svoboda-Smith Family",
            }
        }
    )

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Household name",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and sanitize household name for updates."""
        if v is None:
            return v
        return _validate_name(v, max_length=100)


class HouseholdResponse(BaseModel):
    """Schema for household response.

    Includes basic household information. Use nested endpoints or
    query parameters to include related members, vehicles, or properties.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Svoboda Family",
                "created_at": "2026-01-20T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique household identifier")
    name: str = Field(..., description="Household name")
    created_at: datetime = Field(..., description="Timestamp when household was created")


class HouseholdListResponse(BaseModel):
    """Schema for listing households.

    Returns a list of households with pagination metadata.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "name": "Svoboda Family",
                        "created_at": "2026-01-20T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[HouseholdResponse] = Field(..., description="List of households")
    total: int = Field(..., ge=0, description="Total number of households")


# =============================================================================
# Property Schemas
# =============================================================================


class PropertyCreate(BaseModel):
    """Schema for creating a new property.

    A property represents a physical location within a household
    (e.g., main house, beach house).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Main House",
                "address": "123 Main St, City, ST 12345",
                "timezone": "America/New_York",
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Property name (e.g., 'Main House')",
    )
    address: str | None = Field(
        None,
        max_length=500,
        description="Optional street address",
    )
    timezone: str = Field(
        default="UTC",
        max_length=50,
        description="Timezone for the property (IANA format)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize property name."""
        return _validate_name(v, max_length=100)


class PropertyUpdate(BaseModel):
    """Schema for updating an existing property.

    All fields are optional; only provided fields will be updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Main Residence",
                "timezone": "America/Chicago",
            }
        }
    )

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Property name",
    )
    address: str | None = Field(
        None,
        max_length=500,
        description="Street address",
    )
    timezone: str | None = Field(
        None,
        max_length=50,
        description="Timezone (IANA format)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and sanitize property name for updates."""
        if v is None:
            return v
        return _validate_name(v, max_length=100)


class PropertyResponse(BaseModel):
    """Schema for property response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "household_id": 1,
                "name": "Main House",
                "address": "123 Main St, City, ST 12345",
                "timezone": "America/New_York",
                "created_at": "2026-01-20T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique property identifier")
    household_id: int = Field(..., description="ID of the owning household")
    name: str = Field(..., description="Property name")
    address: str | None = Field(None, description="Street address")
    timezone: str = Field(..., description="Timezone (IANA format)")
    created_at: datetime = Field(..., description="Timestamp when property was created")


class PropertyListResponse(BaseModel):
    """Schema for listing properties."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "household_id": 1,
                        "name": "Main House",
                        "address": "123 Main St",
                        "timezone": "America/New_York",
                        "created_at": "2026-01-20T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[PropertyResponse] = Field(..., description="List of properties")
    total: int = Field(..., ge=0, description="Total number of properties")


# =============================================================================
# Area Schemas (for future use in Phase 6.2+)
# =============================================================================


class AreaCreate(BaseModel):
    """Schema for creating a new area.

    An area represents a logical zone within a property
    (e.g., front yard, garage, pool area).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Yard",
                "description": "Main entrance and lawn area",
                "color": "#10B981",
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Area name (e.g., 'Front Yard')",
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Optional longer description",
    )
    color: str = Field(
        default="#76B900",
        max_length=7,
        description="Hex color code for UI display",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize area name."""
        return _validate_name(v, max_length=100)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Validate hex color format."""
        import re

        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color (e.g., '#76B900')")
        return v.upper()


class AreaUpdate(BaseModel):
    """Schema for updating an existing area.

    All fields are optional; only provided fields will be updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Main Entrance",
                "color": "#3B82F6",
            }
        }
    )

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Area name",
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Description",
    )
    color: str | None = Field(
        None,
        max_length=7,
        description="Hex color code",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and sanitize area name for updates."""
        if v is None:
            return v
        return _validate_name(v, max_length=100)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        """Validate hex color format for updates."""
        if v is None:
            return v
        import re

        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color (e.g., '#76B900')")
        return v.upper()


class AreaResponse(BaseModel):
    """Schema for area response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "property_id": 1,
                "name": "Front Yard",
                "description": "Main entrance and lawn area",
                "color": "#10B981",
                "created_at": "2026-01-20T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique area identifier")
    property_id: int = Field(..., description="ID of the parent property")
    name: str = Field(..., description="Area name")
    description: str | None = Field(None, description="Description")
    color: str = Field(..., description="Hex color code for UI")
    created_at: datetime = Field(..., description="Timestamp when area was created")


class AreaListResponse(BaseModel):
    """Schema for listing areas."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "property_id": 1,
                        "name": "Front Yard",
                        "description": "Main entrance",
                        "color": "#10B981",
                        "created_at": "2026-01-20T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[AreaResponse] = Field(..., description="List of areas")
    total: int = Field(..., ge=0, description="Total number of areas")


# =============================================================================
# Camera Linking Schemas (NEM-3133: Phase 6.3)
# =============================================================================


class CameraLinkRequest(BaseModel):
    """Schema for linking a camera to an area.

    Used to establish the many-to-many relationship between areas and cameras.
    A camera can be linked to multiple areas, and an area can have multiple cameras.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
            }
        }
    )

    camera_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID of the camera to link to this area",
    )

    @field_validator("camera_id")
    @classmethod
    def validate_camera_id(cls, v: str) -> str:
        """Validate camera ID is not empty."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Camera ID cannot be empty or whitespace-only")
        return stripped


class CameraLinkResponse(BaseModel):
    """Schema for camera link/unlink response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "area_id": 1,
                "camera_id": "front_door",
                "linked": True,
            }
        }
    )

    area_id: int = Field(..., description="ID of the area")
    camera_id: str = Field(..., description="ID of the camera")
    linked: bool = Field(
        ..., description="Whether the camera is now linked (True) or unlinked (False)"
    )


class AreaCameraResponse(BaseModel):
    """Schema for camera info in area context (minimal camera info)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "front_door",
                "name": "Front Door Camera",
                "status": "online",
            }
        },
    )

    id: str = Field(..., description="Camera ID")
    name: str = Field(..., description="Camera name")
    status: str = Field(..., description="Camera status (online, offline, error, unknown)")


class AreaCamerasResponse(BaseModel):
    """Schema for listing cameras in an area."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "area_id": 1,
                "area_name": "Front Yard",
                "cameras": [
                    {
                        "id": "front_door",
                        "name": "Front Door Camera",
                        "status": "online",
                    }
                ],
                "count": 1,
            }
        }
    )

    area_id: int = Field(..., description="ID of the area")
    area_name: str = Field(..., description="Name of the area")
    cameras: list[AreaCameraResponse] = Field(..., description="List of cameras in this area")
    count: int = Field(..., ge=0, description="Number of cameras in this area")
