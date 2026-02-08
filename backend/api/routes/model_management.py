"""REST API endpoints for Model Zoo Management.

This module provides endpoints for viewing, loading, and unloading AI models
across the ai-enrichment and ai-enrichment-light services.

The backend acts as an aggregation layer that combines:
- Static model metadata from the registry (name, category, estimated VRAM)
- Runtime state from enrichment services via HTTP proxy

Design Document:
    See docs/plans/2025-01-31-model-zoo-management-design.md

Related Issues:
    - NEM-4780: Model Zoo Management Epic
    - NEM-4784: Backend API endpoint implementation

Endpoints:
    - GET  /api/system/models           - List all models with runtime state
    - GET  /api/system/models/{name}/status - Get detailed model status
    - POST /api/system/models/{name}/load   - Load a model
    - POST /api/system/models/{name}/unload - Unload a model
    - POST /api/system/models/{name}/reload - Reload a model (unload + load)
    - POST /api/system/models/unload-all    - Unload all models
    - GET  /api/system/models/vram-summary  - Get VRAM usage summary
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas.model_management import (
    LoadModelResponse,
    ModelDetailResponse,
    ModelListResponse,
    ModelRuntimeInfo,
    ModelStatus,
    UnloadAllResponse,
    UnloadModelResponse,
    VramGpuInfo,
    VramSummaryResponse,
    VramTotals,
)
from backend.core.logging import get_logger
from backend.services.model_zoo import get_model_config, get_model_zoo

logger = get_logger(__name__)

router = APIRouter(prefix="/api/system/models", tags=["model-management"])

# =============================================================================
# Service Routing Configuration
# =============================================================================

# Heavy models assigned to GPU 0 (ai-enrichment service)
HEAVY_MODELS = frozenset(
    {
        "vehicle-segment-classification",
        "fashion-clip",
        "xclip-base",
        "segformer-b2-clothes",
        "yolo-world-s",
        "vitpose-small",
        "vehicle-damage-detection",
        "violence-detection",
    }
)

# Light models assigned to GPU 1 (ai-enrichment-light service)
LIGHT_MODELS = frozenset(
    {
        "threat-detection-yolov8n",
        "osnet-x0-25",
        "depth-anything-v2-tiny",
        "pet-classifier",
        "vit-age-classifier",
        "vit-gender-classifier",
        "yolov8n-pose",
        "weather-classification",
        "brisque-quality",
    }
)

# Service URLs
ENRICHMENT_URL = "http://ai-enrichment:8094"
ENRICHMENT_LIGHT_URL = "http://ai-enrichment-light:8096"

# Default VRAM budgets
HEAVY_VRAM_BUDGET_MB = 6800
LIGHT_VRAM_BUDGET_MB = 1200

# HTTP client timeout settings
HTTP_CONNECT_TIMEOUT = 5.0
HTTP_READ_TIMEOUT = 30.0


# =============================================================================
# Service Routing Functions
# =============================================================================


def get_service_for_model(model_name: str) -> str:
    """Get the enrichment service URL for a model.

    Args:
        model_name: Name of the model

    Returns:
        Service URL (ai-enrichment or ai-enrichment-light)
    """
    if model_name in LIGHT_MODELS:
        return ENRICHMENT_LIGHT_URL
    return ENRICHMENT_URL


def get_service_name_for_model(model_name: str) -> str:
    """Get the enrichment service name for a model.

    Args:
        model_name: Name of the model

    Returns:
        Service name ("ai-enrichment" or "ai-enrichment-light")
    """
    if model_name in LIGHT_MODELS:
        return "ai-enrichment-light"
    return "ai-enrichment"


def get_gpu_id_for_model(model_name: str) -> int:
    """Get the GPU ID for a model.

    Args:
        model_name: Name of the model

    Returns:
        GPU ID (0 for heavy models, 1 for light models)
    """
    if model_name in LIGHT_MODELS:
        return 1
    return 0


# =============================================================================
# HTTP Client Dependency
# =============================================================================


async def get_http_client() -> httpx.AsyncClient:
    """Get an HTTP client for enrichment service calls.

    Returns:
        httpx.AsyncClient instance
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=HTTP_CONNECT_TIMEOUT,
            read=HTTP_READ_TIMEOUT,
            write=HTTP_READ_TIMEOUT,
            pool=HTTP_READ_TIMEOUT,
        )
    )


# =============================================================================
# Internal Helper Functions
# =============================================================================


async def _fetch_service_status(
    client: httpx.AsyncClient,
    service_url: str,
) -> dict[str, Any] | None:
    """Fetch model status from an enrichment service.

    Args:
        client: HTTP client
        service_url: Base URL of the enrichment service

    Returns:
        Status response dictionary or None if service unavailable
    """
    try:
        response = await client.get(f"{service_url}/models/status")
        if response.status_code == 200:
            result: dict[str, Any] = response.json()
            return result
        logger.warning(f"Failed to get status from {service_url}: HTTP {response.status_code}")
        return None
    except httpx.ConnectError:
        logger.warning(f"Cannot connect to {service_url}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"Timeout connecting to {service_url}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching status from {service_url}: {e}")
        return None


def _get_runtime_for_model(
    model_name: str,
    heavy_status: dict[str, Any] | None,
    light_status: dict[str, Any] | None,
) -> ModelRuntimeInfo:
    """Get runtime info for a model from enrichment service status.

    Args:
        model_name: Name of the model
        heavy_status: Status from ai-enrichment service
        light_status: Status from ai-enrichment-light service

    Returns:
        ModelRuntimeInfo for the model
    """
    # Determine which service to check
    if model_name in LIGHT_MODELS:
        status = light_status
    else:
        status = heavy_status

    if status is None:
        return ModelRuntimeInfo(
            loaded=False,
            actual_vram_mb=None,
            last_used=None,
            load_count=0,
        )

    # Check if model is loaded
    loaded_models = status.get("loaded_models", {})
    is_loaded = False
    model_info: dict[str, Any] | None = None

    if isinstance(loaded_models, list):
        # Handle list format (old format) - check separate models dict for details
        if model_name in loaded_models:
            is_loaded = True
            models_dict = status.get("models", {})
            if isinstance(models_dict, dict) and model_name in models_dict:
                model_info = models_dict[model_name]
    elif isinstance(loaded_models, dict):
        # Handle dict format (new format with details inline)
        if model_name in loaded_models:
            is_loaded = True
            model_info = loaded_models[model_name]

    if is_loaded:
        if model_info:
            return ModelRuntimeInfo(
                loaded=True,
                actual_vram_mb=model_info.get("actual_vram_mb") or model_info.get("vram_mb"),
                last_used=model_info.get("last_used"),
                load_count=model_info.get("load_count", 0),
            )
        return ModelRuntimeInfo(
            loaded=True,
            actual_vram_mb=None,
            last_used=None,
            load_count=0,
        )

    return ModelRuntimeInfo(
        loaded=False,
        actual_vram_mb=None,
        last_used=None,
        load_count=0,
    )


def _get_service_health(status: dict[str, Any] | None) -> str:
    """Get service health status.

    Args:
        status: Status response from service or None

    Returns:
        "healthy", "unhealthy", or "unknown"
    """
    if status is None:
        return "unhealthy"
    return "healthy"


def _build_gpu_vram_info(
    gpu_id: int,
    service_name: str,
    status: dict[str, Any] | None,
    default_budget_mb: int,
) -> VramGpuInfo:
    """Build VRAM info for a GPU from service status.

    Extracts VRAM budget, usage, and loaded models from enrichment service
    status response, falling back to defaults if service is unavailable.

    Args:
        gpu_id: GPU index (0 or 1)
        service_name: Name of the enrichment service
        status: Status response from enrichment service, or None if unavailable
        default_budget_mb: Default VRAM budget if not in status response

    Returns:
        VramGpuInfo with VRAM metrics for this GPU
    """
    if status:
        budget_mb = status.get("vram_budget_mb") or status.get("budget_mb", default_budget_mb)
        used_mb = status.get("vram_used_mb") or status.get("used_mb", 0)
        loaded_models_data = status.get("loaded_models", {})
        if isinstance(loaded_models_data, dict):
            loaded_models = list(loaded_models_data.keys())
        else:
            loaded_models = loaded_models_data if isinstance(loaded_models_data, list) else []
    else:
        budget_mb = default_budget_mb
        used_mb = 0
        loaded_models = []

    available_mb = budget_mb - used_mb
    utilization = (used_mb / budget_mb * 100) if budget_mb > 0 else 0.0

    return VramGpuInfo(
        gpu_id=gpu_id,
        service=service_name,
        budget_mb=budget_mb,
        used_mb=used_mb,
        available_mb=available_mb,
        utilization_percent=round(utilization, 1),
        loaded_models=loaded_models,
    )


# =============================================================================
# Endpoint Handlers
# =============================================================================


@router.get(
    "",
    response_model=ModelListResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def list_models(
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ModelListResponse:
    """List all models with registry metadata and runtime state.

    Returns models from the registry merged with runtime state from
    enrichment services. If enrichment services are unavailable,
    returns registry data with runtime.loaded=False.

    Returns:
        List of all models with status and service health info
    """
    # Get static config from registry
    registry = get_model_zoo()

    # Fetch runtime state from both enrichment services
    heavy_status = await _fetch_service_status(http_client, ENRICHMENT_URL)
    light_status = await _fetch_service_status(http_client, ENRICHMENT_LIGHT_URL)

    # Build model list
    models = []
    for name, config in registry.items():
        runtime = _get_runtime_for_model(name, heavy_status, light_status)
        models.append(
            ModelStatus(
                name=name,
                category=config.category,
                estimated_vram_mb=config.vram_mb,
                enabled=config.enabled,
                service=get_service_name_for_model(name),
                gpu_id=get_gpu_id_for_model(name),
                runtime=runtime,
            )
        )

    # Build service status
    service_status = {
        "ai-enrichment": _get_service_health(heavy_status),
        "ai-enrichment-light": _get_service_health(light_status),
    }

    return ModelListResponse(models=models, service_status=service_status)


@router.get(
    "/{model_name}/status",
    response_model=ModelDetailResponse,
    responses={
        404: {"description": "Model not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_model_status(
    model_name: str,
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ModelDetailResponse:
    """Get detailed status for a specific model.

    Args:
        model_name: Name of the model to get status for

    Returns:
        Detailed model information including runtime state

    Raises:
        HTTPException: 404 if model not found
    """
    config = get_model_config(model_name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found in registry",
        )

    # Fetch runtime state from the appropriate service
    service_url = get_service_for_model(model_name)
    status = await _fetch_service_status(http_client, service_url)
    runtime = _get_runtime_for_model(model_name, status, status)

    return ModelDetailResponse(
        name=config.name,
        category=config.category,
        path=config.path,
        estimated_vram_mb=config.vram_mb,
        enabled=config.enabled,
        available=config.available,
        service=get_service_name_for_model(model_name),
        gpu_id=get_gpu_id_for_model(model_name),
        runtime=runtime,
    )


@router.post(
    "/{model_name}/load",
    response_model=LoadModelResponse,
    responses={
        400: {"description": "Model is disabled"},
        404: {"description": "Model not found"},
        502: {"description": "Enrichment service error"},
        503: {"description": "Enrichment service unavailable"},
    },
)
async def load_model(
    model_name: str,
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> LoadModelResponse:
    """Load a model via the enrichment service.

    Proxies the load request to the appropriate enrichment service
    based on model-to-service mapping.

    Args:
        model_name: Name of the model to load

    Returns:
        Load result with timing and VRAM info

    Raises:
        HTTPException: 404 if model not found, 400 if disabled,
                      502 if service error, 503 if unavailable
    """
    config = get_model_config(model_name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found in registry",
        )

    if not config.enabled:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' is disabled",
        )

    service_url = get_service_for_model(model_name)
    service_name = get_service_name_for_model(model_name)
    gpu_id = get_gpu_id_for_model(model_name)

    try:
        response = await http_client.post(
            f"{service_url}/models/preload",
            params={"model_name": model_name},
        )

        if response.status_code == 200:
            data = response.json()
            return LoadModelResponse(
                success=True,
                model_name=model_name,
                service=service_name,
                gpu_id=gpu_id,
                load_time_ms=data.get("load_time_ms", 0.0),
                vram_mb=data.get("vram_mb", config.vram_mb),
            )
        else:
            logger.error(f"Failed to load model {model_name}: HTTP {response.status_code}")
            raise HTTPException(
                status_code=502,
                detail=f"Enrichment service returned error: {response.status_code}",
            )

    except httpx.ConnectError:
        logger.error(f"Cannot connect to {service_url} to load {model_name}")
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment service unavailable: {service_name}",
        ) from None
    except httpx.TimeoutException:
        logger.error(f"Timeout loading {model_name} from {service_url}")
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment service timeout: {service_name}",
        ) from None


@router.post(
    "/{model_name}/unload",
    response_model=UnloadModelResponse,
    responses={
        404: {"description": "Model not found"},
        502: {"description": "Enrichment service error"},
        503: {"description": "Enrichment service unavailable"},
    },
)
async def unload_model(
    model_name: str,
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> UnloadModelResponse:
    """Unload a model via the enrichment service.

    Proxies the unload request to the appropriate enrichment service
    based on model-to-service mapping.

    Args:
        model_name: Name of the model to unload

    Returns:
        Unload result with freed VRAM info

    Raises:
        HTTPException: 404 if model not found,
                      502 if service error, 503 if unavailable
    """
    config = get_model_config(model_name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found in registry",
        )

    service_url = get_service_for_model(model_name)

    try:
        response = await http_client.post(
            f"{service_url}/models/{model_name}/unload",
        )

        if response.status_code == 200:
            data = response.json()
            return UnloadModelResponse(
                success=True,
                model_name=model_name,
                freed_vram_mb=data.get("freed_vram_mb", config.vram_mb),
            )
        else:
            logger.error(f"Failed to unload model {model_name}: HTTP {response.status_code}")
            raise HTTPException(
                status_code=502,
                detail=f"Enrichment service returned error: {response.status_code}",
            )

    except httpx.ConnectError:
        service_name = get_service_name_for_model(model_name)
        logger.error(f"Cannot connect to {service_url} to unload {model_name}")
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment service unavailable: {service_name}",
        ) from None
    except httpx.TimeoutException:
        service_name = get_service_name_for_model(model_name)
        logger.error(f"Timeout unloading {model_name} from {service_url}")
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment service timeout: {service_name}",
        ) from None


@router.post(
    "/{model_name}/reload",
    response_model=LoadModelResponse,
    responses={
        400: {"description": "Model is disabled"},
        404: {"description": "Model not found"},
        502: {"description": "Enrichment service error"},
        503: {"description": "Enrichment service unavailable"},
    },
)
async def reload_model(
    model_name: str,
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> LoadModelResponse:
    """Reload a model by unloading and then loading it.

    Args:
        model_name: Name of the model to reload

    Returns:
        Load result with timing and VRAM info

    Raises:
        HTTPException: 404 if model not found, 400 if disabled,
                      502 if service error, 503 if unavailable
    """
    config = get_model_config(model_name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found in registry",
        )

    if not config.enabled:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' is disabled",
        )

    service_url = get_service_for_model(model_name)
    service_name = get_service_name_for_model(model_name)
    gpu_id = get_gpu_id_for_model(model_name)

    try:
        # First unload (ignore errors if not loaded)
        try:
            await http_client.post(f"{service_url}/models/{model_name}/unload")
        except Exception:
            # Ignore unload errors - model may not be loaded
            logger.debug(f"Unload during reload failed for {model_name} (may not be loaded)")

        # Then load
        response = await http_client.post(
            f"{service_url}/models/preload",
            params={"model_name": model_name},
        )

        if response.status_code == 200:
            data = response.json()
            return LoadModelResponse(
                success=True,
                model_name=model_name,
                service=service_name,
                gpu_id=gpu_id,
                load_time_ms=data.get("load_time_ms", 0.0),
                vram_mb=data.get("vram_mb", config.vram_mb),
            )
        else:
            logger.error(f"Failed to reload model {model_name}: HTTP {response.status_code}")
            raise HTTPException(
                status_code=502,
                detail=f"Enrichment service returned error: {response.status_code}",
            )

    except httpx.ConnectError:
        logger.error(f"Cannot connect to {service_url} to reload {model_name}")
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment service unavailable: {service_name}",
        ) from None
    except httpx.TimeoutException:
        logger.error(f"Timeout reloading {model_name} from {service_url}")
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment service timeout: {service_name}",
        ) from None


@router.post(
    "/unload-all",
    response_model=UnloadAllResponse,
    responses={
        502: {"description": "Enrichment service error"},
        503: {"description": "Enrichment service unavailable"},
    },
)
async def unload_all_models(
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> UnloadAllResponse:
    """Unload all models from both enrichment services.

    Returns:
        Summary of unloaded models and freed VRAM

    Raises:
        HTTPException: 502 if service error, 503 if unavailable
    """
    total_unloaded = 0
    total_freed_vram = 0
    services_unloaded: dict[str, int] = {}

    # Unload from heavy service
    try:
        response = await http_client.post(f"{ENRICHMENT_URL}/models/unload-all")
        if response.status_code == 200:
            data = response.json()
            count = data.get("unloaded_count", 0)
            freed = data.get("freed_vram_mb", 0)
            total_unloaded += count
            total_freed_vram += freed
            services_unloaded["ai-enrichment"] = count
        else:
            services_unloaded["ai-enrichment"] = 0
    except Exception as e:
        logger.warning(f"Failed to unload from ai-enrichment: {e}")
        services_unloaded["ai-enrichment"] = 0

    # Unload from light service
    try:
        response = await http_client.post(f"{ENRICHMENT_LIGHT_URL}/models/unload-all")
        if response.status_code == 200:
            data = response.json()
            count = data.get("unloaded_count", 0)
            freed = data.get("freed_vram_mb", 0)
            total_unloaded += count
            total_freed_vram += freed
            services_unloaded["ai-enrichment-light"] = count
        else:
            services_unloaded["ai-enrichment-light"] = 0
    except Exception as e:
        logger.warning(f"Failed to unload from ai-enrichment-light: {e}")
        services_unloaded["ai-enrichment-light"] = 0

    return UnloadAllResponse(
        success=True,
        unloaded_count=total_unloaded,
        freed_vram_mb=total_freed_vram,
        services=services_unloaded,
    )


@router.get(
    "/vram-summary",
    response_model=VramSummaryResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_vram_summary(
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> VramSummaryResponse:
    """Get per-GPU VRAM usage summary from both enrichment services.

    Returns:
        Per-GPU VRAM breakdown plus aggregate totals
    """
    # Fetch status from both services
    heavy_status = await _fetch_service_status(http_client, ENRICHMENT_URL)
    light_status = await _fetch_service_status(http_client, ENRICHMENT_LIGHT_URL)

    # Build VRAM info for each GPU
    gpus = [
        _build_gpu_vram_info(0, "ai-enrichment", heavy_status, HEAVY_VRAM_BUDGET_MB),
        _build_gpu_vram_info(1, "ai-enrichment-light", light_status, LIGHT_VRAM_BUDGET_MB),
    ]

    # Calculate totals
    totals = VramTotals(
        budget_mb=sum(g.budget_mb for g in gpus),
        used_mb=sum(g.used_mb for g in gpus),
        available_mb=sum(g.available_mb for g in gpus),
        model_count=sum(len(g.loaded_models) for g in gpus),
    )

    return VramSummaryResponse(gpus=gpus, totals=totals)
