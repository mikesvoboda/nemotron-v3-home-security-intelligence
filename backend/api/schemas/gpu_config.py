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
        from_attributes=True,
        json_schema_extra={
            "example": {
                "index": 0,
                "name": "RTX A5500",
                "vram_total_mb": 24564,
                "vram_used_mb": 19304,
                "compute_capability": "8.6",
            }
        },
    )


class GpuDevicesResponse(BaseModel):
    """Response schema for listing detected GPUs."""

    gpus: list[GpuDeviceResponse] = Field(
        ...,
        description="List of detected GPU devices",
    )

    model_config = ConfigDict(
        from_attributes=True,
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
        },
    )


class GpuAssignment(BaseModel):
    """Schema for a single service-to-GPU assignment.

    Maps an AI service to a specific GPU with optional VRAM budget override
    and affinity constraints.

    Affinity Constraints (NEM-4944):
    - exclusive_gpu: If True, service requires a dedicated GPU (no sharing)
    - priority_weight: Priority for auto-assignment (higher = more important, 1-100)
    - incompatible_with: List of services that cannot share the same GPU
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
    # Affinity constraints (NEM-4944)
    exclusive_gpu: bool = Field(
        default=False,
        description="If True, service requires a dedicated GPU (no sharing with other services)",
    )
    priority_weight: int = Field(
        default=50,
        description="Priority for auto-assignment algorithms (1-100, higher = more important)",
        ge=1,
        le=100,
    )
    incompatible_with: list[str] | None = Field(
        default=None,
        description="List of service names that cannot share the same GPU with this service",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "service": "ai-enrichment",
                "gpu_index": 1,
                "vram_budget_override": 3.5,
                "exclusive_gpu": False,
                "priority_weight": 50,
                "incompatible_with": None,
            }
        },
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
        from_attributes=True,
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
        },
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
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "ai-llm",
                "display_name": "LLM (Nemotron)",
                "vram_required_mb": 8192,
                "vram_required_gb": 8.0,
                "description": "Nemotron LLM for risk analysis and enrichment",
            }
        },
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
        from_attributes=True,
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
        },
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
        from_attributes=True,
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
        },
    )


# =============================================================================
# Version History Schemas (NEM-4945)
# =============================================================================


class GpuConfigVersionSummary(BaseModel):
    """Summary of a GPU configuration version for listing.

    Provides a brief overview of each version for the history list,
    including version number, strategy, timestamp, and description.
    """

    id: str = Field(
        ...,
        description="Unique version identifier",
    )
    version_number: int = Field(
        ...,
        description="Sequential version number (higher = newer)",
        ge=1,
    )
    strategy: str = Field(
        ...,
        description="Assignment strategy used in this version",
    )
    description: str | None = Field(
        None,
        description="Optional description of changes",
    )
    created_at: datetime = Field(
        ...,
        description="When this version was created",
    )
    created_by: str | None = Field(
        None,
        description="Who created this version (if tracked)",
    )
    assignment_count: int = Field(
        ...,
        description="Number of service assignments in this version",
        ge=0,
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "version_number": 3,
                "strategy": "vram_based",
                "description": "Moved LLM to GPU 0 for better VRAM utilization",
                "created_at": "2026-01-23T10:30:00Z",
                "created_by": "system",
                "assignment_count": 5,
            }
        },
    )


class GpuConfigVersionDetail(GpuConfigVersionSummary):
    """Full details of a GPU configuration version.

    Extends the summary with complete assignment data for viewing
    or restoring a specific version.
    """

    assignments: list[GpuAssignment] = Field(
        ...,
        description="Complete service-to-GPU assignments for this version",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "version_number": 3,
                "strategy": "vram_based",
                "description": "Moved LLM to GPU 0 for better VRAM utilization",
                "created_at": "2026-01-23T10:30:00Z",
                "created_by": "system",
                "assignment_count": 3,
                "assignments": [
                    {"service": "ai-llm", "gpu_index": 0, "vram_budget_override": None},
                    {"service": "ai-yolo26", "gpu_index": 0, "vram_budget_override": None},
                    {"service": "ai-enrichment", "gpu_index": 1, "vram_budget_override": 3.5},
                ],
            }
        },
    )


class GpuConfigVersionListResponse(BaseModel):
    """Response schema for listing configuration versions.

    Returns paginated version history with summary information.
    """

    versions: list[GpuConfigVersionSummary] = Field(
        ...,
        description="List of version summaries, newest first",
    )
    total_count: int = Field(
        ...,
        description="Total number of versions",
        ge=0,
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "versions": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "version_number": 3,
                        "strategy": "vram_based",
                        "description": "Updated for multi-GPU setup",
                        "created_at": "2026-01-23T10:30:00Z",
                        "created_by": "system",
                        "assignment_count": 5,
                    }
                ],
                "total_count": 3,
            }
        },
    )


class GpuConfigAssignmentChange(BaseModel):
    """A single assignment change in a version diff.

    Describes what changed for a specific service between two versions.
    """

    service: str = Field(
        ...,
        description="Service name",
    )
    change_type: str = Field(
        ...,
        description="Type of change: 'added', 'removed', or 'modified'",
    )
    old_gpu_index: int | None = Field(
        None,
        description="Previous GPU index (for modified/removed)",
    )
    new_gpu_index: int | None = Field(
        None,
        description="New GPU index (for added/modified)",
    )
    old_vram_override: float | None = Field(
        None,
        description="Previous VRAM override (for modified/removed)",
    )
    new_vram_override: float | None = Field(
        None,
        description="New VRAM override (for added/modified)",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "service": "ai-llm",
                "change_type": "modified",
                "old_gpu_index": 1,
                "new_gpu_index": 0,
                "old_vram_override": None,
                "new_vram_override": None,
            }
        },
    )


class GpuConfigVersionDiffResponse(BaseModel):
    """Response schema for comparing two configuration versions.

    Shows the differences between two versions including strategy
    and assignment changes.
    """

    from_version: int = Field(
        ...,
        description="Source version number",
    )
    to_version: int = Field(
        ...,
        description="Target version number",
    )
    strategy_changed: bool = Field(
        ...,
        description="Whether the strategy changed between versions",
    )
    old_strategy: str | None = Field(
        None,
        description="Strategy in source version",
    )
    new_strategy: str | None = Field(
        None,
        description="Strategy in target version",
    )
    assignment_changes: list[GpuConfigAssignmentChange] = Field(
        default_factory=list,
        description="List of assignment changes",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "from_version": 2,
                "to_version": 3,
                "strategy_changed": True,
                "old_strategy": "manual",
                "new_strategy": "vram_based",
                "assignment_changes": [
                    {
                        "service": "ai-llm",
                        "change_type": "modified",
                        "old_gpu_index": 1,
                        "new_gpu_index": 0,
                        "old_vram_override": None,
                        "new_vram_override": None,
                    }
                ],
            }
        },
    )


# =============================================================================
# Export/Import Schemas (NEM-4945)
# =============================================================================


class GpuConfigExportData(BaseModel):
    """Exported GPU configuration data.

    Contains all information needed to restore a configuration,
    including metadata for validation.
    """

    export_version: str = Field(
        default="1.0",
        description="Export format version for compatibility",
    )
    exported_at: datetime = Field(
        ...,
        description="When the export was created",
    )
    strategy: str = Field(
        ...,
        description="Assignment strategy",
    )
    assignments: list[GpuAssignment] = Field(
        ...,
        description="Service-to-GPU assignments",
    )
    source_version: int | None = Field(
        None,
        description="Version number this was exported from (if applicable)",
    )
    description: str | None = Field(
        None,
        description="Optional description for this configuration",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "export_version": "1.0",
                "exported_at": "2026-01-23T10:30:00Z",
                "strategy": "vram_based",
                "assignments": [
                    {"service": "ai-llm", "gpu_index": 0, "vram_budget_override": None},
                    {"service": "ai-yolo26", "gpu_index": 0, "vram_budget_override": None},
                ],
                "source_version": 3,
                "description": "Production GPU configuration",
            }
        },
    )


# Export all schemas
__all__ = [
    "AiServiceInfo",
    "AiServicesResponse",
    "GpuAssignment",
    "GpuAssignmentStrategy",
    "GpuConfigAssignmentChange",
    "GpuConfigExportData",
    "GpuConfigPreviewResponse",
    "GpuConfigResponse",
    "GpuConfigVersionDetail",
    "GpuConfigVersionDiffResponse",
    "GpuConfigVersionListResponse",
    "GpuConfigVersionSummary",
    "GpuDeviceResponse",
    "GpuDevicesResponse",
]
