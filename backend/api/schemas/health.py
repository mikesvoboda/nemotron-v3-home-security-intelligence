"""Pydantic schemas for health check API endpoints.

This module defines consolidated response schemas for health check endpoints:
- LivenessResponse: For liveness probes (/health)
- ReadinessResponse: For readiness probes (/ready, /api/system/health/ready)
- CheckResult: Individual service check result
- DetailedHealthResponse: For debugging (/api/system/health)

The schemas ensure consistent response formats across all health endpoints.
"""

from typing import Literal

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
