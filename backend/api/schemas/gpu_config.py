"""Pydantic schemas for GPU configuration API endpoints.

This module provides request/response schemas for the GPU configuration
API, enabling multi-GPU support with manual and auto-assignment strategies.

See docs/plans/2025-01-23-multi-gpu-support-design.md for design details.
"""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, Field


class GpuAssignmentStrategy(StrEnum):
    """GPU assignment strategies for AI services.

    Strategies determine how models are distributed across GPUs:
    - MANUAL: User controls each assignment explicitly
    - VRAM_BASED: Largest models assigned to GPU with most VRAM
    - LATENCY_OPTIMIZED: Critical path models on fastest GPU
    - ISOLATION_FIRST: LLM gets dedicated GPU, others share
    - BALANCED: Distribute VRAM evenly across GPUs
    """

    MANUAL = auto()
    VRAM_BASED = auto()
    LATENCY_OPTIMIZED = auto()
    ISOLATION_FIRST = auto()
    BALANCED = auto()


class GpuDeviceResponse(BaseModel):
    """Response schema for a detected GPU device.

    Contains metadata about a GPU including VRAM capacity
    and current utilization.
    """

    index: int = Field(
        ...,
        description="GPU index (0-based)",
        ge=0,
    )
    name: str = Field(
        ...,
        description="GPU name (e.g., 'NVIDIA RTX A5500')",
    )
    vram_total_mb: int = Field(
        ...,
        description="Total VRAM in megabytes",
        ge=0,
    )
    vram_used_mb: int = Field(
        ...,
        description="Currently used VRAM in megabytes",
        ge=0,
    )
    compute_capability: str | None = Field(
        None,
        description="CUDA compute capability (e.g., '8.6')",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "index": 0,
                "name": "RTX A5500",
                "vram_total_mb": 24564,
                "vram_used_mb": 19304,
                "compute_capability": "8.6",
            }
        }
    )


class GpuDevicesResponse(BaseModel):
    """Response schema for listing detected GPUs."""

    gpus: list[GpuDeviceResponse] = Field(
        ...,
        description="List of detected GPU devices",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "gpus": [
                    {
                        "index": 0,
                        "name": "RTX A5500",
                        "vram_total_mb": 24564,
                        "vram_used_mb": 19304,
                        "compute_capability": "8.6",
                    },
                    {
                        "index": 1,
                        "name": "RTX A400",
                        "vram_total_mb": 4094,
                        "vram_used_mb": 329,
                        "compute_capability": "8.6",
                    },
                ]
            }
        }
    )


class GpuAssignment(BaseModel):
    """Schema for a single service-to-GPU assignment.

    Maps an AI service to a specific GPU with optional VRAM budget override.
    """

    service: str = Field(
        ...,
        description="Service name (e.g., 'ai-llm', 'ai-yolo26')",
        min_length=1,
        max_length=64,
    )
    gpu_index: int | None = Field(
        None,
        description="Target GPU index (null for auto-assign)",
        ge=0,
    )
    vram_budget_override: float | None = Field(
        None,
        description="Override VRAM budget in GB (for services with dynamic VRAM needs)",
        ge=0.0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "ai-enrichment",
                "gpu_index": 1,
                "vram_budget_override": 3.5,
            }
        }
    )


class GpuConfigResponse(BaseModel):
    """Response schema for current GPU configuration.

    Returns the current assignment strategy and all service-to-GPU mappings.
    """

    strategy: GpuAssignmentStrategy = Field(
        ...,
        description="Current GPU assignment strategy",
    )
    assignments: list[GpuAssignment] = Field(
        ...,
        description="List of service-to-GPU assignments",
    )
    updated_at: datetime | None = Field(
        None,
        description="Timestamp of last configuration update",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy": "manual",
                "assignments": [
                    {"service": "ai-llm", "gpu_index": 0, "vram_budget_override": None},
                    {"service": "ai-yolo26", "gpu_index": 0, "vram_budget_override": None},
                    {"service": "ai-enrichment", "gpu_index": 1, "vram_budget_override": 3.5},
                ],
                "updated_at": "2026-01-23T10:30:00Z",
            }
        }
    )


class GpuConfigUpdateRequest(BaseModel):
    """Request schema for updating GPU configuration.

    Allows updating the assignment strategy and/or individual assignments.
    """

    strategy: GpuAssignmentStrategy | None = Field(
        None,
        description="GPU assignment strategy (null to keep current)",
    )
    assignments: list[GpuAssignment] | None = Field(
        None,
        description="Service-to-GPU assignments (null to keep current)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy": "manual",
                "assignments": [
                    {"service": "ai-llm", "gpu_index": 0},
                    {"service": "ai-yolo26", "gpu_index": 0},
                    {"service": "ai-enrichment", "gpu_index": 1, "vram_budget_override": 3.5},
                ],
            }
        }
    )


class GpuConfigUpdateResponse(BaseModel):
    """Response schema for GPU configuration update.

    Returns success status and any warnings about the configuration.
    """

    success: bool = Field(
        ...,
        description="Whether the configuration was saved successfully",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about the configuration (e.g., VRAM overages)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "warnings": [
                    "ai-enrichment VRAM budget (6.8 GB) exceeds GPU 1 (4 GB). Auto-adjusted to 3.5 GB."
                ],
            }
        }
    )


class ServiceStatus(BaseModel):
    """Schema for service status after GPU config apply.

    Reports the status of a service after applying GPU configuration changes.
    """

    service: str = Field(
        ...,
        description="Service name",
    )
    status: str = Field(
        ...,
        description="Service status (running, starting, stopped, error)",
    )
    message: str | None = Field(
        None,
        description="Optional status message or error details",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "ai-llm",
                "status": "running",
                "message": None,
            }
        }
    )


class ServiceHealthStatus(BaseModel):
    """Schema for service health status including GPU assignment.

    Provides comprehensive service health information for the GPU settings UI,
    including container status, health check result, and GPU assignment.
    """

    name: str = Field(
        ...,
        description="Service name (e.g., 'ai-llm')",
    )
    status: str = Field(
        ...,
        description="Container status (running, stopped, etc.)",
    )
    health: str = Field(
        ...,
        description="Health check result (healthy, unhealthy, unknown)",
    )
    gpu_index: int | None = Field(
        None,
        description="Assigned GPU index",
    )
    restart_status: str | None = Field(
        None,
        description="Restart status if currently restarting (pending, completed)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "ai-llm",
                "status": "running",
                "health": "healthy",
                "gpu_index": 0,
                "restart_status": None,
            }
        }
    )


class ServiceHealthResponse(BaseModel):
    """Response schema for AI service health status.

    Returns health status of all AI services including GPU assignments.
    """

    services: list[ServiceHealthStatus] = Field(
        ...,
        description="Status of all AI services",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "services": [
                    {
                        "name": "ai-llm",
                        "status": "running",
                        "health": "healthy",
                        "gpu_index": 0,
                        "restart_status": None,
                    },
                    {
                        "name": "ai-yolo26",
                        "status": "running",
                        "health": "healthy",
                        "gpu_index": 1,
                        "restart_status": None,
                    },
                ]
            }
        }
    )


class AiServiceInfo(BaseModel):
    """Information about an AI service for GPU assignment.

    Provides service metadata including VRAM requirements, enabling
    the frontend to dynamically build the assignment UI.
    """

    name: str = Field(
        ...,
        description="Service name (e.g., 'ai-llm')",
    )
    display_name: str = Field(
        ...,
        description="Human-readable display name",
    )
    vram_required_mb: int = Field(
        ...,
        description="VRAM requirement in megabytes",
        ge=0,
    )
    vram_required_gb: float = Field(
        ...,
        description="VRAM requirement in gigabytes",
        ge=0.0,
    )
    description: str | None = Field(
        None,
        description="Service description",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "ai-llm",
                "display_name": "LLM (Nemotron)",
                "vram_required_mb": 8192,
                "vram_required_gb": 8.0,
                "description": "Nemotron LLM for risk analysis and enrichment",
            }
        }
    )


class AiServicesResponse(BaseModel):
    """Response schema for listing available AI services.

    Returns all AI services with their VRAM requirements for GPU assignment.
    """

    services: list[AiServiceInfo] = Field(
        ...,
        description="List of available AI services",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "services": [
                    {
                        "name": "ai-llm",
                        "display_name": "LLM (Nemotron)",
                        "vram_required_mb": 8192,
                        "vram_required_gb": 8.0,
                        "description": "Nemotron LLM for risk analysis and enrichment",
                    },
                    {
                        "name": "ai-yolo26",
                        "display_name": "Object Detector",
                        "vram_required_mb": 2048,
                        "vram_required_gb": 2.0,
                        "description": "YOLO26 real-time object detection",
                    },
                ]
            }
        }
    )


class GpuApplyResponse(BaseModel):
    """Response schema for applying GPU configuration.

    Returns the result of applying GPU configuration changes,
    including which services were restarted and any warnings.
    """

    success: bool = Field(
        ...,
        description="Whether the configuration was applied successfully",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about the configuration",
    )
    restarted_services: list[str] = Field(
        default_factory=list,
        description="Services that were restarted to apply changes",
    )
    service_statuses: list[ServiceStatus] = Field(
        default_factory=list,
        description="Status of each affected service after apply",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "warnings": [],
                "restarted_services": ["ai-enrichment"],
                "service_statuses": [
                    {"service": "ai-enrichment", "status": "starting", "message": None}
                ],
            }
        }
    )


class GpuConfigStatusResponse(BaseModel):
    """Response schema for GPU configuration apply status.

    Returns the current status of a GPU configuration apply operation.
    """

    in_progress: bool = Field(
        ...,
        description="Whether an apply operation is currently in progress",
    )
    services_pending: list[str] = Field(
        default_factory=list,
        description="Services still pending restart",
    )
    services_completed: list[str] = Field(
        default_factory=list,
        description="Services that have completed restart",
    )
    service_statuses: list[ServiceStatus] = Field(
        default_factory=list,
        description="Current status of all affected services",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "in_progress": False,
                "services_pending": [],
                "services_completed": ["ai-enrichment"],
                "service_statuses": [
                    {"service": "ai-enrichment", "status": "running", "message": None}
                ],
            }
        }
    )


class GpuConfigPreviewResponse(BaseModel):
    """Response schema for previewing auto-assignment.

    Returns the proposed assignments for a given strategy without applying.
    """

    strategy: GpuAssignmentStrategy = Field(
        ...,
        description="Strategy used for preview",
    )
    proposed_assignments: list[GpuAssignment] = Field(
        ...,
        description="Proposed service-to-GPU assignments",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about the proposed configuration",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy": "vram_based",
                "proposed_assignments": [
                    {"service": "ai-llm", "gpu_index": 0, "vram_budget_override": None},
                    {"service": "ai-yolo26", "gpu_index": 0, "vram_budget_override": None},
                    {"service": "ai-enrichment", "gpu_index": 1, "vram_budget_override": 3.5},
                ],
                "warnings": [
                    "ai-enrichment VRAM budget (6.8 GB) exceeds GPU 1 (4 GB). Suggested budget: 3.5 GB."
                ],
            }
        }
    )


# Export all schemas
__all__ = [
    "AiServiceInfo",
    "AiServicesResponse",
    "GpuApplyResponse",
    "GpuAssignment",
    "GpuAssignmentStrategy",
    "GpuConfigPreviewResponse",
    "GpuConfigResponse",
    "GpuConfigStatusResponse",
    "GpuConfigUpdateRequest",
    "GpuConfigUpdateResponse",
    "GpuDeviceResponse",
    "GpuDevicesResponse",
    "ServiceHealthResponse",
    "ServiceHealthStatus",
    "ServiceStatus",
]
