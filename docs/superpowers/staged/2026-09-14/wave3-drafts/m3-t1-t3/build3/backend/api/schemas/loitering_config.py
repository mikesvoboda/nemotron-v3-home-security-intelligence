"""Pydantic schemas for loitering configuration endpoints.

This module defines schemas for:
- LoiteringConfigUpdate: Request to update loitering configuration
- LoiteringConfigResponse: Response with current loitering configuration
"""

from pydantic import BaseModel, ConfigDict, Field


class LoiteringConfigUpdate(BaseModel):
    """Request to update loitering configuration for a polygon zone.

    Loitering detection identifies objects that remain in a zone longer than
    the configured threshold. This can be used to detect suspicious behavior
    such as someone lingering near a restricted area.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "threshold_seconds": 300,
                "alert_enabled": True,
            }
        }
    )

    threshold_seconds: int = Field(
        ge=0,
        le=3600,
        description="Loitering threshold in seconds (0-3600). "
        "Objects dwelling longer than this trigger alerts.",
    )
    alert_enabled: bool = Field(
        default=True,
        description="Whether to generate alerts when threshold exceeded",
    )


class LoiteringConfigResponse(BaseModel):
    """Response with current loitering configuration for a polygon zone.

    Returns the zone's loitering settings including the threshold and
    whether alerts are enabled.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "zone_name": "Backyard",
                "threshold_seconds": 300,
                "alert_enabled": True,
            }
        },
    )

    zone_id: int = Field(..., description="ID of the polygon zone")
    zone_name: str = Field(..., description="Human-readable name of the zone")
    threshold_seconds: int = Field(
        ...,
        ge=0,
        le=3600,
        description="Loitering threshold in seconds (0-3600)",
    )
    alert_enabled: bool = Field(
        ...,
        description="Whether alerts are generated when threshold exceeded",
    )


# Export all schemas
__all__ = [
    "LoiteringConfigResponse",
    "LoiteringConfigUpdate",
]
