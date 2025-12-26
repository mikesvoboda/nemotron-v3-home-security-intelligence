"""Pydantic schemas for system API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceStatus(BaseModel):
    """Status information for a service component."""

    status: str = Field(
        ...,
        description="Service status: healthy, unhealthy, or not_initialized",
    )
    message: str | None = Field(
        None,
        description="Optional status message or error details",
    )
    details: dict[str, str] | None = Field(
        None,
        description="Additional service-specific details",
    )


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str = Field(
        ...,
        description="Overall system status: healthy, degraded, or unhealthy",
    )
    services: dict[str, ServiceStatus] = Field(
        ...,
        description="Status of individual services (database, redis, ai)",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of health check",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "services": {
                    "database": {
                        "status": "healthy",
                        "message": "Database operational",
                        "details": None,
                    },
                    "redis": {
                        "status": "healthy",
                        "message": "Redis connected",
                        "details": {"redis_version": "7.0.0"},
                    },
                    "ai": {
                        "status": "healthy",
                        "message": "AI services operational",
                        "details": None,
                    },
                },
                "timestamp": "2025-12-23T10:30:00",
            }
        }
    )


class GPUStatsResponse(BaseModel):
    """Response schema for GPU statistics endpoint."""

    utilization: float | None = Field(
        None,
        description="GPU utilization percentage (0-100)",
        ge=0,
        le=100,
    )
    memory_used: int | None = Field(
        None,
        description="GPU memory used in MB",
        ge=0,
    )
    memory_total: int | None = Field(
        None,
        description="Total GPU memory in MB",
        ge=0,
    )
    temperature: float | None = Field(
        None,
        description="GPU temperature in Celsius",
    )
    inference_fps: float | None = Field(
        None,
        description="Inference frames per second",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "utilization": 75.5,
                "memory_used": 12000,
                "memory_total": 24000,
                "temperature": 65.0,
                "inference_fps": 30.5,
            }
        }
    )


class GPUStatsSample(BaseModel):
    """Single time-series sample of GPU statistics."""

    recorded_at: datetime = Field(..., description="When the GPU sample was recorded (UTC)")
    utilization: float | None = Field(
        None,
        description="GPU utilization percentage (0-100)",
        ge=0,
        le=100,
    )
    memory_used: int | None = Field(None, description="GPU memory used in MB", ge=0)
    memory_total: int | None = Field(None, description="Total GPU memory in MB", ge=0)
    temperature: float | None = Field(None, description="GPU temperature in Celsius")
    inference_fps: float | None = Field(None, description="Inference frames per second", ge=0)

    model_config = ConfigDict(from_attributes=True)


class GPUStatsHistoryResponse(BaseModel):
    """Response schema for GPU stats history endpoint."""

    samples: list[GPUStatsSample] = Field(
        ..., description="GPU stats samples (chronological order)"
    )
    count: int = Field(..., description="Number of samples returned", ge=0)
    limit: int = Field(..., description="Applied limit", ge=1)


class ConfigResponse(BaseModel):
    """Response schema for configuration endpoint.

    Only includes public, non-sensitive configuration values.
    """

    app_name: str = Field(
        ...,
        description="Application name",
    )
    version: str = Field(
        ...,
        description="Application version",
    )
    retention_days: int = Field(
        ...,
        description="Number of days to retain events and detections",
        ge=1,
    )
    batch_window_seconds: int = Field(
        ...,
        description="Time window for batch processing detections",
        ge=1,
    )
    batch_idle_timeout_seconds: int = Field(
        ...,
        description="Idle timeout before processing incomplete batch",
        ge=1,
    )
    detection_confidence_threshold: float = Field(
        ...,
        description="Minimum confidence threshold for detections (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_name": "Home Security Intelligence",
                "version": "0.1.0",
                "retention_days": 30,
                "batch_window_seconds": 90,
                "batch_idle_timeout_seconds": 30,
                "detection_confidence_threshold": 0.5,
            }
        }
    )


class ConfigUpdateRequest(BaseModel):
    """Request schema for PATCH /api/system/config.

    Only supports a subset of processing-related settings.
    """

    retention_days: int | None = Field(
        None,
        description="Number of days to retain events and detections",
        ge=1,
    )
    batch_window_seconds: int | None = Field(
        None,
        description="Time window for batch processing detections",
        ge=1,
    )
    batch_idle_timeout_seconds: int | None = Field(
        None,
        description="Idle timeout before processing incomplete batch",
        ge=1,
    )
    detection_confidence_threshold: float | None = Field(
        None,
        description="Minimum confidence threshold for detections (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )


class SystemStatsResponse(BaseModel):
    """Response schema for system statistics endpoint."""

    total_cameras: int = Field(
        ...,
        description="Total number of cameras in the system",
        ge=0,
    )
    total_events: int = Field(
        ...,
        description="Total number of events recorded",
        ge=0,
    )
    total_detections: int = Field(
        ...,
        description="Total number of detections recorded",
        ge=0,
    )
    uptime_seconds: float = Field(
        ...,
        description="Application uptime in seconds",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_cameras": 4,
                "total_events": 156,
                "total_detections": 892,
                "uptime_seconds": 86400.5,
            }
        }
    )


class LivenessResponse(BaseModel):
    """Response schema for liveness probe endpoint.

    Liveness probes indicate whether the process is running and able to
    respond to HTTP requests. This is a minimal check that always returns
    200 if the process is up.
    """

    status: str = Field(
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


class WorkerStatus(BaseModel):
    """Status information for a background worker/service."""

    name: str = Field(
        ...,
        description="Worker/service name",
    )
    running: bool = Field(
        ...,
        description="Whether the worker is currently running",
    )
    message: str | None = Field(
        None,
        description="Optional status message or error details",
    )


class ReadinessResponse(BaseModel):
    """Response schema for readiness probe endpoint.

    Readiness probes indicate whether the application is ready to receive
    traffic and process requests. This checks all dependencies:
    - Database connectivity
    - Redis connectivity
    - AI services availability
    - Background worker status
    """

    ready: bool = Field(
        ...,
        description="Overall readiness status: True if system can process requests",
    )
    status: str = Field(
        ...,
        description="Status string: 'ready', 'degraded', or 'not_ready'",
    )
    services: dict[str, ServiceStatus] = Field(
        ...,
        description="Status of infrastructure services (database, redis, ai)",
    )
    workers: list[WorkerStatus] = Field(
        default_factory=list,
        description="Status of background workers",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of readiness check",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ready": True,
                "status": "ready",
                "services": {
                    "database": {
                        "status": "healthy",
                        "message": "Database operational",
                        "details": None,
                    },
                    "redis": {
                        "status": "healthy",
                        "message": "Redis connected",
                        "details": {"redis_version": "7.0.0"},
                    },
                    "ai": {
                        "status": "healthy",
                        "message": "AI services operational",
                        "details": None,
                    },
                },
                "workers": [
                    {"name": "gpu_monitor", "running": True, "message": None},
                    {"name": "cleanup_service", "running": True, "message": None},
                ],
                "timestamp": "2025-12-23T10:30:00",
            }
        }
    )
