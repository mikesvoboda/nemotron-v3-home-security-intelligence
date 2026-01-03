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

    gpu_name: str | None = Field(
        None,
        description="GPU device name (e.g., 'NVIDIA RTX A5500')",
    )
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
    power_usage: float | None = Field(
        None,
        description="GPU power usage in watts",
        ge=0,
    )
    inference_fps: float | None = Field(
        None,
        description="Inference frames per second",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "gpu_name": "NVIDIA RTX A5500",
                "utilization": 75.5,
                "memory_used": 12000,
                "memory_total": 24000,
                "temperature": 65.0,
                "power_usage": 150.0,
                "inference_fps": 30.5,
            }
        }
    )


class GPUStatsSample(BaseModel):
    """Single time-series sample of GPU statistics."""

    recorded_at: datetime = Field(..., description="When the GPU sample was recorded (UTC)")
    gpu_name: str | None = Field(None, description="GPU device name")
    utilization: float | None = Field(
        None,
        description="GPU utilization percentage (0-100)",
        ge=0,
        le=100,
    )
    memory_used: int | None = Field(None, description="GPU memory used in MB", ge=0)
    memory_total: int | None = Field(None, description="Total GPU memory in MB", ge=0)
    temperature: float | None = Field(None, description="GPU temperature in Celsius")
    power_usage: float | None = Field(None, description="GPU power usage in watts", ge=0)
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
    grafana_url: str = Field(
        ...,
        description="Grafana dashboard URL for frontend link",
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
                "grafana_url": "http://localhost:3002",
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


# =============================================================================
# Storage Schemas
# =============================================================================


class StorageCategoryStats(BaseModel):
    """Storage statistics for a single category."""

    file_count: int = Field(
        ...,
        description="Number of files in this category",
        ge=0,
    )
    size_bytes: int = Field(
        ...,
        description="Total size in bytes for this category",
        ge=0,
    )


class StorageStatsResponse(BaseModel):
    """Response schema for storage statistics endpoint.

    Provides detailed storage usage information including:
    - Disk usage for the storage volume
    - Breakdown by data category (thumbnails, images, clips)
    - Database record counts
    """

    # Disk usage
    disk_used_bytes: int = Field(
        ...,
        description="Total disk space used in bytes",
        ge=0,
    )
    disk_total_bytes: int = Field(
        ...,
        description="Total disk space available in bytes",
        ge=0,
    )
    disk_free_bytes: int = Field(
        ...,
        description="Free disk space in bytes",
        ge=0,
    )
    disk_usage_percent: float = Field(
        ...,
        description="Disk usage percentage (0-100)",
        ge=0,
        le=100,
    )

    # Storage breakdown by category
    thumbnails: StorageCategoryStats = Field(
        ...,
        description="Storage used by detection thumbnails",
    )
    images: StorageCategoryStats = Field(
        ...,
        description="Storage used by original camera images",
    )
    clips: StorageCategoryStats = Field(
        ...,
        description="Storage used by event video clips",
    )

    # Database record counts
    events_count: int = Field(
        ...,
        description="Total number of events in database",
        ge=0,
    )
    detections_count: int = Field(
        ...,
        description="Total number of detections in database",
        ge=0,
    )
    gpu_stats_count: int = Field(
        ...,
        description="Total number of GPU stats records in database",
        ge=0,
    )
    logs_count: int = Field(
        ...,
        description="Total number of log entries in database",
        ge=0,
    )

    timestamp: datetime = Field(
        ...,
        description="Timestamp of storage stats snapshot",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "disk_used_bytes": 107374182400,
                "disk_total_bytes": 536870912000,
                "disk_free_bytes": 429496729600,
                "disk_usage_percent": 20.0,
                "thumbnails": {
                    "file_count": 1500,
                    "size_bytes": 75000000,
                },
                "images": {
                    "file_count": 10000,
                    "size_bytes": 5000000000,
                },
                "clips": {
                    "file_count": 50,
                    "size_bytes": 500000000,
                },
                "events_count": 156,
                "detections_count": 892,
                "gpu_stats_count": 2880,
                "logs_count": 5000,
                "timestamp": "2025-12-30T10:30:00Z",
            }
        }
    )


# =============================================================================
# Circuit Breaker Schemas
# =============================================================================


class CircuitBreakerStateEnum(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerConfigResponse(BaseModel):
    """Configuration for a circuit breaker."""

    failure_threshold: int = Field(
        ...,
        description="Number of failures before opening circuit",
        ge=1,
    )
    recovery_timeout: float = Field(
        ...,
        description="Seconds to wait before transitioning to half-open",
        ge=0,
    )
    half_open_max_calls: int = Field(
        ...,
        description="Maximum calls allowed in half-open state",
        ge=1,
    )
    success_threshold: int = Field(
        ...,
        description="Successes needed in half-open to close circuit",
        ge=1,
    )


class CircuitBreakerStatusResponse(BaseModel):
    """Status of a single circuit breaker."""

    name: str = Field(
        ...,
        description="Circuit breaker name",
    )
    state: CircuitBreakerStateEnum = Field(
        ...,
        description="Current circuit state: closed (normal), open (failing), half_open (testing)",
    )
    failure_count: int = Field(
        ...,
        description="Current consecutive failure count",
        ge=0,
    )
    success_count: int = Field(
        ...,
        description="Current consecutive success count (relevant in half-open)",
        ge=0,
    )
    total_calls: int = Field(
        ...,
        description="Total calls attempted through this circuit",
        ge=0,
    )
    rejected_calls: int = Field(
        ...,
        description="Calls rejected due to open circuit",
        ge=0,
    )
    last_failure_time: float | None = Field(
        None,
        description="Monotonic time of last failure (seconds)",
    )
    opened_at: float | None = Field(
        None,
        description="Monotonic time when circuit opened (seconds)",
    )
    config: CircuitBreakerConfigResponse = Field(
        ...,
        description="Circuit breaker configuration",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "ai_service",
                "state": "closed",
                "failure_count": 0,
                "success_count": 0,
                "total_calls": 150,
                "rejected_calls": 0,
                "last_failure_time": None,
                "opened_at": None,
                "config": {
                    "failure_threshold": 5,
                    "recovery_timeout": 30.0,
                    "half_open_max_calls": 3,
                    "success_threshold": 2,
                },
            }
        }
    )


class CircuitBreakersResponse(BaseModel):
    """Response schema for circuit breakers status endpoint."""

    circuit_breakers: dict[str, CircuitBreakerStatusResponse] = Field(
        ...,
        description="Status of all circuit breakers keyed by name",
    )
    total_count: int = Field(
        ...,
        description="Total number of circuit breakers",
        ge=0,
    )
    open_count: int = Field(
        ...,
        description="Number of circuit breakers currently open",
        ge=0,
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of status snapshot",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "circuit_breakers": {
                    "rtdetr": {
                        "name": "rtdetr",
                        "state": "closed",
                        "failure_count": 0,
                        "success_count": 0,
                        "total_calls": 100,
                        "rejected_calls": 0,
                        "last_failure_time": None,
                        "opened_at": None,
                        "config": {
                            "failure_threshold": 5,
                            "recovery_timeout": 30.0,
                            "half_open_max_calls": 3,
                            "success_threshold": 2,
                        },
                    },
                },
                "total_count": 2,
                "open_count": 0,
                "timestamp": "2025-12-30T10:30:00Z",
            }
        }
    )


class CircuitBreakerResetResponse(BaseModel):
    """Response for circuit breaker reset operation."""

    name: str = Field(
        ...,
        description="Name of the circuit breaker that was reset",
    )
    previous_state: CircuitBreakerStateEnum = Field(
        ...,
        description="State before reset",
    )
    new_state: CircuitBreakerStateEnum = Field(
        ...,
        description="State after reset (should be closed)",
    )
    message: str = Field(
        ...,
        description="Human-readable result message",
    )


class WebSocketBroadcasterStatus(BaseModel):
    """Status of a WebSocket broadcaster's circuit breaker."""

    state: CircuitBreakerStateEnum = Field(
        ...,
        description="Current circuit state: closed (normal), open (failing), half_open (testing)",
    )
    failure_count: int = Field(
        ...,
        description="Current consecutive failure count",
        ge=0,
    )
    is_degraded: bool = Field(
        ...,
        description="Whether the broadcaster is in degraded mode",
    )


class WebSocketHealthResponse(BaseModel):
    """Response schema for WebSocket health endpoint."""

    event_broadcaster: WebSocketBroadcasterStatus | None = Field(
        None,
        description="Status of the event broadcaster circuit breaker",
    )
    system_broadcaster: WebSocketBroadcasterStatus | None = Field(
        None,
        description="Status of the system broadcaster circuit breaker",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of health check",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_broadcaster": {
                    "state": "closed",
                    "failure_count": 0,
                    "is_degraded": False,
                },
                "system_broadcaster": {
                    "state": "closed",
                    "failure_count": 0,
                    "is_degraded": False,
                },
                "timestamp": "2025-12-30T10:30:00Z",
            }
        }
    )


# =============================================================================
# Cleanup Status Schemas
# =============================================================================


class CleanupStatusResponse(BaseModel):
    """Response schema for cleanup service status endpoint."""

    running: bool = Field(
        ...,
        description="Whether the cleanup service is currently running",
    )
    retention_days: int = Field(
        ...,
        description="Current retention period in days",
        ge=1,
        le=365,
    )
    cleanup_time: str = Field(
        ...,
        description="Scheduled daily cleanup time in HH:MM format",
    )
    delete_images: bool = Field(
        ...,
        description="Whether original images are deleted during cleanup",
    )
    next_cleanup: str | None = Field(
        None,
        description="ISO timestamp of next scheduled cleanup (null if not running)",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of status snapshot",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "running": True,
                "retention_days": 30,
                "cleanup_time": "03:00",
                "delete_images": False,
                "next_cleanup": "2025-12-31T03:00:00Z",
                "timestamp": "2025-12-30T10:30:00Z",
            }
        }
    )


# =============================================================================
# Pipeline Status Schemas
# =============================================================================


class DegradationModeEnum(str, Enum):
    """System degradation modes."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    OFFLINE = "offline"


class FileWatcherStatusResponse(BaseModel):
    """Status information for the FileWatcher service."""

    running: bool = Field(
        ...,
        description="Whether the file watcher is currently running",
    )
    camera_root: str = Field(
        ...,
        description="Root directory being watched for camera uploads",
    )
    pending_tasks: int = Field(
        ...,
        description="Number of files pending processing (debouncing)",
        ge=0,
    )
    observer_type: str = Field(
        ...,
        description="Type of filesystem observer (native or polling)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "running": True,
                "camera_root": "/export/foscam",
                "pending_tasks": 3,
                "observer_type": "native",
            }
        }
    )


class BatchInfoResponse(BaseModel):
    """Information about an active batch."""

    batch_id: str = Field(
        ...,
        description="Unique batch identifier",
    )
    camera_id: str = Field(
        ...,
        description="Camera ID this batch belongs to",
    )
    detection_count: int = Field(
        ...,
        description="Number of detections in this batch",
        ge=0,
    )
    started_at: float = Field(
        ...,
        description="Batch start time (Unix timestamp)",
    )
    age_seconds: float = Field(
        ...,
        description="Time since batch started in seconds",
        ge=0,
    )
    last_activity_seconds: float = Field(
        ...,
        description="Time since last activity in seconds",
        ge=0,
    )


class BatchAggregatorStatusResponse(BaseModel):
    """Status information for the BatchAggregator service."""

    active_batches: int = Field(
        ...,
        description="Number of active batches being aggregated",
        ge=0,
    )
    batches: list[BatchInfoResponse] = Field(
        default_factory=list,
        description="Details of active batches",
    )
    batch_window_seconds: int = Field(
        ...,
        description="Configured batch window timeout in seconds",
        ge=1,
    )
    idle_timeout_seconds: int = Field(
        ...,
        description="Configured idle timeout in seconds",
        ge=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "active_batches": 2,
                "batches": [
                    {
                        "batch_id": "abc123",
                        "camera_id": "front_door",
                        "detection_count": 5,
                        "started_at": 1735500000.0,
                        "age_seconds": 45.5,
                        "last_activity_seconds": 10.2,
                    }
                ],
                "batch_window_seconds": 90,
                "idle_timeout_seconds": 30,
            }
        }
    )


class ServiceHealthStatusResponse(BaseModel):
    """Health status of a registered service."""

    name: str = Field(
        ...,
        description="Service name",
    )
    status: str = Field(
        ...,
        description="Health status (healthy, unhealthy, unknown)",
    )
    last_check: float | None = Field(
        None,
        description="Monotonic time of last health check",
    )
    consecutive_failures: int = Field(
        ...,
        description="Count of consecutive health check failures",
        ge=0,
    )
    error_message: str | None = Field(
        None,
        description="Last error message if unhealthy",
    )


class DegradationStatusResponse(BaseModel):
    """Status information for the DegradationManager service."""

    mode: DegradationModeEnum = Field(
        ...,
        description="Current degradation mode",
    )
    is_degraded: bool = Field(
        ...,
        description="Whether system is in any degraded state",
    )
    redis_healthy: bool = Field(
        ...,
        description="Whether Redis is healthy",
    )
    memory_queue_size: int = Field(
        ...,
        description="Number of jobs in in-memory fallback queue",
        ge=0,
    )
    fallback_queues: dict[str, int] = Field(
        default_factory=dict,
        description="Count of items in disk-based fallback queues by name",
    )
    services: list[ServiceHealthStatusResponse] = Field(
        default_factory=list,
        description="Health status of registered services",
    )
    available_features: list[str] = Field(
        default_factory=list,
        description="Features available in current degradation mode",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "normal",
                "is_degraded": False,
                "redis_healthy": True,
                "memory_queue_size": 0,
                "fallback_queues": {},
                "services": [
                    {
                        "name": "rtdetr",
                        "status": "healthy",
                        "last_check": 1735500000.0,
                        "consecutive_failures": 0,
                        "error_message": None,
                    }
                ],
                "available_features": ["detection", "analysis", "events", "media"],
            }
        }
    )


class PipelineStatusResponse(BaseModel):
    """Combined status of all pipeline operations.

    Provides visibility into:
    - FileWatcher: Monitoring camera directories for new uploads
    - BatchAggregator: Grouping detections into time-based batches
    - DegradationManager: Graceful degradation and service health
    """

    file_watcher: FileWatcherStatusResponse | None = Field(
        None,
        description="FileWatcher service status (null if not running)",
    )
    batch_aggregator: BatchAggregatorStatusResponse | None = Field(
        None,
        description="BatchAggregator service status (null if not running)",
    )
    degradation: DegradationStatusResponse | None = Field(
        None,
        description="DegradationManager service status (null if not initialized)",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp of status snapshot",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_watcher": {
                    "running": True,
                    "camera_root": "/export/foscam",
                    "pending_tasks": 0,
                    "observer_type": "native",
                },
                "batch_aggregator": {
                    "active_batches": 1,
                    "batches": [],
                    "batch_window_seconds": 90,
                    "idle_timeout_seconds": 30,
                },
                "degradation": {
                    "mode": "normal",
                    "is_degraded": False,
                    "redis_healthy": True,
                    "memory_queue_size": 0,
                    "fallback_queues": {},
                    "services": [],
                    "available_features": ["detection", "analysis", "events", "media"],
                },
                "timestamp": "2025-12-30T10:30:00Z",
            }
        }
    )


# =============================================================================
# Model Zoo Schemas
# =============================================================================


class ModelStatusEnum(str, Enum):
    """Model loading status."""

    LOADED = "loaded"
    UNLOADED = "unloaded"
    DISABLED = "disabled"
    LOADING = "loading"
    ERROR = "error"


class ModelStatusResponse(BaseModel):
    """Status information for a single model in the Model Zoo.

    Provides detailed information about a model including:
    - Identity: name, display_name, category
    - Configuration: vram_mb, enabled, available, path
    - Runtime status: status, load_count
    """

    name: str = Field(
        ...,
        description="Unique identifier for the model (e.g., 'yolo11-license-plate')",
    )
    display_name: str = Field(
        ...,
        description="Human-readable display name for the model",
    )
    vram_mb: int = Field(
        ...,
        description="Estimated VRAM usage in megabytes when loaded",
        ge=0,
    )
    status: ModelStatusEnum = Field(
        ...,
        description="Current loading status: loaded, unloaded, disabled, loading, error",
    )
    category: str = Field(
        ...,
        description="Model category (detection, recognition, ocr, embedding, etc.)",
    )
    enabled: bool = Field(
        ...,
        description="Whether the model is enabled for use",
    )
    available: bool = Field(
        ...,
        description="Whether the model has been successfully loaded at least once",
    )
    path: str = Field(
        ...,
        description="HuggingFace repo path or local file path for the model",
    )
    load_count: int = Field(
        default=0,
        description="Current reference count for loaded model (0 if not loaded)",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "yolo11-license-plate",
                "display_name": "YOLO11 License Plate",
                "vram_mb": 300,
                "status": "unloaded",
                "category": "detection",
                "enabled": True,
                "available": False,
                "path": "/models/model-zoo/yolo11-license-plate/license-plate-finetune-v1n.pt",
                "load_count": 0,
            }
        }
    )


class ModelRegistryResponse(BaseModel):
    """Response schema for model registry endpoint.

    Returns comprehensive information about all models in the Model Zoo
    including VRAM budget, current usage, and individual model statuses.
    """

    vram_budget_mb: int = Field(
        ...,
        description="Total VRAM budget available for Model Zoo models (excludes Nemotron and RT-DETRv2)",
        ge=0,
    )
    vram_used_mb: int = Field(
        ...,
        description="Currently used VRAM by loaded models",
        ge=0,
    )
    vram_available_mb: int = Field(
        ...,
        description="Available VRAM for loading additional models",
        ge=0,
    )
    models: list[ModelStatusResponse] = Field(
        ...,
        description="List of all models in the registry with their status",
    )
    loading_strategy: str = Field(
        default="sequential",
        description="Model loading strategy (sequential = one at a time)",
    )
    max_concurrent_models: int = Field(
        default=1,
        description="Maximum number of models that can be loaded concurrently",
        ge=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vram_budget_mb": 1650,
                "vram_used_mb": 300,
                "vram_available_mb": 1350,
                "models": [
                    {
                        "name": "yolo11-license-plate",
                        "display_name": "YOLO11 License Plate",
                        "vram_mb": 300,
                        "status": "loaded",
                        "category": "detection",
                        "enabled": True,
                        "available": True,
                        "path": "/models/model-zoo/yolo11-license-plate/license-plate-finetune-v1n.pt",
                        "load_count": 1,
                    },
                    {
                        "name": "yolo11-face",
                        "display_name": "YOLO11 Face Detection",
                        "vram_mb": 200,
                        "status": "unloaded",
                        "category": "detection",
                        "enabled": True,
                        "available": False,
                        "path": "/models/model-zoo/yolo11-face-detection/model.pt",
                        "load_count": 0,
                    },
                ],
                "loading_strategy": "sequential",
                "max_concurrent_models": 1,
            }
        }
    )
