"""Pydantic schemas for service management API (container orchestrator).

This module provides schemas for the container orchestrator endpoints that manage
the lifecycle of deployment containers including AI services (YOLO26, Nemotron,
Florence, CLIP, Enrichment), infrastructure (PostgreSQL, Redis), and monitoring
(Grafana, Prometheus, Redis Exporter, JSON Exporter).
"""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, Field


class ServiceCategory(StrEnum):
    """Service category for classification and restart policy.

    Categories determine restart behavior and priority:
    - INFRASTRUCTURE: Critical services (PostgreSQL, Redis) with aggressive restart
    - AI: AI/ML services with standard backoff
    - MONITORING: Optional monitoring services with lenient restart
    """

    INFRASTRUCTURE = auto()  # PostgreSQL, Redis - critical
    AI = auto()  # YOLO26, Nemotron, Florence, CLIP, Enrichment
    MONITORING = auto()  # Grafana, Prometheus - optional


class ContainerServiceStatus(StrEnum):
    """Current status of a managed container service.

    Status values:
    - RUNNING: Container is up and passing health checks
    - STARTING: Container is starting, not yet healthy
    - UNHEALTHY: Running but failing health checks
    - STOPPED: Container is not running
    - DISABLED: Exceeded failure limit, requires manual reset
    - NOT_FOUND: Container doesn't exist yet
    """

    RUNNING = auto()  # Container up and healthy
    STARTING = auto()  # Container starting, not yet healthy
    UNHEALTHY = auto()  # Running but failing health checks
    STOPPED = auto()  # Container not running
    DISABLED = auto()  # Exceeded failure limit, requires manual reset
    NOT_FOUND = auto()  # Container doesn't exist


class ServiceInfo(BaseModel):
    """Information about a single managed service.

    Contains identity, configuration, and runtime status for a container
    managed by the orchestrator.
    """

    name: str = Field(
        ...,
        description="Service identifier (e.g., 'ai-yolo26', 'postgres', 'grafana')",
    )
    display_name: str = Field(
        ...,
        description="Human-readable display name (e.g., 'YOLO26v2', 'PostgreSQL')",
    )
    category: ServiceCategory = Field(
        ...,
        description="Service category: infrastructure, ai, or monitoring",
    )
    status: ContainerServiceStatus = Field(
        ...,
        description="Current service status: running, starting, unhealthy, stopped, disabled, not_found",
    )
    enabled: bool = Field(
        True,
        description="Whether auto-restart is enabled for this service",
    )
    container_id: str | None = Field(
        None,
        description="Docker container ID (short form)",
    )
    image: str | None = Field(
        None,
        description="Container image (e.g., 'postgres:16-alpine', 'ghcr.io/.../yolo26:latest')",
    )
    port: int = Field(
        ...,
        description="Primary service port",
        ge=1,
        le=65535,
    )
    failure_count: int = Field(
        0,
        description="Consecutive health check failure count",
        ge=0,
    )
    restart_count: int = Field(
        0,
        description="Total restarts since backend boot",
        ge=0,
    )
    last_restart_at: datetime | None = Field(
        None,
        description="Timestamp of last restart (null if never restarted)",
    )
    uptime_seconds: int | None = Field(
        None,
        description="Seconds since container started (null if not running)",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "ai-yolo26",
                "display_name": "YOLO26v2",
                "category": "ai",
                "status": "running",
                "enabled": True,
                "container_id": "abc123def456",
                "image": "ghcr.io/.../yolo26:latest",
                "port": 8095,
                "failure_count": 0,
                "restart_count": 2,
                "last_restart_at": "2026-01-05T10:30:00Z",
                "uptime_seconds": 3600,
            }
        }
    )


class CategorySummary(BaseModel):
    """Summary of services in a category.

    Provides a quick overview of service health within a category
    for dashboard displays.
    """

    total: int = Field(
        ...,
        description="Total number of services in this category",
        ge=0,
    )
    healthy: int = Field(
        ...,
        description="Number of healthy (running) services",
        ge=0,
    )
    unhealthy: int = Field(
        ...,
        description="Number of unhealthy/stopped/disabled services",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 5,
                "healthy": 3,
                "unhealthy": 2,
            }
        }
    )


class ServicesResponse(BaseModel):
    """Response for GET /api/system/services.

    Returns a list of all managed services with their current status
    and category-level summaries.
    """

    services: list[ServiceInfo] = Field(
        ...,
        description="List of all managed services with current status",
    )
    by_category: dict[str, CategorySummary] = Field(
        ...,
        description="Health summary by category (infrastructure, ai, monitoring)",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of status snapshot",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "services": [
                    {
                        "name": "postgres",
                        "display_name": "PostgreSQL",
                        "category": "infrastructure",
                        "status": "running",
                        "enabled": True,
                        "container_id": "def456...",
                        "image": "postgres:16-alpine",
                        "port": 5432,
                        "failure_count": 0,
                        "restart_count": 0,
                        "last_restart_at": None,
                        "uptime_seconds": 86400,
                    },
                    {
                        "name": "ai-yolo26",
                        "display_name": "YOLO26v2",
                        "category": "ai",
                        "status": "running",
                        "enabled": True,
                        "container_id": "abc123...",
                        "image": "ghcr.io/.../yolo26:latest",
                        "port": 8095,
                        "failure_count": 0,
                        "restart_count": 2,
                        "last_restart_at": "2026-01-05T10:30:00Z",
                        "uptime_seconds": 3600,
                    },
                ],
                "by_category": {
                    "infrastructure": {"total": 2, "healthy": 2, "unhealthy": 0},
                    "ai": {"total": 5, "healthy": 3, "unhealthy": 2},
                    "monitoring": {"total": 4, "healthy": 4, "unhealthy": 0},
                },
                "timestamp": "2026-01-05T15:45:00Z",
            }
        }
    )


class ServiceActionResponse(BaseModel):
    """Response for service action endpoints (restart, enable, disable, start).

    Returned after POST /api/system/services/{name}/restart, enable, disable, or start.
    """

    success: bool = Field(
        ...,
        description="Whether the action completed successfully",
    )
    message: str = Field(
        ...,
        description="Human-readable result message",
    )
    service: ServiceInfo = Field(
        ...,
        description="Updated service information after the action",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Service restarted successfully",
                "service": {
                    "name": "ai-yolo26",
                    "display_name": "YOLO26v2",
                    "category": "ai",
                    "status": "starting",
                    "enabled": True,
                    "container_id": "abc123...",
                    "image": "ghcr.io/.../yolo26:latest",
                    "port": 8095,
                    "failure_count": 0,
                    "restart_count": 3,
                    "last_restart_at": "2026-01-05T15:50:00Z",
                    "uptime_seconds": None,
                },
            }
        }
    )


class ServiceStatusEvent(BaseModel):
    """WebSocket event for service status changes.

    Broadcast to connected clients when a service status changes,
    enabling real-time UI updates.
    """

    type: str = Field(
        default="service_status",
        description="Event type identifier for WebSocket routing",
    )
    data: ServiceInfo = Field(
        ...,
        description="Updated service information",
    )
    message: str | None = Field(
        None,
        description="Optional human-readable message about the status change",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "service_status",
                "data": {
                    "name": "ai-florence",
                    "display_name": "Florence-2",
                    "category": "ai",
                    "status": "unhealthy",
                    "enabled": True,
                    "container_id": "ghi789...",
                    "image": "ghcr.io/.../florence:latest",
                    "port": 8092,
                    "failure_count": 3,
                    "restart_count": 1,
                    "last_restart_at": "2026-01-05T15:30:00Z",
                    "uptime_seconds": 1200,
                },
                "message": "Health check failed, restart scheduled",
            }
        }
    )
