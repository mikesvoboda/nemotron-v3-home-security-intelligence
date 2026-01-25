"""Pydantic schemas for SystemSetting Key-Value Store API (NEM-3638).

This module provides schemas for the system settings API endpoints that expose
the SystemSetting model as a key-value store for application-wide configuration.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SystemSettingResponse(BaseModel):
    """Response schema for a system setting.

    Represents a single key-value pair from the SystemSetting table.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "key": "default_gpu_strategy",
                "value": {"strategy": "vram_based", "fallback": "balanced"},
                "updated_at": "2026-01-25T12:00:00Z",
            }
        },
    )

    key: str = Field(..., max_length=64, description="Setting key (primary key)")
    value: dict[str, Any] = Field(..., description="Setting value as JSON object")
    updated_at: datetime = Field(..., description="Last update timestamp")


class SystemSettingUpdate(BaseModel):
    """Request schema for updating a system setting.

    The value is a flexible JSON object that can store any configuration.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "value": {"strategy": "vram_based", "fallback": "balanced"},
            }
        },
    )

    value: dict[str, Any] = Field(
        ...,
        description="New value for the setting (JSON object). "
        "Replaces the existing value entirely (not merged).",
    )


class SystemSettingCreate(BaseModel):
    """Request schema for creating a new system setting.

    Used when a setting does not exist and needs to be created.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "custom_setting",
                "value": {"enabled": True, "threshold": 0.5},
            }
        },
    )

    key: str = Field(
        ...,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Setting key. Must be lowercase alphanumeric with underscores, "
        "starting with a letter. Max 64 characters.",
    )
    value: dict[str, Any] = Field(..., description="Initial value for the setting (JSON object)")


class SystemSettingListResponse(BaseModel):
    """Response schema for listing all system settings."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "key": "default_gpu_strategy",
                        "value": {"strategy": "vram_based"},
                        "updated_at": "2026-01-25T12:00:00Z",
                    },
                    {
                        "key": "notification_defaults",
                        "value": {"email": True, "push": False},
                        "updated_at": "2026-01-25T11:00:00Z",
                    },
                ],
                "total": 2,
            }
        },
    )

    items: list[SystemSettingResponse] = Field(..., description="List of system settings")
    total: int = Field(..., description="Total number of settings")
