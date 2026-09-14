"""Pydantic schemas for unified AI services health endpoint (NEM-3143).

This module defines response schemas for the /api/health/ai-services endpoint,
providing a unified view of all AI service health including:
- Individual service health status with circuit breaker states
- Error rates and latency metrics
- Queue depths for detection and analysis queues
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AIServiceOverallStatus(str, Enum):
    """Overall status for the AI services subsystem.

    Statuses:
    - healthy: All services are operational
    - degraded: Some services are unhealthy but system is functional
    - critical: Critical services are down, system cannot process requests
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class AIServiceCircuitState(str, Enum):
    """Circuit breaker state for an AI service.

    States:
    - closed: Normal operation, requests pass through
    - open: Service failing, requests fail immediately
    - half_open: Testing recovery, limited requests allowed
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AIServiceStatus(str, Enum):
    """Health status for an individual AI service.

    Statuses:
    - healthy: Service is fully operational
    - unhealthy: Service is down or experiencing critical issues
    - degraded: Service is partially operational
    - unknown: Service status cannot be determined
    """

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class AIServiceHealthDetail(BaseModel):
    """Detailed health information for a single AI service.

    Provides comprehensive status including circuit breaker state,
    error rates, and latency metrics for monitoring and alerting.
    """

    status: AIServiceStatus = Field(
        ...,
        description="Current health status of the service",
    )
    circuit_state: AIServiceCircuitState = Field(
        default=AIServiceCircuitState.CLOSED,
        description="Circuit breaker state for this service",
    )
    last_health_check: datetime | None = Field(
        default=None,
        description="Timestamp of the last successful health check",
    )
    error_rate_1h: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Error rate over the last hour (0.0 to 1.0)",
    )
    latency_p99_ms: float | None = Field(
        default=None,
        ge=0,
        description="99th percentile latency in milliseconds",
    )
    url: str | None = Field(
        default=None,
        description="Service URL if configured",
    )
    error: str | None = Field(
        default=None,
        description="Error message if service is unhealthy",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "circuit_state": "closed",
                "last_health_check": "2026-01-20T12:00:00Z",
                "error_rate_1h": 0.02,
                "latency_p99_ms": 450,
                "url": "http://ai-yolo26:8095",
                "error": None,
            }
        }
    )


class QueueDepthInfo(BaseModel):
    """Queue depth information for a processing queue.

    Tracks the number of items in the main queue and the dead letter queue
    for monitoring backlog and failed processing.
    """

    depth: int = Field(
        ...,
        ge=0,
        description="Number of items currently in the queue",
    )
    dlq_depth: int = Field(
        default=0,
        ge=0,
        description="Number of items in the dead letter queue",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "depth": 5,
                "dlq_depth": 0,
            }
        }
    )


class AIServicesHealthResponse(BaseModel):
    """Response schema for GET /api/health/ai-services endpoint.

    Provides a unified view of all AI service health including:
    - Overall system status (healthy/degraded/critical)
    - Individual service health with circuit breaker states
    - Queue depths for detection and analysis pipelines

    HTTP Status Codes:
    - 200: System is healthy or degraded (can still serve traffic)
    - 503: Critical services are unhealthy (should not receive traffic)
    """

    overall_status: AIServiceOverallStatus = Field(
        ...,
        description="Overall health status of the AI services subsystem",
    )
    services: dict[str, AIServiceHealthDetail] = Field(
        ...,
        description="Health details for each AI service keyed by service name",
    )
    queues: dict[str, QueueDepthInfo] = Field(
        ...,
        description="Queue depth information for processing queues",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp when this health check was performed",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_status": "healthy",
                "services": {
                    "yolo26": {
                        "status": "healthy",
                        "circuit_state": "closed",
                        "last_health_check": "2026-01-20T12:00:00Z",
                        "error_rate_1h": 0.02,
                        "latency_p99_ms": 450,
                        "url": "http://ai-yolo26:8095",
                        "error": None,
                    },
                    "nemotron": {
                        "status": "healthy",
                        "circuit_state": "closed",
                        "last_health_check": "2026-01-20T12:00:00Z",
                        "error_rate_1h": 0.01,
                        "latency_p99_ms": 2500,
                        "url": "http://llm-analyzer:8080",
                        "error": None,
                    },
                    "florence": {
                        "status": "healthy",
                        "circuit_state": "closed",
                        "last_health_check": "2026-01-20T12:00:00Z",
                        "error_rate_1h": 0.0,
                        "latency_p99_ms": 350,
                        "url": "http://florence-service:8091",
                        "error": None,
                    },
                    "clip": {
                        "status": "healthy",
                        "circuit_state": "closed",
                        "last_health_check": "2026-01-20T12:00:00Z",
                        "error_rate_1h": 0.0,
                        "latency_p99_ms": 200,
                        "url": "http://clip-service:8092",
                        "error": None,
                    },
                    "enrichment": {
                        "status": "degraded",
                        "circuit_state": "half_open",
                        "last_health_check": "2026-01-20T11:55:00Z",
                        "error_rate_1h": 0.15,
                        "latency_p99_ms": 1200,
                        "url": "http://enrichment-service:8093",
                        "error": "Intermittent connection issues",
                    },
                },
                "queues": {
                    "detection_queue": {"depth": 5, "dlq_depth": 0},
                    "analysis_queue": {"depth": 2, "dlq_depth": 0},
                },
                "timestamp": "2026-01-20T12:00:00Z",
            }
        }
    )
