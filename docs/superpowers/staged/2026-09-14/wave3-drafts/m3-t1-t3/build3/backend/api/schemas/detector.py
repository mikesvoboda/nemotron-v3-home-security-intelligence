"""API schemas for detector management endpoints.

Pydantic models for request/response validation in the detector
switching API (NEM-3692).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DetectorInfoResponse(BaseModel):
    """Information about a registered detector."""

    detector_type: str = Field(
        ...,
        description="Unique identifier for the detector (e.g., 'yolo26', 'yolov8')",
        examples=["yolo26"],
    )
    display_name: str = Field(
        ...,
        description="Human-readable name for UI display",
        examples=["YOLO26"],
    )
    url: str = Field(
        ...,
        description="Base URL of the detector service",
        examples=["http://ai-yolo26:8095"],
    )
    enabled: bool = Field(
        ...,
        description="Whether this detector is available for use",
    )
    is_active: bool = Field(
        ...,
        description="Whether this is the currently active detector",
    )
    model_version: str | None = Field(
        None,
        description="Model version identifier",
        examples=["yolo26m", "yolov8n"],
    )
    description: str = Field(
        "",
        description="Description of the detector capabilities",
    )

    model_config = {"from_attributes": True}


class DetectorHealthResponse(BaseModel):
    """Health status of a detector."""

    detector_type: str = Field(
        ...,
        description="Identifier of the detector",
    )
    healthy: bool = Field(
        ...,
        description="Whether the detector is responding and healthy",
    )
    model_loaded: bool = Field(
        False,
        description="Whether the model is loaded in memory",
    )
    latency_ms: float | None = Field(
        None,
        description="Health check response time in milliseconds",
    )
    error_message: str | None = Field(
        None,
        description="Error message if unhealthy",
    )

    model_config = {"from_attributes": True}


class DetectorListResponse(BaseModel):
    """Response containing list of all registered detectors."""

    detectors: list[DetectorInfoResponse] = Field(
        ...,
        description="List of all registered detectors",
    )
    active_detector: str | None = Field(
        None,
        description="Type of the currently active detector",
    )
    health_checked: bool = Field(
        False,
        description="Whether health status was included in the response",
    )


class SwitchDetectorRequest(BaseModel):
    """Request to switch the active detector."""

    detector_type: str = Field(
        ...,
        description="Type identifier of the detector to switch to",
        examples=["yolo26", "yolov8"],
    )
    force: bool = Field(
        False,
        description="Skip health check validation when switching",
    )


class SwitchDetectorResponse(BaseModel):
    """Response after switching detectors."""

    detector_type: str = Field(
        ...,
        description="Type of the now-active detector",
    )
    display_name: str = Field(
        ...,
        description="Human-readable name of the detector",
    )
    message: str = Field(
        ...,
        description="Status message about the switch operation",
    )
    healthy: bool = Field(
        True,
        description="Health status of the new active detector",
    )
