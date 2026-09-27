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
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Triton native HTTP endpoint for metrics/health (inside same container)
TRITON_HTTP_URL = os.getenv("TRITON_HTTP_URL", "http://localhost:8000")
TRITON_METRICS_URL = os.getenv("TRITON_METRICS_URL", "http://localhost:8002")

# The complete Triton model repository (the `full` residency set). Derived
# from ai.gateway.residency.FULL_MODEL_SET — one source of truth (review
# 1.4 item 1): the repository this gateway describes and the repository the
# entrypoint's residency step prunes are the SAME tuple, so they cannot
# drift. Rev 6: residency is by repository contents; --model-control-mode
# stays `none`.
from ai.gateway.residency import FULL_MODEL_SET, resolve_active_set

ALL_MODELS: list[str] = list(FULL_MODEL_SET)

# What THIS gateway instance serves (GATEWAY_MODEL_SET; default `full`).
# /health and startup reporting use this, so a vlm-mode gateway reports the
# retired models' absence by NOT listing them — listing them as not_loaded
# forever would be a false alarm by construction.
ACTIVE_MODELS: tuple[str, ...] = resolve_active_set()


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
    # The middleware checks for None and self-disables when the client is
    # missing, mirroring the limited /metrics behaviour above.
    GATEWAY_REQUEST_DURATION = None  # type: ignore[assignment]
    GATEWAY_REQUEST_ERRORS = None  # type: ignore[assignment]


# Paths that are NOT inference traffic and must stay out of the inference
# histograms so health-probe/scrape chatter does not skew latency panels:
# the gateway root and per-adapter health checks, plus Prometheus' own scrape
# target. Inference endpoints (/yolo26/detect, /clip/embed, ...) are observed.
_METRICS_EXCLUDED_PREFIXES = ("/metrics",)


def _is_health_path(path: str) -> bool:
    """True for the aggregated /health and any adapter /…/health route."""
    return path == "/health" or path.endswith("/health")


def _gateway_labels(scope: Scope) -> tuple[str, str]:
    """Derive (service, endpoint) Prometheus labels for a request.

    Labels come from the matched route pattern, not the raw URL: service is
    the adapter prefix the router is mounted under (/yolo26 -> "yolo26",
    /enrich-lt -> "enrich-lt", ...), endpoint is the route path under that
    prefix with the slash stripped (/clip/embed -> "embed"; a root path
    like /docs -> "root"). Paths that match no route (404s) get
    ("other", "other") so label cardinality stays bounded by the fixed
    route table even under attacker-crafted URLs.
    """
    path: str = scope.get("path", "")
    for route in app.routes:
        match, _child = route.matches(scope)
        if match == Match.FULL:
            route_path: str = getattr(route, "path", path)
            stripped = route_path.lstrip("/")
            service, _, tail = stripped.partition("/")
            return (service or "root", tail.lstrip("/") or "root")
    return ("other", "other")


class GatewayMetricsMiddleware:
    """Observe GATEWAY_REQUEST_DURATION / GATEWAY_REQUEST_ERRORS.

    Pure ASGI middleware: times every request that is not a health check or
    a metrics scrape, labels it by adapter service + endpoint, and counts an
    error when the response is 5xx or the wrapped app raises. Duration is
    measured up to the last message sent to the client (the response body
    fully flushed), so inference latency includes serialize+upload time.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        duration_metric = GATEWAY_REQUEST_DURATION
        errors_metric = GATEWAY_REQUEST_ERRORS
        if scope["type"] != "http" or duration_metric is None:
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if path.startswith(_METRICS_EXCLUDED_PREFIXES) or _is_health_path(path):
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status: int = 500  # assume failure; an exception that escapes means 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            service, endpoint = _gateway_labels(scope)
            duration_metric.labels(service=service, endpoint=endpoint).observe(duration)
            if status >= 500 and errors_metric is not None:
                errors_metric.labels(service=service, endpoint=endpoint).inc()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
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

    # Check which models are loaded (the ACTIVE residency set only — retired
    # models are absent from the repository by design, rev 6)
    loaded: list[str] = []
    not_loaded: list[str] = []
    for model_name in ACTIVE_MODELS:
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
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gateway request observability: observes hsi_ai_inference_duration_seconds /
# hsi_ai_inference_errors_total on every non-health, non-scrape request
# (labels: service = adapter prefix, endpoint = route under it).
app.add_middleware(GatewayMetricsMiddleware)


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
    for model_name in ACTIVE_MODELS:
        model_statuses[model_name] = await triton.is_model_ready(model_name)

    all_models_ready = all(model_statuses.values())
    overall_status = "healthy" if (server_ready and all_models_ready) else "degraded"

    return {
        "status": overall_status,
        "triton_server_ready": server_ready,
        "models": model_statuses,
        "models_loaded": sum(1 for v in model_statuses.values() if v),
        "models_total": len(ACTIVE_MODELS),
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
