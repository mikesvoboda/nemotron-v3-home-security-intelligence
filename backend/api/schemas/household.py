"""Pydantic schemas for household API endpoints.

Implements NEM-3018: Build API endpoints for household member and vehicle management.

These schemas enable tracking of known household members and vehicles to reduce
false positives in security monitoring.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.household import MemberRole, TrustLevel, VehicleType

# =============================================================================
# Household Member Schemas
# =============================================================================


class HouseholdMemberCreate(BaseModel):
    """Schema for creating a new household member."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "role": "resident",
                "trusted_level": "full",
                "typical_schedule": {"weekdays": "9-17", "weekends": "flexible"},
                "notes": "Works from home on Fridays",
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name for the person",
    )
    role: MemberRole = Field(
        ...,
        description="Role/relationship of the person to the household",
    )
    trusted_level: TrustLevel = Field(
        ...,
        description="Trust level determining alert suppression behavior",
    )
    typical_schedule: dict | None = Field(
        default=None,
        description="JSON object defining expected presence schedule",
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Free-form notes about the person",
    )


class HouseholdMemberUpdate(BaseModel):
    """Schema for updating an existing household member."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe Updated",
                "trusted_level": "partial",
                "notes": "Now works remotely full-time",
            }
        }
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Display name for the person",
    )
    role: MemberRole | None = Field(
        default=None,
        description="Role/relationship of the person to the household",
    )
    trusted_level: TrustLevel | None = Field(
        default=None,
        description="Trust level determining alert suppression behavior",
    )
    typical_schedule: dict | None = Field(
        default=None,
        description="JSON object defining expected presence schedule",
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Free-form notes about the person",
    )


class HouseholdMemberResponse(BaseModel):
    """Schema for household member response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "John Doe",
                "role": "resident",
                "trusted_level": "full",
                "typical_schedule": {"weekdays": "9-17"},
                "notes": "Works from home on Fridays",
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-01T12:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique identifier for the household member")
    name: str = Field(..., description="Display name for the person")
    role: MemberRole = Field(..., description="Role/relationship to the household")
    trusted_level: TrustLevel = Field(..., description="Trust level for alert behavior")
    typical_schedule: dict | None = Field(None, description="Expected presence schedule")
    notes: str | None = Field(None, description="Notes about the person")
    created_at: datetime = Field(..., description="When the member was created")
    updated_at: datetime = Field(..., description="When the member was last updated")


# =============================================================================
# Registered Vehicle Schemas
# =============================================================================


class RegisteredVehicleCreate(BaseModel):
    """Schema for creating a new registered vehicle."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Silver Tesla Model 3",
                "license_plate": "ABC123",
                "vehicle_type": "car",
                "color": "Silver",
                "owner_id": 1,
                "trusted": True,
            }
        }
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable description (e.g., 'Silver Tesla Model 3')",
    )
    license_plate: str | None = Field(
        default=None,
        max_length=20,
        description="License plate number",
    )
    vehicle_type: VehicleType = Field(
        ...,
        description="Type/category of the vehicle",
    )
    color: str | None = Field(
        default=None,
        max_length=50,
        description="Color description",
    )
    owner_id: int | None = Field(
        default=None,
        description="ID of the vehicle owner (HouseholdMember)",
    )
    trusted: bool = Field(
        default=True,
        description="Whether this vehicle should suppress alerts",
    )


class RegisteredVehicleUpdate(BaseModel):
    """Schema for updating an existing registered vehicle."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Updated Tesla Description",
                "license_plate": "NEW456",
                "trusted": False,
            }
        }
    )

    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Human-readable description",
    )
    license_plate: str | None = Field(
        default=None,
        max_length=20,
        description="License plate number",
    )
    vehicle_type: VehicleType | None = Field(
        default=None,
        description="Type/category of the vehicle",
    )
    color: str | None = Field(
        default=None,
        max_length=50,
        description="Color description",
    )
    owner_id: int | None = Field(
        default=None,
        description="ID of the vehicle owner (HouseholdMember)",
    )
    trusted: bool | None = Field(
        default=None,
        description="Whether this vehicle should suppress alerts",
    )


class RegisteredVehicleResponse(BaseModel):
    """Schema for registered vehicle response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "description": "Silver Tesla Model 3",
                "license_plate": "ABC123",
                "vehicle_type": "car",
                "color": "Silver",
                "owner_id": 1,
                "trusted": True,
                "created_at": "2025-01-01T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique identifier for the vehicle")
    description: str = Field(..., description="Human-readable description")
    license_plate: str | None = Field(None, description="License plate number")
    vehicle_type: VehicleType = Field(..., description="Type of vehicle")
    color: str | None = Field(None, description="Color description")
    owner_id: int | None = Field(None, description="ID of the vehicle owner")
    trusted: bool = Field(..., description="Whether vehicle suppresses alerts")
    created_at: datetime = Field(..., description="When the vehicle was registered")


# =============================================================================
# Embedding Schemas
# =============================================================================


class AddEmbeddingRequest(BaseModel):
    """Schema for adding a person embedding from an event."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 100,
                "confidence": 0.95,
            }
        }
    )

    event_id: int = Field(
        ...,
        description="ID of the event to extract embedding from",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Reliability score for this embedding (0-1)",
    )


class PersonEmbeddingResponse(BaseModel):
    """Schema for person embedding response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "member_id": 1,
                "source_event_id": 100,
                "confidence": 0.95,
                "created_at": "2025-01-01T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique identifier for the embedding")
    member_id: int = Field(..., description="ID of the associated household member")
    source_event_id: int | None = Field(None, description="Event ID where embedding was captured")
    confidence: float = Field(..., description="Reliability score (0-1)")
    created_at: datetime = Field(..., description="When the embedding was created")
