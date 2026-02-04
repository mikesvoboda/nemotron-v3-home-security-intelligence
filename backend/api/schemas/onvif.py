"""ONVIF Pydantic schemas for camera discovery and PTZ control.

NEM-4207: Schemas for ONVIF device discovery, configuration, and PTZ operations.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# URL validation patterns
_HTTP_URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_RTSP_URL_PATTERN = re.compile(r"^rtsps?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def _validate_http_url(v: str) -> str:
    """Validate HTTP(S) URL format."""
    if not _HTTP_URL_PATTERN.match(v):
        raise ValueError("Invalid device_url format - must be a valid HTTP(S) URL")
    return v


def _validate_rtsp_url(v: str | None) -> str | None:
    """Validate RTSP URL format if provided."""
    if v is None:
        return v
    if not _RTSP_URL_PATTERN.match(v):
        raise ValueError("Invalid rtsp_url format - must be a valid RTSP URL")
    return v


class OnvifDiscoveryRequest(BaseModel):
    """Request schema for ONVIF device discovery.

    NEM-4207: Defines the network subnet to scan and timeout for WS-Discovery.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subnet": "192.168.1.0/24",
                "timeout": 10,
            }
        }
    )

    subnet: str = Field(
        ...,
        min_length=1,
        description="Network subnet in CIDR notation (e.g., '192.168.1.0/24')",
    )
    timeout: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Discovery timeout in seconds (1-300)",
    )

    @field_validator("subnet")
    @classmethod
    def validate_subnet(cls, v: str) -> str:
        """Validate subnet format as valid CIDR notation."""
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid subnet format: {e}") from e
        return v


class OnvifDiscoveryResult(BaseModel):
    """Response schema for a discovered ONVIF device.

    NEM-4207: Contains device information from WS-Discovery response.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_url": "http://192.168.1.100/onvif/device_service",
                "manufacturer": "Hikvision",
                "model": "DS-2CD2032-I",
                "firmware_version": "5.4.5",
                "serial_number": "SN001234567890",
                "hardware_id": "HW-001",
            }
        }
    )

    device_url: str = Field(
        ...,
        description="ONVIF device service URL",
    )
    manufacturer: str = Field(
        ...,
        description="Device manufacturer name",
    )
    model: str = Field(
        ...,
        description="Device model name",
    )
    firmware_version: str | None = Field(
        default=None,
        description="Device firmware version",
    )
    serial_number: str | None = Field(
        default=None,
        description="Device serial number",
    )
    hardware_id: str | None = Field(
        default=None,
        description="Device hardware ID",
    )

    @field_validator("device_url")
    @classmethod
    def validate_device_url(cls, v: str) -> str:
        """Validate device URL format."""
        return _validate_http_url(v)


class OnvifDeviceConfig(BaseModel):
    """Configuration schema for connecting to an ONVIF device.

    NEM-4207: Stores credentials and connection details for ONVIF devices.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_url": "http://192.168.1.100/onvif/device_service",
                "username": "admin",
                "password": "password123",  # pragma: allowlist secret
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
            }
        }
    )

    device_url: str = Field(
        ...,
        description="ONVIF device service URL",
    )
    username: str = Field(
        ...,
        min_length=1,
        description="ONVIF device username",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="ONVIF device password",
    )
    rtsp_url: str | None = Field(
        default=None,
        description="RTSP stream URL (if known)",
    )

    @field_validator("device_url")
    @classmethod
    def validate_device_url(cls, v: str) -> str:
        """Validate device URL format."""
        return _validate_http_url(v)

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: str | None) -> str | None:
        """Validate RTSP URL format if provided."""
        return _validate_rtsp_url(v)


class PTZCommand(BaseModel):
    """PTZ (Pan-Tilt-Zoom) command schema.

    NEM-4207: Defines PTZ movement commands with value and speed parameters.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "command": "pan",
                "value": 0.5,
                "speed": 1.0,
            }
        }
    )

    command: Literal["pan", "tilt", "zoom", "stop"] = Field(
        ...,
        description="PTZ command type (pan, tilt, zoom, or stop)",
    )
    value: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Movement value (-1.0 to 1.0)",
    )
    speed: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Movement speed (0.0 to 1.0)",
    )


class PTZPreset(BaseModel):
    """PTZ preset position schema.

    NEM-4207: Represents a saved PTZ preset position.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "preset_1",
                "name": "Front Door View",
            }
        }
    )

    token: str = Field(
        ...,
        min_length=1,
        description="Unique preset token",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Preset name",
    )

    @field_validator("token", "name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading and trailing whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Value cannot be empty or whitespace-only")
        return stripped


# =============================================================================
# Response Schemas (NEM-5000, NEM-5001)
# =============================================================================


class OnvifDiscoveryResponse(BaseModel):
    """Response schema for ONVIF device discovery.

    NEM-5000: Typed response replacing dict[str, Any] return type.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "devices": [
                    {
                        "device_url": "http://192.168.1.100/onvif/device_service",
                        "manufacturer": "Hikvision",
                        "model": "DS-2CD2032-I",
                    }
                ],
                "count": 1,
            }
        }
    )

    devices: list[OnvifDiscoveryResult] = Field(
        default_factory=list,
        description="List of discovered ONVIF devices",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of devices discovered",
    )


class PTZCommandResponse(BaseModel):
    """Response schema for PTZ command execution.

    NEM-5000: Typed response replacing dict[str, Any] return type.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "command": "pan",
                "value": 0.5,
                "speed": 1.0,
            }
        }
    )

    success: bool = Field(
        ...,
        description="Whether the command was executed successfully",
    )
    command: str = Field(
        ...,
        description="The command type that was executed",
    )
    value: float = Field(
        default=0.0,
        description="The movement value used (-1.0 to 1.0)",
    )
    speed: float = Field(
        default=0.0,
        description="The speed used (0.0 to 1.0)",
    )


class PTZStopResponse(BaseModel):
    """Response schema for PTZ stop command.

    NEM-5000: Typed response replacing dict[str, Any] return type.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "command": "stop",
            }
        }
    )

    success: bool = Field(
        ...,
        description="Whether the stop command was executed successfully",
    )
    command: Literal["stop"] = Field(
        default="stop",
        description="The command type (always 'stop')",
    )


class PTZPresetsResponse(BaseModel):
    """Response schema for listing PTZ presets.

    NEM-5000: Typed response replacing dict[str, Any] return type.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "presets": [
                    {"token": "preset_1", "name": "Front Door View"},
                    {"token": "preset_2", "name": "Backyard"},
                ],
                "count": 2,
            }
        }
    )

    presets: list[PTZPreset] = Field(
        default_factory=list,
        description="List of available PTZ presets",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of presets available",
    )


class PTZGotoPresetResponse(BaseModel):
    """Response schema for navigating to a PTZ preset.

    NEM-5000: Typed response replacing dict[str, Any] return type.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "preset_token": "preset_1",
            }
        }
    )

    success: bool = Field(
        ...,
        description="Whether navigation to the preset started successfully",
    )
    preset_token: str = Field(
        ...,
        description="The preset token that was used",
    )


class OnvifCapabilitiesResponse(BaseModel):
    """Response schema for ONVIF device capabilities.

    NEM-5000: Typed response replacing dict[str, Any] return type.
    Contains device info and capability flags from ONVIF GetCapabilities.
    """

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields from ONVIF capabilities
        json_schema_extra={
            "example": {
                "manufacturer": "Hikvision",
                "model": "DS-2CD2032-I",
                "firmware_version": "5.4.5",
                "serial_number": "SN001234567890",
                "ptz_supported": True,
                "media_supported": True,
                "analytics_supported": False,
            }
        },
    )

    manufacturer: str | None = Field(
        default=None,
        description="Device manufacturer name",
    )
    model: str | None = Field(
        default=None,
        description="Device model name",
    )
    firmware_version: str | None = Field(
        default=None,
        description="Device firmware version",
    )
    serial_number: str | None = Field(
        default=None,
        description="Device serial number",
    )
    hardware_id: str | None = Field(
        default=None,
        description="Device hardware ID",
    )
    ptz_supported: bool = Field(
        default=False,
        description="Whether PTZ control is supported",
    )
    media_supported: bool = Field(
        default=False,
        description="Whether media streaming is supported",
    )
    analytics_supported: bool = Field(
        default=False,
        description="Whether video analytics is supported",
    )
