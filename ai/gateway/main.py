"""AI Gateway — FastAPI application.

A thin REST-to-gRPC translation layer that sits in front of NVIDIA Triton
Inference Server. The gateway preserves the exact HTTP API that the backend's
AI clients already use, so the backend only needs a URL change to switch
from 5 separate AI containers to a single Triton-backed gateway.

Architecture:
    Backend (port 8000)
        -> AI Gateway (port 8090, FastAPI on CPU)
            -> Triton Inference Server (port 8001 gRPC, GPU)

Adapters:
    /yolo26/*      - Object detection (TensorRT)
    /clip/*        - CLIP embeddings (TensorRT vision, optional ONNX text)
    /florence/*    - Florence-2 vision-language (Python backend)
    /enrichment/*  - Heavy enrichment models (vehicle, clothing, demographics, etc.)
    /enrich-lt/*   - Light enrichment models (pose, threat, reid, pet, depth)

Top-level endpoints:
    GET /health    - Aggregated health across all Triton models
    GET /metrics   - Prometheus metrics (Triton native + gateway application)
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Triton native HTTP endpoint for metrics/health (inside same container)
TRITON_HTTP_URL = os.getenv("TRITON_HTTP_URL", "http://localhost:8000")
TRITON_METRICS_URL = os.getenv("TRITON_METRICS_URL", "http://localhost:8002")

# All models that should be loaded in Triton
ALL_MODELS: list[str] = [
    "yolo26",
    "clip",
    "florence2",
    "vehicle",
    "fashion_clip",
    "demographics_age",
    "demographics_gender",
    "pet",
    "depth",
    "reid",
    "pose",
    "threat",
    "xclip_action",
]


# ---------------------------------------------------------------------------
# Prometheus metrics for gateway-level observability
# ---------------------------------------------------------------------------

try:
    from prometheus_client import (
        Counter,
        Histogram,
        generate_latest,
    )

    GATEWAY_REQUEST_DURATION = Histogram(
        "hsi_ai_inference_duration_seconds",
        "Gateway-level inference request duration in seconds",
        ["service", "endpoint"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )

    GATEWAY_REQUEST_ERRORS = Counter(
        "hsi_ai_inference_errors_total",
        "Gateway-level inference errors",
        ["service", "endpoint"],
    )

    _prometheus_available = True
except ImportError:
    _prometheus_available = False
    logger.warning("prometheus_client not installed, metrics endpoint will be limited")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager.

    On startup: connect to Triton gRPC and verify all models are loaded.
    On shutdown: close Triton gRPC connection gracefully.
    """
    from ai.gateway.triton_client import get_triton_client

    triton = get_triton_client()
    logger.info("AI Gateway starting up...")

    # Verify Triton server connectivity
    retries = 30
    for attempt in range(retries):
        if await triton.is_server_ready():
            logger.info("Triton Inference Server is ready")
            break
        if attempt < retries - 1:
            logger.info(f"Waiting for Triton server... (attempt {attempt + 1}/{retries})")
            import asyncio

            await asyncio.sleep(2)
    else:
        logger.error("Triton server not ready after all retries")

    # Check which models are loaded
    loaded: list[str] = []
    not_loaded: list[str] = []
    for model_name in ALL_MODELS:
        if await triton.is_model_ready(model_name):
            loaded.append(model_name)
        else:
            not_loaded.append(model_name)

    logger.info(f"Models loaded: {loaded}")
    if not_loaded:
        logger.warning(f"Models NOT loaded: {not_loaded}")

    yield

    # Shutdown
    logger.info("AI Gateway shutting down...")
    await triton.close()
    logger.info("AI Gateway shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Gateway",
    description="REST-to-gRPC translation layer for Triton Inference Server",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Mount adapter routers
# ---------------------------------------------------------------------------

from ai.gateway.adapters.clip import router as clip_router
from ai.gateway.adapters.enrichment import router as enrichment_router
from ai.gateway.adapters.enrichment_light import router as enrichment_light_router
from ai.gateway.adapters.florence import router as florence_router
from ai.gateway.adapters.yolo26 import router as yolo26_router

app.include_router(yolo26_router, prefix="/yolo26", tags=["yolo26"])
app.include_router(clip_router, prefix="/clip", tags=["clip"])
app.include_router(florence_router, prefix="/florence", tags=["florence"])
app.include_router(enrichment_router, prefix="/enrichment", tags=["enrichment"])
app.include_router(enrichment_light_router, prefix="/enrich-lt", tags=["enrichment-light"])


# ---------------------------------------------------------------------------
# Top-level endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Aggregated health check across all Triton models.

    Checks each model's readiness via Triton's v2/models/{name}/ready
    endpoint. Returns overall status as 'healthy' only if all models
    are loaded and ready.

    Matches the health response format expected by the backend's
    health checking infrastructure.
    """
    from ai.gateway.triton_client import get_triton_client

    triton = get_triton_client()

    server_ready = await triton.is_server_ready()

    model_statuses: dict[str, bool] = {}
    for model_name in ALL_MODELS:
        model_statuses[model_name] = await triton.is_model_ready(model_name)

    all_models_ready = all(model_statuses.values())
    overall_status = "healthy" if (server_ready and all_models_ready) else "degraded"

    return {
        "status": overall_status,
        "triton_server_ready": server_ready,
        "models": model_statuses,
        "models_loaded": sum(1 for v in model_statuses.values() if v),
        "models_total": len(ALL_MODELS),
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus metrics endpoint.

    Merges Triton's native metrics (from :8002/metrics) with gateway-level
    application metrics into a single scrape target.
    """
    parts: list[str] = []

    # Fetch Triton native metrics
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{TRITON_METRICS_URL}/metrics")
            if resp.status_code == 200:
                parts.append(resp.text)
    except Exception as e:
        logger.debug(f"Could not fetch Triton metrics: {e}")
        parts.append(f"# Triton metrics unavailable: {e}\n")

    # Append gateway application metrics
    if _prometheus_available:
        gateway_metrics = generate_latest().decode("utf-8")
        parts.append(gateway_metrics)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("GATEWAY_PORT", "8090"))

    uvicorn.run(
        "ai.gateway.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
