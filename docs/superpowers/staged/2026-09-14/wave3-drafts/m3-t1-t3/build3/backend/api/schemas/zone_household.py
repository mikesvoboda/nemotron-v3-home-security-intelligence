"""Pydantic schemas for zone-household linkage API endpoints.

These schemas define the request/response models for the zone-household
configuration endpoints that enable zone-based access control.

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TrustLevelResult(str, Enum):
    """Trust level result from zone access check.

    These values indicate the level of trust an entity has in a specific zone:
    - FULL: Entity is the zone owner - full trust, never alert
    - PARTIAL: Entity is allowed member/vehicle - reduced alert severity
    - MONITOR: Entity is scheduled for access at current time - log only
    - NONE: Entity has no special trust in this zone
    """

    FULL = "full"
    PARTIAL = "partial"
    MONITOR = "monitor"
    NONE = "none"


class AccessSchedule(BaseModel):
    """Schema for time-based access schedule configuration.

    Allows defining when specific members have access to a zone using
    cron-style expressions for flexible scheduling.

    Example:
        {
            "member_ids": [1, 2, 3],
            "cron_expression": "0 9-17 * * 1-5",  # Weekdays 9am-5pm
            "description": "Service workers during business hours"
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "member_ids": [1, 2],
                "cron_expression": "0 9-17 * * 1-5",
                "description": "Business hours access",
            }
        }
    )

    member_ids: list[int] = Field(
        ...,
        description="List of household member IDs this schedule applies to",
        min_length=1,
    )
    cron_expression: str = Field(
        ...,
        description="Cron expression defining when access is granted (minute hour day month weekday)",
        min_length=1,
    )
    description: str | None = Field(
        None,
        description="Optional human-readable description of the schedule",
        max_length=255,
    )


class ZoneHouseholdConfigCreate(BaseModel):
    """Schema for creating a zone household configuration.

    Used when initially configuring household linkage for a zone.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "owner_id": 1,
                "allowed_member_ids": [2, 3],
                "allowed_vehicle_ids": [1, 2],
                "access_schedules": [
                    {
                        "member_ids": [4, 5],
                        "cron_expression": "0 9-17 * * 1-5",
                        "description": "Weekday daytime access",
                    }
                ],
            }
        }
    )

    owner_id: int | None = Field(
        None,
        description="ID of the household member who owns this zone (full trust)",
    )
    allowed_member_ids: list[int] = Field(
        default_factory=list,
        description="IDs of household members allowed in this zone (partial trust)",
    )
    allowed_vehicle_ids: list[int] = Field(
        default_factory=list,
        description="IDs of registered vehicles allowed in this zone (partial trust)",
    )
    access_schedules: list[AccessSchedule] = Field(
        default_factory=list,
        description="Time-based access schedules for specific members",
    )


class ZoneHouseholdConfigUpdate(BaseModel):
    """Schema for updating a zone household configuration.

    All fields are optional - only provided fields will be updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "owner_id": 2,
                "allowed_member_ids": [3, 4, 5],
            }
        }
    )

    owner_id: int | None = Field(
        default=None,
        description="ID of the household member who owns this zone",
    )
    allowed_member_ids: list[int] | None = Field(
        default=None,
        description="IDs of household members allowed in this zone",
    )
    allowed_vehicle_ids: list[int] | None = Field(
        default=None,
        description="IDs of registered vehicles allowed in this zone",
    )
    access_schedules: list[AccessSchedule] | None = Field(
        default=None,
        description="Time-based access schedules for specific members",
    )


class ZoneHouseholdConfigResponse(BaseModel):
    """Schema for zone household configuration response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "zone_id": "550e8400-e29b-41d4-a716-446655440000",
                "owner_id": 1,
                "allowed_member_ids": [2, 3],
                "allowed_vehicle_ids": [1],
                "access_schedules": [
                    {
                        "member_ids": [4],
                        "cron_expression": "0 9-17 * * 1-5",
                        "description": "Weekday access",
                    }
                ],
                "created_at": "2026-01-21T10:00:00Z",
                "updated_at": "2026-01-21T12:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Configuration ID")
    zone_id: str = Field(..., description="ID of the zone this configuration applies to")
    owner_id: int | None = Field(
        None,
        description="ID of the zone owner (household member with full trust)",
    )
    allowed_member_ids: list[int] = Field(
        ...,
        description="IDs of household members allowed in this zone",
    )
    allowed_vehicle_ids: list[int] = Field(
        ...,
        description="IDs of registered vehicles allowed in this zone",
    )
    access_schedules: list[dict] = Field(
        ...,
        description="Time-based access schedules",
    )
    created_at: datetime = Field(..., description="When the configuration was created")
    updated_at: datetime = Field(..., description="When the configuration was last updated")


class TrustCheckRequest(BaseModel):
    """Schema for trust check request body (optional, for specifying time)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "at_time": "2026-01-21T14:30:00Z",
            }
        }
    )

    at_time: datetime | None = Field(
        None,
        description="Time to check access for (defaults to current time if not specified)",
    )


class TrustCheckResponse(BaseModel):
    """Schema for trust check response.

    Indicates the trust level an entity has in a specific zone.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": "550e8400-e29b-41d4-a716-446655440000",
                "entity_id": 1,
                "entity_type": "member",
                "trust_level": "full",
                "reason": "Entity is the zone owner",
            }
        }
    )

    zone_id: str = Field(..., description="ID of the zone")
    entity_id: int = Field(..., description="ID of the entity being checked")
    entity_type: str = Field(
        ...,
        description="Type of entity ('member' or 'vehicle')",
    )
    trust_level: TrustLevelResult = Field(
        ...,
        description="Trust level result (full, partial, monitor, none)",
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of the trust level",
    )
