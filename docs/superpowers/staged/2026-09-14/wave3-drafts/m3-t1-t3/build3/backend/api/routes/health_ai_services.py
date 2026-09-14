"""Unified AI services health endpoint (NEM-3143).

This module provides the /api/health/ai-services endpoint for aggregated AI service
health monitoring. It combines health status from all AI services with circuit breaker
states and queue depth visibility.

Endpoints:
- GET /api/health/ai-services: Get unified AI services health status
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Response

from backend.api.schemas.ai_services_health import (
    AIServiceCircuitState,
    AIServiceHealthDetail,
    AIServiceOverallStatus,
    AIServicesHealthResponse,
    AIServiceStatus,
    QueueDepthInfo,
)
from backend.core import get_settings
from backend.core.config import Settings
from backend.core.constants import (
    ANALYSIS_QUEUE,
    DETECTION_QUEUE,
    DLQ_ANALYSIS_QUEUE,
    DLQ_DETECTION_QUEUE,
)
from backend.core.logging import get_logger
from backend.core.metrics import set_dlq_depth
from backend.core.redis import RedisClient, get_redis_optional

logger = get_logger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])

# Health check timeout for AI services
AI_SERVICE_HEALTH_TIMEOUT = 5.0

# AI Service definitions with display names and criticality
# Critical services affect overall_status = "critical" when down
AI_SERVICES_CONFIG: list[dict[str, Any]] = [
    {
        "name": "yolo26",
        "display_name": "YOLO26 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    },
    {
        "name": "nemotron",
        "display_name": "Nemotron LLM Risk Analysis",
        "url_attr": "nemotron_url",
        "circuit_breaker_name": "nemotron",
        "critical": True,
    },
    {
        "name": "florence",
        "display_name": "Florence-2 Vision Language",
        "url_attr": "florence_url",
        "circuit_breaker_name": "florence",
        "critical": False,
    },
    {
        "name": "clip",
        "display_name": "CLIP Embedding Service",
        "url_attr": "clip_url",
        "circuit_breaker_name": "clip",
        "critical": False,
    },
    {
        "name": "enrichment",
        "display_name": "Enrichment Service",
        "url_attr": "enrichment_url",
        "circuit_breaker_name": "enrichment",
        "critical": False,
    },
]


def _get_circuit_breaker_state(service_name: str) -> AIServiceCircuitState:
    """Get the circuit breaker state for a service.

    Args:
        service_name: Name of the service to check

    Returns:
        AIServiceCircuitState for the service
    """
    from backend.services.circuit_breaker import _get_registry

    registry = _get_registry()
    breaker = registry.get(service_name)

    if breaker is None:
        return AIServiceCircuitState.CLOSED

    state_value = breaker.state.value
    if state_value == "open":
        return AIServiceCircuitState.OPEN
    elif state_value == "half_open":
        return AIServiceCircuitState.HALF_OPEN
    return AIServiceCircuitState.CLOSED


def _get_circuit_breaker_metrics(service_name: str) -> dict[str, Any]:
    """Get metrics from the circuit breaker for a service.

    Args:
        service_name: Name of the service

    Returns:
        Dict with failure_count, total_calls, rejected_calls
    """
    from backend.services.circuit_breaker import _get_registry

    registry = _get_registry()
    breaker = registry.get(service_name)

    if breaker is None:
        return {
            "failure_count": 0,
            "total_calls": 0,
            "rejected_calls": 0,
        }

    status = breaker.get_status()
    return {
        "failure_count": status.get("failure_count", 0),
        "total_calls": status.get("total_calls", 0),
        "rejected_calls": status.get("rejected_calls", 0),
    }


def _calculate_error_rate(metrics: dict[str, Any]) -> float | None:
    """Calculate error rate from circuit breaker metrics.

    This provides an approximation of error rate based on circuit breaker
    failure count vs total calls. For more accurate metrics, a dedicated
    metrics service would be needed.

    Args:
        metrics: Circuit breaker metrics dict

    Returns:
        Error rate as float (0.0-1.0) or None if no calls recorded
    """
    total_calls: int = metrics.get("total_calls", 0)
    if total_calls == 0:
        return None

    # Calculate error rate from failures + rejected calls
    failures: int = metrics.get("failure_count", 0)
    rejected: int = metrics.get("rejected_calls", 0)
    error_count = failures + rejected

    return float(round(min(error_count / total_calls, 1.0), 4))


async def _check_ai_service_health(  # noqa: PLR0911
    service_config: dict[str, Any],
    settings: Settings,
    timeout: float = AI_SERVICE_HEALTH_TIMEOUT,
) -> AIServiceHealthDetail:
    """Check health of a single AI service.

    Args:
        service_config: Service configuration dict
        settings: Application settings
        timeout: HTTP timeout in seconds

    Returns:
        AIServiceHealthDetail with current health status
    """
    name = service_config["name"]
    url_attr = service_config["url_attr"]
    circuit_breaker_name = service_config.get("circuit_breaker_name", name)

    service_url = getattr(settings, url_attr, None)
    circuit_state = _get_circuit_breaker_state(circuit_breaker_name)
    cb_metrics = _get_circuit_breaker_metrics(circuit_breaker_name)
    error_rate = _calculate_error_rate(cb_metrics)

    # If URL not configured, mark as unknown
    if not service_url:
        return AIServiceHealthDetail(
            status=AIServiceStatus.UNKNOWN,
            circuit_state=circuit_state,
            last_health_check=datetime.now(UTC),
            error_rate_1h=error_rate,
            latency_p99_ms=None,
            url=None,
            error="Service URL not configured",
        )

    # If circuit is open, don't make HTTP request
    if circuit_state == AIServiceCircuitState.OPEN:
        return AIServiceHealthDetail(
            status=AIServiceStatus.UNHEALTHY,
            circuit_state=circuit_state,
            last_health_check=datetime.now(UTC),
            error_rate_1h=error_rate,
            latency_p99_ms=None,
            url=service_url,
            error="Circuit breaker is open - service unreachable",
        )

    # Perform health check
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{service_url}/health")
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return AIServiceHealthDetail(
                    status=AIServiceStatus.HEALTHY,
                    circuit_state=circuit_state,
                    last_health_check=datetime.now(UTC),
                    error_rate_1h=error_rate,
                    latency_p99_ms=round(latency_ms, 2),
                    url=service_url,
                    error=None,
                )
            return AIServiceHealthDetail(
                status=AIServiceStatus.UNHEALTHY,
                circuit_state=circuit_state,
                last_health_check=datetime.now(UTC),
                error_rate_1h=error_rate,
                latency_p99_ms=round(latency_ms, 2),
                url=service_url,
                error=f"HTTP {response.status_code}",
            )
    except httpx.ConnectError:
        return AIServiceHealthDetail(
            status=AIServiceStatus.UNHEALTHY,
            circuit_state=circuit_state,
            last_health_check=datetime.now(UTC),
            error_rate_1h=error_rate,
            latency_p99_ms=None,
            url=service_url,
            error="Connection refused",
        )
    except httpx.TimeoutException:
        return AIServiceHealthDetail(
            status=AIServiceStatus.UNHEALTHY,
            circuit_state=circuit_state,
            last_health_check=datetime.now(UTC),
            error_rate_1h=error_rate,
            latency_p99_ms=None,
            url=service_url,
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        logger.warning(f"Health check error for {name}: {e}")
        return AIServiceHealthDetail(
            status=AIServiceStatus.UNHEALTHY,
            circuit_state=circuit_state,
            last_health_check=datetime.now(UTC),
            error_rate_1h=error_rate,
            latency_p99_ms=None,
            url=service_url,
            error=str(e),
        )


async def _get_queue_depths(redis: RedisClient | None) -> dict[str, QueueDepthInfo]:
    """Get queue depths for detection and analysis queues.

    Also updates DLQ depth Prometheus metrics (NEM-3891) for alerting.

    Args:
        redis: Redis client or None if unavailable

    Returns:
        Dict mapping queue names to QueueDepthInfo
    """
    if redis is None:
        return {
            "detection_queue": QueueDepthInfo(depth=0, dlq_depth=0),
            "analysis_queue": QueueDepthInfo(depth=0, dlq_depth=0),
        }

    try:
        # Get queue lengths in parallel
        # NEM-3891: Use correct DLQ key names (dlq:detection_queue, not detection_queue:dlq)
        detection_depth, analysis_depth, detection_dlq, analysis_dlq = await asyncio.gather(
            redis.get_queue_length(DETECTION_QUEUE),
            redis.get_queue_length(ANALYSIS_QUEUE),
            redis.get_queue_length(DLQ_DETECTION_QUEUE),
            redis.get_queue_length(DLQ_ANALYSIS_QUEUE),
            return_exceptions=True,
        )

        # Handle any exceptions
        def safe_int(val: Any) -> int:
            if isinstance(val, Exception):
                logger.warning(f"Error getting queue length: {val}")
                return 0
            return int(val) if val is not None else 0

        detection_dlq_depth = safe_int(detection_dlq)
        analysis_dlq_depth = safe_int(analysis_dlq)

        # NEM-3891: Update DLQ depth Prometheus metrics for alerting
        set_dlq_depth(DLQ_DETECTION_QUEUE, detection_dlq_depth)
        set_dlq_depth(DLQ_ANALYSIS_QUEUE, analysis_dlq_depth)

        return {
            "detection_queue": QueueDepthInfo(
                depth=safe_int(detection_depth),
                dlq_depth=detection_dlq_depth,
            ),
            "analysis_queue": QueueDepthInfo(
                depth=safe_int(analysis_depth),
                dlq_depth=analysis_dlq_depth,
            ),
        }
    except Exception as e:
        logger.warning(f"Error getting queue depths: {e}")
        return {
            "detection_queue": QueueDepthInfo(depth=0, dlq_depth=0),
            "analysis_queue": QueueDepthInfo(depth=0, dlq_depth=0),
        }


def _calculate_overall_status(
    service_health: dict[str, AIServiceHealthDetail],
) -> AIServiceOverallStatus:
    """Calculate overall status from individual service health.

    Logic:
    - CRITICAL: Any critical service is unhealthy
    - DEGRADED: Any non-critical service is unhealthy, but all critical services are healthy
    - HEALTHY: All services are healthy

    Args:
        service_health: Dict mapping service names to health details

    Returns:
        AIServiceOverallStatus
    """
    critical_services = {cfg["name"] for cfg in AI_SERVICES_CONFIG if cfg.get("critical", False)}

    # Check if any critical service is unhealthy
    for name, health in service_health.items():
        if name in critical_services and health.status in (
            AIServiceStatus.UNHEALTHY,
            AIServiceStatus.UNKNOWN,
        ):
            return AIServiceOverallStatus.CRITICAL

    # Check if any service is unhealthy (degraded mode)
    for health in service_health.values():
        if health.status in (AIServiceStatus.UNHEALTHY, AIServiceStatus.DEGRADED):
            return AIServiceOverallStatus.DEGRADED

    return AIServiceOverallStatus.HEALTHY


@router.get(
    "/ai-services",
    response_model=AIServicesHealthResponse,
    responses={
        200: {"description": "AI services health status returned"},
        503: {"description": "Critical AI services are unhealthy"},
    },
    summary="Get Unified AI Services Health Status",
    description="""
Get a unified view of all AI service health including circuit breaker states,
error rates, latency metrics, and queue depths.

The response includes:
- **overall_status**: healthy/degraded/critical based on service availability
- **services**: Individual health status for each AI service (yolo26, nemotron, florence, clip, enrichment)
- **queues**: Current depth of detection and analysis queues with DLQ counts

HTTP Status Codes:
- **200**: All services operational or system is degraded but functional
- **503**: Critical services (yolo26, nemotron) are unhealthy
""",
)
async def get_ai_services_health(
    response: Response,
    redis: RedisClient | None = Depends(get_redis_optional),
) -> AIServicesHealthResponse:
    """Get unified AI services health status."""
    settings = get_settings()

    # Check all AI services in parallel
    health_tasks = [_check_ai_service_health(config, settings) for config in AI_SERVICES_CONFIG]

    results = await asyncio.gather(*health_tasks)

    # Build services dict
    services: dict[str, AIServiceHealthDetail] = {}
    for config, health in zip(AI_SERVICES_CONFIG, results, strict=True):
        services[config["name"]] = health

    # Get queue depths
    queues = await _get_queue_depths(redis)

    # Calculate overall status
    overall_status = _calculate_overall_status(services)

    # Set HTTP status code based on overall health
    if overall_status == AIServiceOverallStatus.CRITICAL:
        response.status_code = 503

    return AIServicesHealthResponse(
        overall_status=overall_status,
        services=services,
        queues=queues,
        timestamp=datetime.now(UTC),
    )
