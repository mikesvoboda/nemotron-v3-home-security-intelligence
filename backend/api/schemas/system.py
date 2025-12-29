"""Pydantic schemas for system API endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SeverityEnum(str, Enum):
    """Severity levels for API responses."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


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
        le=365,
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
        le=365,
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


# =============================================================================
# Telemetry Schemas
# =============================================================================


class QueueDepths(BaseModel):
    """Queue depth information for pipeline queues."""

    detection_queue: int = Field(
        ...,
        description="Number of items in detection queue waiting for RT-DETRv2 processing",
        ge=0,
    )
    analysis_queue: int = Field(
        ...,
        description="Number of batches in analysis queue waiting for Nemotron LLM analysis",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection_queue": 5,
                "analysis_queue": 2,
            }
        }
    )


class StageLatency(BaseModel):
    """Latency statistics for a single pipeline stage."""

    avg_ms: float | None = Field(
        None,
        description="Average latency in milliseconds",
        ge=0,
    )
    min_ms: float | None = Field(
        None,
        description="Minimum latency in milliseconds",
        ge=0,
    )
    max_ms: float | None = Field(
        None,
        description="Maximum latency in milliseconds",
        ge=0,
    )
    p50_ms: float | None = Field(
        None,
        description="50th percentile (median) latency in milliseconds",
        ge=0,
    )
    p95_ms: float | None = Field(
        None,
        description="95th percentile latency in milliseconds",
        ge=0,
    )
    p99_ms: float | None = Field(
        None,
        description="99th percentile latency in milliseconds",
        ge=0,
    )
    sample_count: int = Field(
        ...,
        description="Number of samples used to calculate statistics",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "avg_ms": 150.5,
                "min_ms": 50.0,
                "max_ms": 500.0,
                "p50_ms": 120.0,
                "p95_ms": 400.0,
                "p99_ms": 480.0,
                "sample_count": 100,
            }
        }
    )


class PipelineLatencies(BaseModel):
    """Latency statistics for all pipeline stages.

    Pipeline stages:
    - watch: File watcher detecting new images (file event -> queue)
    - detect: RT-DETRv2 object detection (image -> detections)
    - batch: Batch aggregation window (detections -> batch)
    - analyze: Nemotron LLM risk analysis (batch -> event)
    """

    watch: StageLatency | None = Field(
        None,
        description="File watcher stage latency (file event to queue)",
    )
    detect: StageLatency | None = Field(
        None,
        description="Object detection stage latency (RT-DETRv2 inference)",
    )
    batch: StageLatency | None = Field(
        None,
        description="Batch aggregation window time",
    )
    analyze: StageLatency | None = Field(
        None,
        description="LLM analysis stage latency (Nemotron inference)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "watch": {
                    "avg_ms": 10.0,
                    "min_ms": 5.0,
                    "max_ms": 50.0,
                    "p50_ms": 8.0,
                    "p95_ms": 40.0,
                    "p99_ms": 48.0,
                    "sample_count": 500,
                },
                "detect": {
                    "avg_ms": 200.0,
                    "min_ms": 100.0,
                    "max_ms": 800.0,
                    "p50_ms": 180.0,
                    "p95_ms": 600.0,
                    "p99_ms": 750.0,
                    "sample_count": 500,
                },
                "batch": {
                    "avg_ms": 30000.0,
                    "min_ms": 5000.0,
                    "max_ms": 90000.0,
                    "p50_ms": 25000.0,
                    "p95_ms": 80000.0,
                    "p99_ms": 88000.0,
                    "sample_count": 100,
                },
                "analyze": {
                    "avg_ms": 5000.0,
                    "min_ms": 2000.0,
                    "max_ms": 15000.0,
                    "p50_ms": 4500.0,
                    "p95_ms": 12000.0,
                    "p99_ms": 14000.0,
                    "sample_count": 100,
                },
            }
        }
    )


class TelemetryResponse(BaseModel):
    """Response schema for pipeline telemetry endpoint.

    Provides real-time visibility into:
    - Queue depths: How many items are waiting in detection/analysis queues
    - Stage latencies: How long each pipeline stage is taking

    This helps operators:
    - Identify pipeline bottlenecks
    - Detect backlog situations
    - Monitor processing performance
    - Debug pipeline stalls
    """

    queues: QueueDepths = Field(
        ...,
        description="Current queue depths for detection and analysis queues",
    )
    latencies: PipelineLatencies | None = Field(
        None,
        description="Latency statistics for each pipeline stage",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of telemetry snapshot",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "queues": {
                    "detection_queue": 5,
                    "analysis_queue": 2,
                },
                "latencies": {
                    "watch": {
                        "avg_ms": 10.0,
                        "min_ms": 5.0,
                        "max_ms": 50.0,
                        "p50_ms": 8.0,
                        "p95_ms": 40.0,
                        "p99_ms": 48.0,
                        "sample_count": 500,
                    },
                    "detect": {
                        "avg_ms": 200.0,
                        "min_ms": 100.0,
                        "max_ms": 800.0,
                        "p50_ms": 180.0,
                        "p95_ms": 600.0,
                        "p99_ms": 750.0,
                        "sample_count": 500,
                    },
                    "batch": None,
                    "analyze": None,
                },
                "timestamp": "2025-12-27T10:30:00Z",
            }
        }
    )


# =============================================================================
# Cleanup Schemas
# =============================================================================


# =============================================================================
# Pipeline Latency Schemas
# =============================================================================


class PipelineStageLatency(BaseModel):
    """Latency statistics for a single pipeline transition stage.

    Tracks time between pipeline stages:
    - watch_to_detect: File detection to RT-DETR processing
    - detect_to_batch: Detection to batch aggregation
    - batch_to_analyze: Batch to Nemotron analysis
    - total_pipeline: End-to-end latency
    """

    avg_ms: float | None = Field(
        None,
        description="Average latency in milliseconds",
        ge=0,
    )
    min_ms: float | None = Field(
        None,
        description="Minimum latency in milliseconds",
        ge=0,
    )
    max_ms: float | None = Field(
        None,
        description="Maximum latency in milliseconds",
        ge=0,
    )
    p50_ms: float | None = Field(
        None,
        description="50th percentile (median) latency in milliseconds",
        ge=0,
    )
    p95_ms: float | None = Field(
        None,
        description="95th percentile latency in milliseconds",
        ge=0,
    )
    p99_ms: float | None = Field(
        None,
        description="99th percentile latency in milliseconds",
        ge=0,
    )
    sample_count: int = Field(
        ...,
        description="Number of samples used to calculate statistics",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "avg_ms": 150.5,
                "min_ms": 50.0,
                "max_ms": 500.0,
                "p50_ms": 120.0,
                "p95_ms": 400.0,
                "p99_ms": 480.0,
                "sample_count": 100,
            }
        }
    )


class PipelineLatencyResponse(BaseModel):
    """Response schema for pipeline latency endpoint.

    Provides latency metrics for each stage transition in the AI pipeline:
    - watch_to_detect: Time from file watcher detecting image to RT-DETR processing start
    - detect_to_batch: Time from detection completion to batch aggregation
    - batch_to_analyze: Time from batch completion to Nemotron analysis start
    - total_pipeline: Total end-to-end processing time
    """

    watch_to_detect: PipelineStageLatency | None = Field(
        None,
        description="Latency from file detection to RT-DETR processing",
    )
    detect_to_batch: PipelineStageLatency | None = Field(
        None,
        description="Latency from detection to batch aggregation",
    )
    batch_to_analyze: PipelineStageLatency | None = Field(
        None,
        description="Latency from batch to Nemotron analysis",
    )
    total_pipeline: PipelineStageLatency | None = Field(
        None,
        description="Total end-to-end pipeline latency",
    )
    window_minutes: int = Field(
        ...,
        description="Time window used for calculating statistics",
        ge=1,
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of latency snapshot",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "watch_to_detect": {
                    "avg_ms": 50.0,
                    "min_ms": 10.0,
                    "max_ms": 200.0,
                    "p50_ms": 40.0,
                    "p95_ms": 150.0,
                    "p99_ms": 180.0,
                    "sample_count": 500,
                },
                "detect_to_batch": {
                    "avg_ms": 100.0,
                    "min_ms": 20.0,
                    "max_ms": 500.0,
                    "p50_ms": 80.0,
                    "p95_ms": 400.0,
                    "p99_ms": 480.0,
                    "sample_count": 500,
                },
                "batch_to_analyze": {
                    "avg_ms": 5000.0,
                    "min_ms": 2000.0,
                    "max_ms": 15000.0,
                    "p50_ms": 4500.0,
                    "p95_ms": 12000.0,
                    "p99_ms": 14000.0,
                    "sample_count": 100,
                },
                "total_pipeline": {
                    "avg_ms": 35000.0,
                    "min_ms": 10000.0,
                    "max_ms": 120000.0,
                    "p50_ms": 30000.0,
                    "p95_ms": 100000.0,
                    "p99_ms": 110000.0,
                    "sample_count": 100,
                },
                "window_minutes": 60,
                "timestamp": "2025-12-28T10:30:00Z",
            }
        }
    )


class CleanupResponse(BaseModel):
    """Response schema for data cleanup endpoint.

    Returns statistics about the cleanup operation including counts of
    deleted records and files. When dry_run is True, the counts represent
    what would be deleted without actually deleting.
    """

    events_deleted: int = Field(
        ...,
        description="Number of events deleted (or would be deleted in dry run)",
        ge=0,
    )
    detections_deleted: int = Field(
        ...,
        description="Number of detections deleted (or would be deleted in dry run)",
        ge=0,
    )
    gpu_stats_deleted: int = Field(
        ...,
        description="Number of GPU stat records deleted (or would be deleted in dry run)",
        ge=0,
    )
    logs_deleted: int = Field(
        ...,
        description="Number of log records deleted (or would be deleted in dry run)",
        ge=0,
    )
    thumbnails_deleted: int = Field(
        ...,
        description="Number of thumbnail files deleted (or would be deleted in dry run)",
        ge=0,
    )
    images_deleted: int = Field(
        ...,
        description="Number of original image files deleted (or would be deleted in dry run)",
        ge=0,
    )
    space_reclaimed: int = Field(
        ...,
        description="Estimated disk space freed in bytes (or would be freed in dry run)",
        ge=0,
    )
    retention_days: int = Field(
        ...,
        description="Retention period used for cleanup",
        ge=1,
        le=365,
    )
    dry_run: bool = Field(
        default=False,
        description="Whether this was a dry run (no actual deletion performed)",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of cleanup operation",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "events_deleted": 15,
                "detections_deleted": 89,
                "gpu_stats_deleted": 2880,
                "logs_deleted": 150,
                "thumbnails_deleted": 89,
                "images_deleted": 0,
                "space_reclaimed": 524288000,
                "retention_days": 30,
                "dry_run": False,
                "timestamp": "2025-12-27T10:30:00Z",
            }
        }
    )


# =============================================================================
# Severity Schemas
# =============================================================================


class SeverityDefinitionResponse(BaseModel):
    """Definition of a single severity level."""

    severity: SeverityEnum = Field(
        ...,
        description="The severity level identifier",
    )
    label: str = Field(
        ...,
        description="Human-readable label for the severity level",
    )
    description: str = Field(
        ...,
        description="Description of when this severity applies",
    )
    color: str = Field(
        ...,
        description="Hex color code for UI display (e.g., '#22c55e')",
        pattern=r"^#[0-9a-fA-F]{6}$",
    )
    priority: int = Field(
        ...,
        description="Sort priority (0 = highest priority, 3 = lowest)",
        ge=0,
        le=3,
    )
    min_score: int = Field(
        ...,
        description="Minimum risk score for this severity (inclusive)",
        ge=0,
        le=100,
    )
    max_score: int = Field(
        ...,
        description="Maximum risk score for this severity (inclusive)",
        ge=0,
        le=100,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "severity": "high",
                "label": "High",
                "description": "Concerning activity, review soon",
                "color": "#f97316",
                "priority": 1,
                "min_score": 60,
                "max_score": 84,
            }
        }
    )


class SeverityThresholds(BaseModel):
    """Current severity threshold configuration."""

    low_max: int = Field(
        ...,
        description="Maximum risk score for LOW severity (0 to this value = LOW)",
        ge=0,
        le=100,
    )
    medium_max: int = Field(
        ...,
        description="Maximum risk score for MEDIUM severity (low_max+1 to this value = MEDIUM)",
        ge=0,
        le=100,
    )
    high_max: int = Field(
        ...,
        description="Maximum risk score for HIGH severity (medium_max+1 to this value = HIGH)",
        ge=0,
        le=100,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "low_max": 29,
                "medium_max": 59,
                "high_max": 84,
            }
        }
    )


class SeverityMetadataResponse(BaseModel):
    """Response schema for severity metadata endpoint.

    Provides complete information about severity levels including:
    - All severity definitions with thresholds and colors
    - Current threshold configuration
    - Useful for frontend to display severity information consistently
    """

    definitions: list[SeverityDefinitionResponse] = Field(
        ...,
        description="List of all severity level definitions",
    )
    thresholds: SeverityThresholds = Field(
        ...,
        description="Current severity threshold configuration",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "definitions": [
                    {
                        "severity": "low",
                        "label": "Low",
                        "description": "Routine activity, no concern",
                        "color": "#22c55e",
                        "priority": 3,
                        "min_score": 0,
                        "max_score": 29,
                    },
                    {
                        "severity": "medium",
                        "label": "Medium",
                        "description": "Notable activity, worth reviewing",
                        "color": "#eab308",
                        "priority": 2,
                        "min_score": 30,
                        "max_score": 59,
                    },
                    {
                        "severity": "high",
                        "label": "High",
                        "description": "Concerning activity, review soon",
                        "color": "#f97316",
                        "priority": 1,
                        "min_score": 60,
                        "max_score": 84,
                    },
                    {
                        "severity": "critical",
                        "label": "Critical",
                        "description": "Immediate attention required",
                        "color": "#ef4444",
                        "priority": 0,
                        "min_score": 85,
                        "max_score": 100,
                    },
                ],
                "thresholds": {
                    "low_max": 29,
                    "medium_max": 59,
                    "high_max": 84,
                },
            }
        }
    )
