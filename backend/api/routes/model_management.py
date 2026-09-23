"""REST API endpoints for Model Zoo Management.

This module provides endpoints for viewing model state across the AI serving
stack. Since the ai-serving consolidation, the standalone ai-enrichment /
ai-enrichment-light containers are retired: every gateway-served model is a
router on ai-gateway (:8090), backed by Triton Inference Server, and the
remaining backend-registry models load lazily in the backend process via
ModelManager.

The backend acts as an aggregation layer that combines:
- Static model metadata from the registry (name, category, estimated VRAM)
- Triton readiness from ai-gateway health, unioned across two surfaces keyed
  by the triton_name values in the root models.yml catalogue:
  * router health (GET {router}/health), which reports only the Triton models
    its own routers serve — /enrichment reports vehicle/fashion_clip/
    demographics_age/demographics_gender/pet/depth and /enrich-lt reports
    pose/threat/reid/pet/depth; neither reports clip, clip_text or
    stgcn_action, and
  * the gateway root health (GET {root}/health), which iterates the gateway's
    full ALL_MODELS registry and therefore covers every Triton name — it is
    the only surface that reports clip/clip_text (serving
    siglip2-base-patch16-224) and stgcn_action (serving stgcn-plus-plus)
  A name is readiness-authoritative in whichever payload reports it; a name
  reported nowhere logs a warning rather than silently reporting not-loaded.
- In-process load state from the backend ModelManager for models without a
  Triton mapping

Load/unload semantics: Triton runs with --model-control-mode=none, so
gateway models are resident and cannot be loaded or unloaded over HTTP —
the gateway exposes no preload/unload surface (see backend/ai_contract
Operation "model_preload"/"model_unload", availability.gateway=False). The
former proxy endpoints therefore return 501 with an explanatory detail
rather than fabricate a no-op success.

VRAM accounting: the retired enrichment services' VRAM manager no longer
exists, so vram-summary reports, per gateway router, the Triton-ready models
from router health with the registry's *estimated* vram_mb summed as used_mb
(the models.yml estimate is the same basis ModelManager.total_loaded_vram
uses). Triton does not expose per-model VRAM over HTTP.

Design Document:
    See docs/plans/2025-01-31-model-zoo-management-design.md (pre-consolidation
    design; the service topology described there is retired)

Related Issues:
    - NEM-4780: Model Zoo Management Epic
    - NEM-4784: Backend API endpoint implementation

Endpoints:
    - GET  /api/system/models           - List all models with runtime state
    - GET  /api/system/models/{name}/status - Get detailed model status
    - POST /api/system/models/{name}/load   - 501 (Triton-resident models)
    - POST /api/system/models/{name}/unload - 501 (Triton-resident models)
    - POST /api/system/models/{name}/reload - 501 (Triton-resident models)
    - POST /api/system/models/unload-all    - 501 (Triton-resident models)
    - GET  /api/system/models/vram-summary  - Get VRAM usage summary
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import yaml
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
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.services.model_zoo import get_model_config, get_model_manager, get_model_zoo

logger = get_logger(__name__)

router = APIRouter(prefix="/api/system/models", tags=["model-management"])

# =============================================================================
# Service Routing Configuration
# =============================================================================

# models.yml catalogue (single source of truth) — maps registry names to the
# Triton model names that ai-gateway router health payloads are keyed by.
_MODELS_YML = Path(__file__).resolve().parents[3] / "models.yml"

# Heavy lane: gateway /enrichment router (models.yml enrichment_*_service=heavy)
HEAVY_MODELS = frozenset(
    {
        "vehicle-segment-classification",
        "fashion-clip",
        "segformer-b2-clothes",
        "yolo-world-s",
        "vitpose-small",
        "vehicle-damage-detection",
        "violence-detection",
        "vit-age-classifier",
        "vit-gender-classifier",
    }
)

# Light lane: gateway /enrich-lt router. This mirrors the gateway reality —
# the /enrich-lt health payload reports readiness for pose/threat/reid/pet/
# depth only (see ai/gateway/adapters/enrichment_light.py); demographics
# models live on the heavy router.
LIGHT_MODELS = frozenset(
    {
        "threat-detection-yolov8n",
        "osnet-ain-x1-0",
        "depth-anything-v2-tiny",
        "pet-classifier",
        "yolov8n-pose",
    }
)

# Default VRAM budgets
HEAVY_VRAM_BUDGET_MB = 6800
LIGHT_VRAM_BUDGET_MB = 1200

# HTTP client timeout settings
HTTP_CONNECT_TIMEOUT = 5.0
HTTP_READ_TIMEOUT = 30.0

# Shared explanation for the retired load/unload lifecycle surface
_LIFECYCLE_UNSUPPORTED_DETAIL = (
    "Model load/unload is not supported after the ai-gateway consolidation: "
    "gateway models run on Triton with --model-control-mode=none (resident; "
    "the gateway exposes no preload/unload API). Per-model readiness is "
    "reported by GET /api/system/models."
)


# =============================================================================
# Service Routing Functions
# =============================================================================


# Path suffixes that identify a settings URL as a gateway router URL;
# get_gateway_root_url strips one to recover the gateway root for its /health
# probe. Derived from the settings-field defaults ("http://ai-gateway:8090/
# enrichment" ends in "/enrichment") so they track the fields, not the
# gateway's internal mount table.
ROUTER_SUFFIXES = ("/enrichment", "/enrich-lt")


def get_router_urls() -> tuple[str, str]:
    """Resolve the (heavy, light) gateway router base URLs from settings.

    Follows the same resolution order as EnrichmentClient: when AI Gateway
    mode is enabled, router URLs are built from ai_gateway_url; otherwise the
    enrichment_url / enrichment_light_url settings fields are used (both
    already default to the ai-gateway routers post-consolidation).

    Returns:
        Tuple of (heavy router URL, light router URL)
    """
    settings = get_settings()
    gateway_url = getattr(settings, "ai_gateway_url", None)
    if getattr(settings, "use_ai_gateway", False) is True and isinstance(gateway_url, str):
        base = gateway_url.rstrip("/")
        return f"{base}/enrichment", f"{base}/enrich-lt"
    return settings.enrichment_url, settings.enrichment_light_url


def get_gateway_root_url() -> str | None:
    """Resolve the ai-gateway ROOT base URL (no router suffix) from settings.

    The gateway's root /health iterates its full Triton registry, so it is the
    only readiness surface that reports the Triton models served by routers
    other than /enrichment and /enrich-lt (clip / clip_text / stgcn_action).
    The root URL is recovered by stripping the router suffix from the resolved
    router URLs (the ai_gateway_url base in gateway mode, else the suffixed
    enrichment_url / enrichment_light_url settings fields); a URL that carries
    no known suffix gets no probe rather than a guessed one.

    Returns:
        Gateway root base URL, or None when it cannot be derived.
    """
    heavy_url, light_url = get_router_urls()
    for router_url in (heavy_url, light_url):
        if not isinstance(router_url, str):
            continue
        base = router_url.rstrip("/")
        for suffix in ROUTER_SUFFIXES:
            if base.endswith(suffix):
                return base[: -len(suffix)]
    logger.warning(
        f"Could not derive the ai-gateway root URL from router URLs {heavy_url!r} / "
        f"{light_url!r}; root /health readiness probe skipped"
    )
    return None


def get_service_for_model(model_name: str) -> str:
    """Get the gateway router URL for a model.

    Args:
        model_name: Name of the model

    Returns:
        Router base URL (heavy /enrichment or light /enrich-lt router)
    """
    heavy_url, light_url = get_router_urls()
    return light_url if model_name in LIGHT_MODELS else heavy_url


def get_service_name_for_model(model_name: str) -> str:
    """Get the logical service name for a model.

    The names are retained as heavy/light router lane labels (the standalone
    containers they were named after are retired).

    Args:
        model_name: Name of the model

    Returns:
        Service label ("ai-enrichment" or "ai-enrichment-light")
    """
    if model_name in LIGHT_MODELS:
        return "ai-enrichment-light"
    return "ai-enrichment"


def get_gpu_id_for_model(model_name: str) -> int:
    """Get the GPU lane ID for a model.

    Args:
        model_name: Name of the model

    Returns:
        Lane ID (0 for heavy lane, 1 for light lane)
    """
    if model_name in LIGHT_MODELS:
        return 1
    return 0


@lru_cache(maxsize=1)
def _load_triton_name_map() -> dict[str, tuple[str, ...]]:
    """Map registry model names to their Triton model names from models.yml.

    ai-gateway router /health payloads key readiness by Triton name (e.g.
    "vehicle", "reid"), not by registry name (e.g.
    "vehicle-segment-classification"); the triton_name / triton_models fields
    in models.yml provide the mapping.

    Returns:
        Mapping of registry name to its Triton model name(s); empty when
        models.yml is unavailable or unparseable.
    """
    if not _MODELS_YML.exists():
        logger.warning(f"models.yml not found at {_MODELS_YML}; Triton readiness unavailable")
        return {}
    try:
        entries: list[dict[str, Any]] = yaml.safe_load(_MODELS_YML.read_text())["models"]
    except Exception:
        logger.exception(f"Failed to parse {_MODELS_YML}")
        return {}

    result: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        names = [
            str(t["triton_name"])
            for t in entry.get("triton_models") or []
            if isinstance(t, dict) and t.get("triton_name")
        ]
        if not names and entry.get("triton_name"):
            names = [str(entry["triton_name"])]
        if names:
            result[str(entry["name"])] = tuple(names)
    return result


# =============================================================================
# HTTP Client Dependency
# =============================================================================


async def get_http_client() -> httpx.AsyncClient:
    """Get an HTTP client for gateway router calls.

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


async def _fetch_router_health(
    client: httpx.AsyncClient,
    router_url: str,
) -> dict[str, Any] | None:
    """Fetch a per-model readiness payload from a gateway health endpoint.

    Serves both surfaces: a router's /health (keyed by the Triton models that
    router serves) and the gateway root /health (keyed by the gateway's full
    Triton registry), since both answer {"models": {triton_name: ready}}.

    Args:
        client: HTTP client
        router_url: Base URL of the gateway router or gateway root

    Returns:
        Health payload ({"status": ..., "models": {triton_name: ready}}) or
        None if the router is unreachable
    """
    try:
        response = await client.get(f"{router_url}/health")
        if response.status_code == 200:
            result: dict[str, Any] = response.json()
            return result
        logger.warning(f"Failed to get health from {router_url}: HTTP {response.status_code}")
        return None
    except httpx.ConnectError:
        logger.warning(f"Cannot connect to {router_url}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"Timeout connecting to {router_url}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching health from {router_url}: {e}")
        return None


async def _fetch_root_and_router_health(
    client: httpx.AsyncClient,
    router_urls: tuple[str, ...],
) -> tuple[dict[str, Any] | None, list[dict[str, Any] | None]]:
    """Fetch the gateway root health and the given routers' health concurrently.

    The union of the returned payloads' "models" maps is the readiness truth
    for every Triton name in models.yml (see _triton_ready): the routers cover
    the models their own endpoints serve, and the root registry covers the
    rest (clip / clip_text / stgcn_action). Probing the root when it cannot be
    derived from settings is skipped rather than guessed.

    Args:
        client: HTTP client
        router_urls: Router base URLs to probe alongside the root

    Returns:
        Tuple of (root_health, router_payloads); root_health is None when the
        root URL was not derivable or the probe failed, and each router
        payload is None when that router was unreachable
    """
    root_url = get_gateway_root_url() if router_urls else None
    fetches = [
        _fetch_router_health(client, url) if url is not None else _unavailable()
        for url in (root_url, *router_urls)
    ]
    results = await asyncio.gather(*fetches)
    return (results[0] if results else None), list(results[1:])


async def _unavailable() -> None:
    """Awaitable None placeholder for a skipped (undervivable-URL) probe."""
    return None


def _readiness_payloads(
    *health: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Extract the {"models": {triton_name: ready}} maps from health payloads.

    Args:
        *health: Any number of gateway health payloads (root and/or router),
            each possibly None when the surface was unreachable

    Returns:
        The "models" sub-maps of the payloads that reported them
    """
    return [
        h["models"] for h in health if isinstance(h, dict) and isinstance(h.get("models"), dict)
    ]


def _triton_ready(
    triton_names: tuple[str, ...],
    root_health: dict[str, Any] | None,
    *router_health: dict[str, Any] | None,
) -> bool:
    """Check whether all Triton models of one registry entry are ready.

    Readiness is unioned across the router /health payloads and the gateway
    root /health payload. A Triton name is authoritative in whichever payload
    reports it: the serving routers are consulted first (their payloads cover
    the models their routers serve — pet/depth overlap and are satisfied by
    either router), and the root payload — which iterates the gateway's full
    ALL_MODELS registry — answers the names no router reports, namely
    clip/clip_text (serving siglip2-base-patch16-224) and stgcn_action
    (serving stgcn-plus-plus). When NO payload reports a name at all (the
    gateway answers but its Triton registry no longer matches models.yml) the
    gap is logged as a warning instead of hiding behind a silent permanent
    not-ready, so catalogue drift is visible.

    Args:
        triton_names: Triton model names for the registry entry
        root_health: Health payload from the gateway root /health, or None
        *router_health: Health payloads from the gateway routers, each or None

    Returns:
        True only if every Triton model is reported ready by the payloads
        that report it
    """
    payloads = _readiness_payloads(root_health, *router_health)
    # Only flag "reported nowhere" when at least one surface answered — with
    # every surface unreachable _fetch_router_health has already warned about
    # connectivity, and per-model drift warnings would just bury it.
    if payloads:
        for name in triton_names:
            if not any(name in payload for payload in payloads):
                logger.warning(
                    f"Triton model '{name}' is reported by no gateway health payload "
                    "(root + routers); its readiness cannot be confirmed — check that "
                    "the gateway's Triton registry still matches models.yml"
                )
    # Every payload reads the same Triton, so a name any reporting payload
    # marks ready is ready (a False from a racing probe must not mask it).
    return all(
        any(isinstance(payload, dict) and payload.get(name) is True for payload in payloads)
        for name in triton_names
    )


def _build_runtime(
    model_name: str,
    config: Any,
    root_health: dict[str, Any] | None,
    *router_health: dict[str, Any] | None,
) -> ModelRuntimeInfo:
    """Build runtime info for a model from gateway readiness or the backend manager.

    Models with a Triton mapping report readiness unioned across the gateway
    root health and the router health payloads — the routers do not report
    every Triton name, so the root registry is required for clip/clip_text/
    stgcn_action (Triton exposes no per-model VRAM/usage over HTTP, so
    actual_vram_mb/last_used/load_count are not available). A Triton-mapped
    model is by definition gateway-served and is never answered from the
    backend ModelManager, which cannot hold it. Models without a mapping run
    in the backend process and report ModelManager state, using the registry
    estimate for VRAM (same basis as ModelManager.total_loaded_vram).

    Args:
        model_name: Name of the model
        config: Registry ModelConfig for the model
        root_health: Health payload from the gateway root /health, or None
        *router_health: Health payloads from the gateway routers, each or None

    Returns:
        ModelRuntimeInfo for the model
    """
    triton_names = _load_triton_name_map().get(model_name)
    if triton_names:
        return ModelRuntimeInfo(
            loaded=_triton_ready(triton_names, root_health, *router_health),
            actual_vram_mb=None,
            last_used=None,
            load_count=0,
        )

    loaded = get_model_manager().is_loaded(model_name)
    return ModelRuntimeInfo(
        loaded=loaded,
        actual_vram_mb=config.vram_mb if loaded else None,
        last_used=None,
        load_count=0,
    )


def _get_service_health(status: dict[str, Any] | None) -> str:
    """Get service health status.

    Args:
        status: Health response from router or None

    Returns:
        "healthy", "unhealthy", or "unknown"
    """
    if status is None:
        return "unhealthy"
    return "healthy"


def _build_gpu_vram_info(
    gpu_id: int,
    service_name: str,
    light_lane: bool,
    health: dict[str, Any] | None,
    default_budget_mb: int,
    registry: dict[str, Any],
) -> VramGpuInfo:
    """Build VRAM info for a router lane from gateway readiness plus registry estimates.

    Lists the registry models assigned to this lane whose Triton models are
    reported ready by the router health payload and sums their registry
    vram_mb estimates (the retired VRAM-manager accounting no longer exists;
    see module docstring).

    Args:
        gpu_id: Lane ID (0 heavy, 1 light)
        service_name: Logical service label for the lane
        light_lane: True to build the light lane, False for heavy
        health: Health payload from the router, or None if unreachable
        default_budget_mb: Configured VRAM budget for this lane
        registry: Model zoo registry (name -> ModelConfig)

    Returns:
        VramGpuInfo with VRAM metrics for this lane
    """
    triton_map = _load_triton_name_map()
    models_payload: dict[str, Any] = {}
    if health and isinstance(health.get("models"), dict):
        models_payload = health["models"]

    loaded_models: list[str] = []
    used_mb = 0
    for name, config in registry.items():
        if (name in LIGHT_MODELS) != light_lane:
            continue
        triton_names = triton_map.get(name)
        if not triton_names:
            continue  # backend-process model, not resident on this router
        if all(models_payload.get(t) is True for t in triton_names):
            loaded_models.append(name)
            used_mb += int(config.vram_mb)

    budget_mb = default_budget_mb
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

    Returns models from the registry merged with Triton readiness unioned
    across the gateway root /health and the two router /health payloads (and
    ModelManager state for backend-process models). If every surface is
    unreachable, Triton-mapped models report runtime.loaded=False.

    Returns:
        List of all models with status and service health info
    """
    # Get static config from registry
    registry = get_model_zoo()

    # Fetch readiness from the gateway root plus both routers
    router_urls = get_router_urls()
    root_health, router_payloads = await _fetch_root_and_router_health(http_client, router_urls)
    heavy_health, light_health = router_payloads

    # Build model list
    models = []
    for name, config in registry.items():
        runtime = _build_runtime(name, config, root_health, heavy_health, light_health)
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
        "ai-enrichment": _get_service_health(heavy_health),
        "ai-enrichment-light": _get_service_health(light_health),
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

    # Fetch readiness from the gateway root plus the router that serves this
    # model — the router payload alone cannot confirm Triton names it does not
    # report (clip/clip_text/stgcn_action come from the root registry only).
    # Backend-process models have no Triton mapping and probe nothing; they
    # report ModelManager state only.
    probe_routers: tuple[str, ...] = ()
    if _load_triton_name_map().get(model_name):
        probe_routers = (get_service_for_model(model_name),)
    root_health, router_payloads = await _fetch_root_and_router_health(http_client, probe_routers)
    runtime = _build_runtime(model_name, config, root_health, *router_payloads)

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
        501: {"description": "Load unsupported — models are Triton-resident on ai-gateway"},
    },
)
async def load_model(
    model_name: str,
) -> LoadModelResponse:
    """Load a model — no longer possible after the ai-gateway consolidation.

    Triton runs with --model-control-mode=none, so gateway models are
    resident and there is no load API; backend-process models load lazily
    through ModelManager on first use. Reported as 501 instead of a
    fabricated success.

    Args:
        model_name: Name of the model to load

    Raises:
        HTTPException: 404 if model not found, 400 if disabled,
                      501 because load is not supported
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

    logger.info(f"Rejected load request for {model_name}: Triton-resident models")
    raise HTTPException(status_code=501, detail=_LIFECYCLE_UNSUPPORTED_DETAIL)


@router.post(
    "/{model_name}/unload",
    response_model=UnloadModelResponse,
    responses={
        404: {"description": "Model not found"},
        501: {"description": "Unload unsupported — models are Triton-resident on ai-gateway"},
    },
)
async def unload_model(
    model_name: str,
) -> UnloadModelResponse:
    """Unload a model — no longer possible after the ai-gateway consolidation.

    See load_model: Triton-resident models cannot be unloaded over HTTP.

    Args:
        model_name: Name of the model to unload

    Raises:
        HTTPException: 404 if model not found, 501 because unload is
                      not supported
    """
    config = get_model_config(model_name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found in registry",
        )

    logger.info(f"Rejected unload request for {model_name}: Triton-resident models")
    raise HTTPException(status_code=501, detail=_LIFECYCLE_UNSUPPORTED_DETAIL)


@router.post(
    "/{model_name}/reload",
    response_model=LoadModelResponse,
    responses={
        400: {"description": "Model is disabled"},
        404: {"description": "Model not found"},
        501: {"description": "Reload unsupported — models are Triton-resident on ai-gateway"},
    },
)
async def reload_model(
    model_name: str,
) -> LoadModelResponse:
    """Reload a model — no longer possible after the ai-gateway consolidation.

    See load_model: Triton-resident models cannot be reloaded over HTTP.

    Args:
        model_name: Name of the model to reload

    Raises:
        HTTPException: 404 if model not found, 400 if disabled,
                      501 because reload is not supported
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

    logger.info(f"Rejected reload request for {model_name}: Triton-resident models")
    raise HTTPException(status_code=501, detail=_LIFECYCLE_UNSUPPORTED_DETAIL)


@router.post(
    "/unload-all",
    response_model=UnloadAllResponse,
    responses={
        501: {"description": "Unload unsupported — models are Triton-resident on ai-gateway"},
    },
)
async def unload_all_models() -> UnloadAllResponse:
    """Unload all models — no longer possible after the ai-gateway consolidation.

    Raises:
        HTTPException: 501 because unload is not supported
    """
    logger.info("Rejected unload-all request: Triton-resident models")
    raise HTTPException(status_code=501, detail=_LIFECYCLE_UNSUPPORTED_DETAIL)


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
    """Get per-lane VRAM summary from gateway readiness plus registry estimates.

    used_mb is the sum of registry vram_mb estimates for the router's
    Triton-ready models (see module docstring — the VRAM-manager accounting
    that previously backed this endpoint was retired with the standalone
    enrichment containers).

    Returns:
        Per-lane VRAM breakdown plus aggregate totals
    """
    registry = get_model_zoo()

    # Fetch readiness from both gateway routers
    heavy_url, light_url = get_router_urls()
    heavy_health = await _fetch_router_health(http_client, heavy_url)
    light_health = await _fetch_router_health(http_client, light_url)

    # Build VRAM info for each lane
    gpus = [
        _build_gpu_vram_info(
            0,
            "ai-enrichment",
            False,
            heavy_health,
            HEAVY_VRAM_BUDGET_MB,
            registry,
        ),
        _build_gpu_vram_info(
            1,
            "ai-enrichment-light",
            True,
            light_health,
            LIGHT_VRAM_BUDGET_MB,
            registry,
        ),
    ]

    # Calculate totals
    totals = VramTotals(
        budget_mb=sum(g.budget_mb for g in gpus),
        used_mb=sum(g.used_mb for g in gpus),
        available_mb=sum(g.available_mb for g in gpus),
        model_count=sum(len(g.loaded_models) for g in gpus),
    )

    return VramSummaryResponse(gpus=gpus, totals=totals)
