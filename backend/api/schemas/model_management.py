"""Pydantic schemas for Model Zoo Management API endpoints.

This module provides request/response schemas for the Model Zoo Management API,
enabling operators to view, load, and unload AI models across enrichment services.

See docs/plans/2025-01-31-model-zoo-management-design.md for design details.

Related Issues:
    - NEM-4780: Model Zoo Management Epic
    - NEM-4782: Backend API endpoint unit tests
"""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, Field


class ModelCategory(StrEnum):
    """Model category enumeration for classification.

    Categories help organize models by their function:
    - DETECTION: Object/feature detection models (YOLO, etc.)
    - CLASSIFICATION: Classification models (vehicle type, pet, etc.)
    - EMBEDDING: Embedding generation models (CLIP, OSNet, etc.)
    - POSE: Human pose estimation models
    - OCR: Text recognition models
    - SEGMENTATION: Image segmentation models
    - DEPTH_ESTIMATION: Depth/distance estimation models
    - ACTION_RECOGNITION: Video action classification models
    - VISION_LANGUAGE: Vision-language models (Florence, etc.)
    - QUALITY_ASSESSMENT: Image quality assessment models
    """

    DETECTION = auto()
    CLASSIFICATION = auto()
    EMBEDDING = auto()
    POSE = auto()
    OCR = auto()
    SEGMENTATION = auto()
    DEPTH_ESTIMATION = auto()
    ACTION_RECOGNITION = auto()
    VISION_LANGUAGE = auto()
    QUALITY_ASSESSMENT = auto()


class ServiceName(StrEnum):
    """Enrichment service names.

    Models are split across two enrichment services based on resource requirements:
    - AI_ENRICHMENT: Heavy models on GPU 0 (6.8 GB VRAM budget)
    - AI_ENRICHMENT_LIGHT: Light models on GPU 1 (1.2 GB VRAM budget)
    """

    AI_ENRICHMENT = "ai-enrichment"
    AI_ENRICHMENT_LIGHT = "ai-enrichment-light"


class ServiceStatus(StrEnum):
    """Service health status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ModelRuntimeInfo(BaseModel):
    """Runtime state information for a loaded model.

    This information comes from the enrichment service at runtime,
    reflecting the actual state of models in GPU memory.
    """

    loaded: bool = Field(
        ...,
        description="Whether the model is currently loaded in GPU memory",
    )
    actual_vram_mb: int | None = Field(
        None,
        description="Actual VRAM usage in megabytes (null if not loaded)",
        ge=0,
    )
    last_used: datetime | None = Field(
        None,
        description="Timestamp of last inference (null if never used or not loaded)",
    )
    load_count: int = Field(
        default=0,
        description="Number of times this model has been loaded since service start",
        ge=0,
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "loaded": True,
                "actual_vram_mb": 287,
                "last_used": "2025-01-31T10:30:00Z",
                "load_count": 5,
            }
        },
    )


class ModelStatus(BaseModel):
    """Combined registry metadata and runtime state for a model.

    Merges static configuration from the Model Zoo registry with
    runtime state from the enrichment service.
    """

    name: str = Field(
        ...,
        description="Unique model identifier (e.g., 'threat-detection-yolov8n')",
        min_length=1,
        max_length=128,
    )
    category: str = Field(
        ...,
        description="Model category (detection, classification, embedding, etc.)",
    )
    estimated_vram_mb: int = Field(
        ...,
        description="Estimated VRAM usage in megabytes from registry",
        ge=0,
    )
    enabled: bool = Field(
        ...,
        description="Whether the model is enabled for use in the system",
    )
    service: str = Field(
        ...,
        description="Enrichment service handling this model (ai-enrichment or ai-enrichment-light)",
    )
    gpu_id: int = Field(
        ...,
        description="GPU index assigned to this model (0 for heavy, 1 for light)",
        ge=0,
    )
    runtime: ModelRuntimeInfo = Field(
        ...,
        description="Runtime state from enrichment service",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "threat-detection-yolov8n",
                "category": "detection",
                "estimated_vram_mb": 300,
                "enabled": True,
                "service": "ai-enrichment-light",
                "gpu_id": 1,
                "runtime": {
                    "loaded": True,
                    "actual_vram_mb": 287,
                    "last_used": "2025-01-31T10:30:00Z",
                    "load_count": 5,
                },
            }
        },
    )


class ModelListResponse(BaseModel):
    """Response schema for GET /api/system/models.

    Returns all models from the registry with their runtime state,
    plus service health status for both enrichment services.
    """

    models: list[ModelStatus] = Field(
        ...,
        description="List of all models with registry metadata and runtime state",
    )
    service_status: dict[str, str] = Field(
        ...,
        description="Health status of each enrichment service (healthy/unhealthy/unknown)",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "models": [
                    {
                        "name": "threat-detection-yolov8n",
                        "category": "detection",
                        "estimated_vram_mb": 300,
                        "enabled": True,
                        "service": "ai-enrichment-light",
                        "gpu_id": 1,
                        "runtime": {
                            "loaded": True,
                            "actual_vram_mb": 287,
                            "last_used": "2025-01-31T10:30:00Z",
                            "load_count": 5,
                        },
                    },
                    {
                        "name": "vehicle-segment-classification",
                        "category": "classification",
                        "estimated_vram_mb": 1500,
                        "enabled": True,
                        "service": "ai-enrichment",
                        "gpu_id": 0,
                        "runtime": {
                            "loaded": False,
                            "actual_vram_mb": None,
                            "last_used": None,
                            "load_count": 0,
                        },
                    },
                ],
                "service_status": {
                    "ai-enrichment": "healthy",
                    "ai-enrichment-light": "healthy",
                },
            }
        },
    )


class VramGpuInfo(BaseModel):
    """VRAM information for a single GPU.

    Provides detailed VRAM breakdown for one GPU including
    budget, usage, and loaded models.
    """

    gpu_id: int = Field(
        ...,
        description="GPU index (0-based)",
        ge=0,
    )
    service: str = Field(
        ...,
        description="Enrichment service assigned to this GPU",
    )
    budget_mb: int = Field(
        ...,
        description="VRAM budget allocated to this GPU in megabytes",
        ge=0,
    )
    used_mb: int = Field(
        ...,
        description="Currently used VRAM in megabytes",
        ge=0,
    )
    available_mb: int = Field(
        ...,
        description="Available VRAM in megabytes (budget - used)",
        ge=0,
    )
    utilization_percent: float = Field(
        ...,
        description="VRAM utilization percentage (0-100)",
        ge=0.0,
        le=100.0,
    )
    loaded_models: list[str] = Field(
        default_factory=list,
        description="Names of models currently loaded on this GPU",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "gpu_id": 0,
                "service": "ai-enrichment",
                "budget_mb": 6800,
                "used_mb": 2100,
                "available_mb": 4700,
                "utilization_percent": 30.9,
                "loaded_models": ["fashion-clip", "vehicle-segment-classification"],
            }
        },
    )


class VramTotals(BaseModel):
    """Aggregate VRAM totals across all GPUs."""

    budget_mb: int = Field(
        ...,
        description="Total VRAM budget across all GPUs in megabytes",
        ge=0,
    )
    used_mb: int = Field(
        ...,
        description="Total VRAM used across all GPUs in megabytes",
        ge=0,
    )
    available_mb: int = Field(
        ...,
        description="Total available VRAM across all GPUs in megabytes",
        ge=0,
    )
    model_count: int = Field(
        ...,
        description="Total number of models currently loaded",
        ge=0,
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "budget_mb": 8000,
                "used_mb": 2550,
                "available_mb": 5450,
                "model_count": 4,
            }
        },
    )


class VramSummaryResponse(BaseModel):
    """Response schema for GET /api/system/models/vram-summary.

    Returns per-GPU VRAM breakdown plus aggregate totals.
    """

    gpus: list[VramGpuInfo] = Field(
        ...,
        description="Per-GPU VRAM information",
    )
    totals: VramTotals = Field(
        ...,
        description="Aggregate VRAM totals across all GPUs",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "gpus": [
                    {
                        "gpu_id": 0,
                        "service": "ai-enrichment",
                        "budget_mb": 6800,
                        "used_mb": 2100,
                        "available_mb": 4700,
                        "utilization_percent": 30.9,
                        "loaded_models": ["fashion-clip", "vehicle-segment-classification"],
                    },
                    {
                        "gpu_id": 1,
                        "service": "ai-enrichment-light",
                        "budget_mb": 1200,
                        "used_mb": 450,
                        "available_mb": 750,
                        "utilization_percent": 37.5,
                        "loaded_models": ["threat-detection-yolov8n", "osnet-x0-25"],
                    },
                ],
                "totals": {
                    "budget_mb": 8000,
                    "used_mb": 2550,
                    "available_mb": 5450,
                    "model_count": 4,
                },
            }
        },
    )


class LoadModelResponse(BaseModel):
    """Response schema for POST /api/system/models/{name}/load.

    Returns success status and details about the loaded model.
    """

    success: bool = Field(
        ...,
        description="Whether the model was loaded successfully",
    )
    model_name: str = Field(
        ...,
        description="Name of the model that was loaded",
    )
    service: str = Field(
        ...,
        description="Enrichment service that loaded the model",
    )
    gpu_id: int = Field(
        ...,
        description="GPU index where the model is loaded",
        ge=0,
    )
    load_time_ms: float = Field(
        ...,
        description="Time taken to load the model in milliseconds",
        ge=0.0,
    )
    vram_mb: int = Field(
        ...,
        description="VRAM consumed by the loaded model in megabytes",
        ge=0,
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "success": True,
                "model_name": "threat-detection-yolov8n",
                "service": "ai-enrichment-light",
                "gpu_id": 1,
                "load_time_ms": 1250.0,
                "vram_mb": 287,
            }
        },
    )


class UnloadModelResponse(BaseModel):
    """Response schema for POST /api/system/models/{name}/unload.

    Returns success status and VRAM freed by unloading.
    """

    success: bool = Field(
        ...,
        description="Whether the model was unloaded successfully",
    )
    model_name: str = Field(
        ...,
        description="Name of the model that was unloaded",
    )
    freed_vram_mb: int = Field(
        ...,
        description="VRAM freed by unloading the model in megabytes",
        ge=0,
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "success": True,
                "model_name": "threat-detection-yolov8n",
                "freed_vram_mb": 287,
            }
        },
    )


class UnloadAllResponse(BaseModel):
    """Response schema for POST /api/system/models/unload-all.

    Returns summary of models unloaded from both enrichment services.
    """

    success: bool = Field(
        ...,
        description="Whether all models were unloaded successfully",
    )
    unloaded_count: int = Field(
        ...,
        description="Number of models unloaded",
        ge=0,
    )
    freed_vram_mb: int = Field(
        ...,
        description="Total VRAM freed in megabytes",
        ge=0,
    )
    services: dict[str, int] = Field(
        ...,
        description="Number of models unloaded per service",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "success": True,
                "unloaded_count": 4,
                "freed_vram_mb": 2550,
                "services": {
                    "ai-enrichment": 2,
                    "ai-enrichment-light": 2,
                },
            }
        },
    )


class ModelDetailResponse(BaseModel):
    """Response schema for GET /api/system/models/{name}/status.

    Returns detailed information about a specific model.
    """

    name: str = Field(
        ...,
        description="Unique model identifier",
    )
    category: str = Field(
        ...,
        description="Model category",
    )
    path: str = Field(
        ...,
        description="Model file path or HuggingFace repo",
    )
    estimated_vram_mb: int = Field(
        ...,
        description="Estimated VRAM usage in megabytes",
        ge=0,
    )
    enabled: bool = Field(
        ...,
        description="Whether the model is enabled",
    )
    available: bool = Field(
        ...,
        description="Whether the model has been verified as working",
    )
    service: str = Field(
        ...,
        description="Enrichment service handling this model",
    )
    gpu_id: int = Field(
        ...,
        description="GPU index assigned to this model",
        ge=0,
    )
    runtime: ModelRuntimeInfo = Field(
        ...,
        description="Current runtime state",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "threat-detection-yolov8n",
                "category": "detection",
                "path": "/models/model-zoo/threat-detection-yolov8n",
                "estimated_vram_mb": 300,
                "enabled": True,
                "available": True,
                "service": "ai-enrichment-light",
                "gpu_id": 1,
                "runtime": {
                    "loaded": True,
                    "actual_vram_mb": 287,
                    "last_used": "2025-01-31T10:30:00Z",
                    "load_count": 5,
                },
            }
        },
    )


# Export all schemas
__all__ = [
    "LoadModelResponse",
    "ModelCategory",
    "ModelDetailResponse",
    "ModelListResponse",
    "ModelRuntimeInfo",
    "ModelStatus",
    "ServiceName",
    "ServiceStatus",
    "UnloadAllResponse",
    "UnloadModelResponse",
    "VramGpuInfo",
    "VramSummaryResponse",
    "VramTotals",
]
