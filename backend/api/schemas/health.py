"""Pydantic schemas for health check API endpoints.

This module defines consolidated response schemas for health check endpoints:
- LivenessResponse: For liveness probes (/health)
- ReadinessResponse: For readiness probes (/ready, /api/system/health/ready)
- CheckResult: Individual service check result
- DetailedHealthResponse: For debugging (/api/system/health)
- FullHealthResponse: For comprehensive health (/api/system/health/full)

The schemas ensure consistent response formats across all health endpoints.

Implements NEM-1582: Service health check orchestration and circuit breaker integration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LivenessResponse(BaseModel):
    """Response schema for liveness probe endpoint.

    Liveness probes indicate whether the process is running and able to
    respond to HTTP requests. This is a minimal check that always returns
    "alive" if the process is up.

    Used by:
    - GET /health (root level liveness probe)
    - Docker HEALTHCHECK liveness checks
    - Kubernetes liveness probes
    """

    status: Literal["alive"] = Field(
        default="alive",
        description="Liveness status: always 'alive' if process is responding",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "alive",
            }
        }
    )


class CheckResult(BaseModel):
    """Result of an individual service health check.

    Provides detailed information about a specific service's health status
    including latency measurements and error details when applicable.

    Status values:
    - healthy: Service is fully operational
    - unhealthy: Service is down or experiencing critical issues
    - degraded: Service is partially operational or experiencing performance issues
    """

    status: Literal["healthy", "unhealthy", "degraded"] = Field(
        ...,
        description="Service health status: healthy, unhealthy, or degraded",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Health check latency in milliseconds",
        ge=0,
    )
    error: str | None = Field(
        default=None,
        description="Error message if service is unhealthy or degraded",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "latency_ms": 5.2,
                "error": None,
            }
        }
    )


class ReadinessResponse(BaseModel):
    """Response schema for readiness probe endpoint.

    Readiness probes indicate whether the application is ready to receive
    traffic and process requests. Checks critical dependencies:
    - Database connectivity
    - Redis connectivity
    - Critical pipeline workers (optional for simple readiness)

    Used by:
    - GET /ready (root level readiness probe)
    - GET /api/system/health/ready (detailed readiness)
    - Docker HEALTHCHECK readiness checks
    - Kubernetes readiness probes
    - Load balancer health checks

    HTTP Status Codes:
    - 200: System is ready to accept traffic
    - 503: System is not ready (should not receive traffic)
    """

    ready: bool = Field(
        ...,
        description="Overall readiness status: True if system can process requests",
    )
    checks: dict[str, CheckResult] = Field(
        ...,
        description="Individual service check results keyed by service name",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ready": True,
                "checks": {
                    "database": {
                        "status": "healthy",
                        "latency_ms": 2.5,
                        "error": None,
                    },
                    "redis": {
                        "status": "healthy",
                        "latency_ms": 1.2,
                        "error": None,
                    },
                },
            }
        }
    )


class SimpleReadinessResponse(BaseModel):
    """Simplified response for the root-level readiness probe.

    A minimal response for basic readiness checks that only needs
    to know if the system is ready or not.

    Used by:
    - GET /ready (root level readiness probe)
    """

    ready: bool = Field(
        ...,
        description="Overall readiness status: True if system can process requests",
    )
    status: Literal["ready", "not_ready"] = Field(
        ...,
        description="Status string for human readability",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ready": True,
                "status": "ready",
            }
        }
    )


# =============================================================================
# Full Health Check Schemas (NEM-1582)
# =============================================================================


class ServiceHealthState(str, Enum):
    """Health state for a service in the full health check.

    States:
    - healthy: Service is fully operational
    - unhealthy: Service is down or experiencing critical issues
    - degraded: Service is partially operational
    - unknown: Service status cannot be determined
    """

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class CircuitState(str, Enum):
    """Circuit breaker state for a service.

    States:
    - closed: Normal operation, requests pass through
    - open: Service failing, requests fail immediately
    - half_open: Testing recovery, limited requests allowed
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AIServiceHealthStatus(BaseModel):
    """Health status for an AI service.

    Includes service identification, health state, circuit breaker state,
    and response time metrics.
    """

    name: str = Field(..., description="Service identifier (e.g., 'yolo26', 'nemotron')")
    display_name: str = Field(..., description="Human-readable service name")
    status: ServiceHealthState = Field(..., description="Current health state")
    url: str | None = Field(default=None, description="Service URL if configured")
    response_time_ms: float | None = Field(
        default=None, description="Health check response time in milliseconds"
    )
    circuit_state: CircuitState = Field(
        default=CircuitState.CLOSED, description="Circuit breaker state"
    )
    error: str | None = Field(default=None, description="Error message if unhealthy")
    last_check: datetime | None = Field(default=None, description="Timestamp of last health check")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "yolo26",
                "display_name": "YOLO26v2 Object Detection",
                "status": "healthy",
                "url": "http://ai-yolo26:8095",
                "response_time_ms": 45.2,
                "circuit_state": "closed",
                "error": None,
                "last_check": "2026-01-08T10:30:00Z",
            }
        }
    )


class InfrastructureHealthStatus(BaseModel):
    """Health status for infrastructure services (postgres, redis).

    Provides detailed status including connection info and any error details.
    """

    name: str = Field(..., description="Service name (e.g., 'postgres', 'redis')")
    status: ServiceHealthState = Field(..., description="Current health state")
    message: str = Field(..., description="Status message or error description")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional details (e.g., redis version)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "postgres",
                "status": "healthy",
                "message": "Database operational",
                "details": None,
            }
        }
    )


class CircuitBreakerSummary(BaseModel):
    """Summary of all circuit breakers in the system.

    Provides counts by state and individual breaker states for monitoring.
    """

    total: int = Field(..., description="Total number of circuit breakers")
    closed: int = Field(..., description="Number of breakers in closed state")
    open: int = Field(..., description="Number of breakers in open state")
    half_open: int = Field(..., description="Number of breakers in half-open state")
    breakers: dict[str, CircuitState] = Field(
        ..., description="Individual circuit breaker states keyed by service name"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 5,
                "closed": 4,
                "open": 1,
                "half_open": 0,
                "breakers": {
                    "yolo26": "closed",
                    "nemotron": "closed",
                    "florence": "open",
                    "clip": "closed",
                    "enrichment": "closed",
                },
            }
        }
    )


class WorkerHealthStatus(BaseModel):
    """Health status for a background worker.

    Workers are background processes that perform periodic or event-driven tasks.
    """

    name: str = Field(..., description="Worker name (e.g., 'file_watcher')")
    running: bool = Field(..., description="Whether the worker is currently running")
    critical: bool = Field(..., description="Whether this worker is critical for system operation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "file_watcher",
                "running": True,
                "critical": True,
            }
        }
    )


class FullHealthResponse(BaseModel):
    """Comprehensive health check response for GET /api/system/health/full.

    Aggregates health status from all services:
    - Infrastructure (postgres, redis)
    - AI services (yolo26, nemotron, florence, clip, enrichment)
    - Circuit breakers
    - Background workers

    HTTP Status Codes:
    - 200: System is healthy or degraded (can still serve traffic)
    - 503: Critical services are unhealthy (should not receive traffic)
    """

    status: ServiceHealthState = Field(..., description="Overall system health status")
    ready: bool = Field(..., description="Whether system is ready to receive traffic")
    message: str = Field(..., description="Human-readable status message")
    postgres: InfrastructureHealthStatus = Field(..., description="PostgreSQL health status")
    redis: InfrastructureHealthStatus = Field(..., description="Redis health status")
    ai_services: list[AIServiceHealthStatus] = Field(
        ..., description="Health status of all AI services"
    )
    circuit_breakers: CircuitBreakerSummary = Field(..., description="Circuit breaker summary")
    workers: list[WorkerHealthStatus] = Field(..., description="Background worker statuses")
    timestamp: datetime = Field(..., description="Response timestamp")
    version: str = Field(..., description="Application version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "ready": True,
                "message": "All systems operational",
                "postgres": {
                    "name": "postgres",
                    "status": "healthy",
                    "message": "Database operational",
                    "details": None,
                },
                "redis": {
                    "name": "redis",
                    "status": "healthy",
                    "message": "Redis connected",
                    "details": {"redis_version": "7.4.0"},
                },
                "ai_services": [
                    {
                        "name": "yolo26",
                        "display_name": "YOLO26v2 Object Detection",
                        "status": "healthy",
                        "url": "http://ai-yolo26:8095",
                        "response_time_ms": 45.2,
                        "circuit_state": "closed",
                        "error": None,
                        "last_check": "2026-01-08T10:30:00Z",
                    }
                ],
                "circuit_breakers": {
                    "total": 5,
                    "closed": 5,
                    "open": 0,
                    "half_open": 0,
                    "breakers": {"yolo26": "closed", "nemotron": "closed"},
                },
                "workers": [{"name": "file_watcher", "running": True, "critical": True}],
                "timestamp": "2026-01-08T10:30:00Z",
                "version": "0.1.0",
            }
        }
    )
