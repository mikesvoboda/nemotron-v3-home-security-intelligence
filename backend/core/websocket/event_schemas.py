"""Pydantic schemas for WebSocket event payload validation.

This module provides Pydantic models for validating event payloads
before they are emitted via WebSocket. Each event type has a corresponding
schema that ensures type safety and data consistency.

Example Usage:
    from backend.core.websocket.event_schemas import AlertCreatedPayload

    # Validate alert data before emitting
    payload = AlertCreatedPayload(
        id="550e8400-e29b-41d4-a716-446655440000",
        event_id=123,
        severity="high",
        status="pending",
        dedup_key="front_door:person:rule1",
        created_at="2026-01-09T12:00:00Z",
        updated_at="2026-01-09T12:00:00Z",
    )
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# Common Enums
# =============================================================================


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    """Alert status values."""

    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class CameraStatus(StrEnum):
    """Camera status values."""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"


class JobStatus(StrEnum):
    """Job status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SystemHealth(StrEnum):
    """System health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceStatus(StrEnum):
    """Service status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    RESTARTING = "restarting"
    RESTART_FAILED = "restart_failed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    """Risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SceneChangeType(StrEnum):
    """Types of scene changes."""

    VIEW_BLOCKED = "view_blocked"
    ANGLE_CHANGED = "angle_changed"
    VIEW_TAMPERED = "view_tampered"
    UNKNOWN = "unknown"


# =============================================================================
# Base Model Configuration
# =============================================================================


class BasePayload(BaseModel):
    """Base configuration for all payload models."""

    model_config = ConfigDict(
        # Allow extra fields for forward compatibility
        extra="ignore",
        # Use enum values in serialization
        use_enum_values=True,
        # Validate on assignment
        validate_assignment=True,
    )


# =============================================================================
# Alert Event Payloads
# =============================================================================


class AlertCreatedPayload(BasePayload):
    """Payload for alert.created events."""

    id: str = Field(..., description="Unique alert identifier (UUID)")
    event_id: int = Field(..., description="Associated event ID")
    rule_id: str | None = Field(None, description="Alert rule UUID that matched")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    status: AlertStatus = Field(..., description="Current alert status")
    dedup_key: str = Field(..., description="Deduplication key for alert grouping")
    created_at: str = Field(..., description="ISO 8601 timestamp when created")
    updated_at: str = Field(..., description="ISO 8601 timestamp when updated")

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, v: str | AlertSeverity) -> AlertSeverity:
        """Convert string to AlertSeverity enum."""
        if isinstance(v, AlertSeverity):
            return v
        if isinstance(v, str):
            return AlertSeverity(v.lower())
        raise ValueError(f"Invalid severity: {v}")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str | AlertStatus) -> AlertStatus:
        """Convert string to AlertStatus enum."""
        if isinstance(v, AlertStatus):
            return v
        if isinstance(v, str):
            return AlertStatus(v.lower())
        raise ValueError(f"Invalid status: {v}")


class AlertUpdatedPayload(BasePayload):
    """Payload for alert.updated events."""

    id: str = Field(..., description="Alert UUID")
    event_id: int | None = Field(None, description="Associated event ID")
    rule_id: str | None = Field(None, description="Alert rule UUID")
    severity: AlertSeverity | None = Field(None, description="Updated severity level")
    status: AlertStatus | None = Field(None, description="Updated status")
    updated_at: str = Field(..., description="ISO 8601 timestamp when updated")
    updated_fields: list[str] | None = Field(None, description="List of updated fields")


class AlertDeletedPayload(BasePayload):
    """Payload for alert.deleted events."""

    id: str = Field(..., description="Deleted alert UUID")
    reason: str | None = Field(None, description="Reason for deletion")


class AlertAcknowledgedPayload(BasePayload):
    """Payload for alert.acknowledged events."""

    id: str = Field(..., description="Alert UUID")
    event_id: int = Field(..., description="Associated event ID")
    acknowledged_at: str = Field(..., description="ISO 8601 timestamp")


class AlertResolvedPayload(BasePayload):
    """Payload for alert.resolved events."""

    id: str = Field(..., description="Alert UUID")
    event_id: int = Field(..., description="Associated event ID")
    resolved_at: str = Field(..., description="ISO 8601 timestamp")
    resolution_notes: str | None = Field(None, description="Optional resolution notes")


class AlertDismissedPayload(BasePayload):
    """Payload for alert.dismissed events."""

    id: str = Field(..., description="Alert UUID")
    event_id: int = Field(..., description="Associated event ID")
    dismissed_at: str = Field(..., description="ISO 8601 timestamp")
    reason: str | None = Field(None, description="Dismissal reason")


# =============================================================================
# Camera Event Payloads
# =============================================================================


class CameraOnlinePayload(BasePayload):
    """Payload for camera.online events."""

    camera_id: str = Field(..., description="Normalized camera ID")
    camera_name: str = Field(..., description="Human-readable camera name")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class CameraOfflinePayload(BasePayload):
    """Payload for camera.offline events."""

    camera_id: str = Field(..., description="Normalized camera ID")
    camera_name: str = Field(..., description="Human-readable camera name")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    reason: str | None = Field(None, description="Reason for going offline")


class CameraStatusChangedPayload(BasePayload):
    """Payload for camera.status_changed events."""

    camera_id: str = Field(..., description="Normalized camera ID")
    camera_name: str = Field(..., description="Human-readable camera name")
    status: CameraStatus = Field(..., description="Current status")
    previous_status: CameraStatus | None = Field(None, description="Previous status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    reason: str | None = Field(None, description="Reason for status change")
    details: dict[str, Any] | None = Field(None, description="Additional details")

    @field_validator("status", "previous_status", mode="before")
    @classmethod
    def validate_camera_status(cls, v: str | CameraStatus | None) -> CameraStatus | None:
        """Convert string to CameraStatus enum."""
        if v is None:
            return None
        if isinstance(v, CameraStatus):
            return v
        if isinstance(v, str):
            return CameraStatus(v.lower())
        raise ValueError(f"Invalid camera status: {v}")


class CameraErrorPayload(BasePayload):
    """Payload for camera.error events."""

    camera_id: str = Field(..., description="Normalized camera ID")
    camera_name: str = Field(..., description="Human-readable camera name")
    error: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class CameraConfigUpdatedPayload(BasePayload):
    """Payload for camera.config_updated events."""

    camera_id: str = Field(..., description="Normalized camera ID")
    updated_fields: list[str] = Field(..., description="List of updated field names")
    updated_at: str = Field(..., description="ISO 8601 timestamp")


# =============================================================================
# Job Event Payloads
# =============================================================================


class JobStartedPayload(BasePayload):
    """Payload for job.started events."""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job (export, cleanup, backup, sync)")
    started_at: str = Field(..., description="ISO 8601 timestamp")
    estimated_duration: int | None = Field(None, description="Estimated duration in seconds")
    metadata: dict[str, Any] | None = Field(None, description="Additional job metadata")


class JobProgressPayload(BasePayload):
    """Payload for job.progress events."""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage (0-100)")
    status: str = Field(..., description="Current job status")
    message: str | None = Field(None, description="Progress message")


class JobCompletedPayload(BasePayload):
    """Payload for job.completed events."""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job")
    completed_at: str = Field(..., description="ISO 8601 timestamp")
    result: dict[str, Any] | None = Field(None, description="Job result data")
    duration_seconds: float | None = Field(None, description="Total duration in seconds")


class JobFailedPayload(BasePayload):
    """Payload for job.failed events."""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job")
    failed_at: str = Field(..., description="ISO 8601 timestamp")
    error: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code")
    retryable: bool = Field(False, description="Whether the job can be retried")


class JobCancelledPayload(BasePayload):
    """Payload for job.cancelled events."""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job")
    cancelled_at: str = Field(..., description="ISO 8601 timestamp")
    reason: str | None = Field(None, description="Cancellation reason")


# =============================================================================
# System Event Payloads
# =============================================================================


class SystemHealthChangedPayload(BasePayload):
    """Payload for system.health_changed events."""

    health: SystemHealth = Field(..., description="Overall system health")
    previous_health: SystemHealth | None = Field(None, description="Previous health state")
    components: dict[str, str] = Field(..., description="Health status per component")
    timestamp: str = Field(..., description="ISO 8601 timestamp")

    @field_validator("health", "previous_health", mode="before")
    @classmethod
    def validate_system_health(cls, v: str | SystemHealth | None) -> SystemHealth | None:
        """Convert string to SystemHealth enum."""
        if v is None:
            return None
        if isinstance(v, SystemHealth):
            return v
        if isinstance(v, str):
            return SystemHealth(v.lower())
        raise ValueError(f"Invalid system health: {v}")


class SystemErrorPayload(BasePayload):
    """Payload for system.error events."""

    error: str = Field(..., description="Error code/type")
    message: str = Field(..., description="Human-readable error message")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    recoverable: bool = Field(True, description="Whether the error is recoverable")


class SystemStatusPayload(BasePayload):
    """Payload for system.status events."""

    gpu: dict[str, Any] = Field(..., description="GPU metrics")
    cameras: dict[str, int] = Field(..., description="Camera counts (active, total)")
    queue: dict[str, int] = Field(..., description="Queue status (pending, processing)")
    health: SystemHealth = Field(..., description="Overall system health")
    ai: dict[str, str] | None = Field(None, description="AI service health status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class ServiceStatusChangedPayload(BasePayload):
    """Payload for service.status_changed events."""

    service: str = Field(..., description="Service name (redis, yolo26, nemotron)")
    status: ServiceStatus = Field(..., description="Current service status")
    previous_status: ServiceStatus | None = Field(None, description="Previous status")
    message: str | None = Field(None, description="Status message")
    timestamp: str = Field(..., description="ISO 8601 timestamp")

    @field_validator("status", "previous_status", mode="before")
    @classmethod
    def validate_service_status(cls, v: str | ServiceStatus | None) -> ServiceStatus | None:
        """Convert string to ServiceStatus enum."""
        if v is None:
            return None
        if isinstance(v, ServiceStatus):
            return v
        if isinstance(v, str):
            return ServiceStatus(v.lower())
        raise ValueError(f"Invalid service status: {v}")


class GPUStatsUpdatedPayload(BasePayload):
    """Payload for gpu.stats_updated events."""

    utilization: float | None = Field(None, ge=0, le=100, description="GPU utilization %")
    memory_used: int | None = Field(None, ge=0, description="GPU memory used (bytes)")
    memory_total: int | None = Field(None, ge=0, description="Total GPU memory (bytes)")
    temperature: float | None = Field(None, description="GPU temperature (Celsius)")
    inference_fps: float | None = Field(None, ge=0, description="Current inference FPS")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# =============================================================================
# Security Event Payloads
# =============================================================================


class EventCreatedPayload(BasePayload):
    """Payload for event.created events."""

    id: int = Field(..., description="Unique event identifier")
    event_id: int = Field(..., description="Legacy alias for id")
    batch_id: str = Field(..., description="Detection batch identifier")
    camera_id: str = Field(..., description="Normalized camera ID")
    risk_score: int = Field(..., ge=0, le=100, description="Risk assessment score")
    risk_level: RiskLevel = Field(..., description="Risk classification")
    summary: str = Field(..., description="Human-readable event summary")
    reasoning: str = Field(..., description="LLM reasoning for risk assessment")
    started_at: str | None = Field(None, description="ISO 8601 event start timestamp")

    @field_validator("risk_level", mode="before")
    @classmethod
    def validate_risk_level(cls, v: str | RiskLevel) -> RiskLevel:
        """Convert string to RiskLevel enum."""
        if isinstance(v, RiskLevel):
            return v
        if isinstance(v, str):
            return RiskLevel(v.lower())
        raise ValueError(f"Invalid risk level: {v}")


class EventUpdatedPayload(BasePayload):
    """Payload for event.updated events."""

    id: int = Field(..., description="Event database ID")
    updated_fields: list[str] = Field(..., description="List of updated field names")
    risk_score: int | None = Field(None, ge=0, le=100, description="Updated risk score")
    risk_level: RiskLevel | None = Field(None, description="Updated risk level")
    updated_at: str = Field(..., description="ISO 8601 timestamp")


class EventDeletedPayload(BasePayload):
    """Payload for event.deleted events."""

    id: int = Field(..., description="Deleted event ID")
    reason: str | None = Field(None, description="Deletion reason")


# =============================================================================
# Detection Event Payloads
# =============================================================================


class BoundingBox(BasePayload):
    """Bounding box coordinates for detection."""

    x: float = Field(..., description="X coordinate (left)")
    y: float = Field(..., description="Y coordinate (top)")
    width: float = Field(..., description="Box width")
    height: float = Field(..., description="Box height")


class DetectionNewPayload(BasePayload):
    """Payload for detection.new events."""

    detection_id: str = Field(..., description="Unique detection identifier")
    event_id: str | None = Field(None, description="Associated event identifier")
    label: str = Field(..., description="Detection class label (person, vehicle, etc.)")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence score")
    bbox: BoundingBox | None = Field(None, description="Bounding box coordinates")
    camera_id: str = Field(..., description="Camera identifier")
    timestamp: str = Field(..., description="ISO 8601 detection timestamp")


class DetectionBatchPayload(BasePayload):
    """Payload for detection.batch events."""

    batch_id: str = Field(..., description="Unique batch identifier")
    detections: list[DetectionNewPayload] = Field(..., description="Array of detections")
    frame_timestamp: str = Field(..., description="Frame capture timestamp")
    camera_id: str = Field(..., description="Camera identifier")
    frame_count: int | None = Field(None, description="Number of frames in batch")


# =============================================================================
# Scene Change Event Payloads
# =============================================================================


class SceneChangeDetectedPayload(BasePayload):
    """Payload for scene_change.detected events."""

    id: int = Field(..., description="Scene change record ID")
    camera_id: str = Field(..., description="Camera identifier")
    detected_at: str = Field(..., description="ISO 8601 detection timestamp")
    change_type: SceneChangeType = Field(..., description="Type of scene change")
    similarity_score: float = Field(
        ..., ge=0, le=1, description="SSIM similarity score (lower = more different)"
    )

    @field_validator("change_type", mode="before")
    @classmethod
    def validate_change_type(cls, v: str | SceneChangeType) -> SceneChangeType:
        """Convert string to SceneChangeType enum."""
        if isinstance(v, SceneChangeType):
            return v
        if isinstance(v, str):
            return SceneChangeType(v.lower())
        raise ValueError(f"Invalid scene change type: {v}")


# =============================================================================
# Prometheus Alert Event Payloads (NEM-3122)
# =============================================================================


class PrometheusAlertStatusEnum(StrEnum):
    """Prometheus alert status values."""

    FIRING = "firing"
    RESOLVED = "resolved"


class PrometheusAlertPayload(BasePayload):
    """Payload for prometheus.alert events.

    Represents a Prometheus/Alertmanager alert received via webhook.
    These are infrastructure monitoring alerts (GPU, memory, pipeline health, etc.)
    separate from AI-generated security alerts.
    """

    fingerprint: str = Field(..., description="Unique alert fingerprint for deduplication")
    status: PrometheusAlertStatusEnum = Field(..., description="Alert status (firing or resolved)")
    alertname: str = Field(..., description="Name of the alert")
    severity: str = Field("info", description="Alert severity level")
    labels: dict[str, str] = Field(default_factory=dict, description="Alert labels")
    annotations: dict[str, str] = Field(default_factory=dict, description="Alert annotations")
    starts_at: str = Field(..., description="ISO 8601 timestamp when alert started")
    ends_at: str | None = Field(None, description="ISO 8601 timestamp when alert resolved")
    received_at: str = Field(..., description="ISO 8601 timestamp when backend received alert")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str | PrometheusAlertStatusEnum) -> PrometheusAlertStatusEnum:
        """Convert string to PrometheusAlertStatusEnum enum."""
        if isinstance(v, PrometheusAlertStatusEnum):
            return v
        if isinstance(v, str):
            return PrometheusAlertStatusEnum(v.lower())
        raise ValueError(f"Invalid prometheus alert status: {v}")


# =============================================================================
# Worker Event Payloads (NEM-2461)
# =============================================================================


class WorkerType(StrEnum):
    """Pipeline worker types."""

    DETECTION = "detection"
    ANALYSIS = "analysis"
    TIMEOUT = "timeout"
    METRICS = "metrics"


class WorkerStateEnum(StrEnum):
    """Worker state values for WebSocket payloads."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class WorkerStartedPayload(BasePayload):
    """Payload for worker.started events."""

    worker_name: str = Field(..., description="Worker instance name")
    worker_type: WorkerType = Field(..., description="Type of worker")
    timestamp: str = Field(..., description="ISO 8601 timestamp when started")
    metadata: dict[str, Any] | None = Field(None, description="Additional worker metadata")

    @field_validator("worker_type", mode="before")
    @classmethod
    def validate_worker_type(cls, v: str | WorkerType) -> WorkerType:
        """Convert string to WorkerType enum."""
        if isinstance(v, WorkerType):
            return v
        if isinstance(v, str):
            return WorkerType(v.lower())
        raise ValueError(f"Invalid worker type: {v}")


class WorkerStoppedPayload(BasePayload):
    """Payload for worker.stopped events."""

    worker_name: str = Field(..., description="Worker instance name")
    worker_type: WorkerType = Field(..., description="Type of worker")
    timestamp: str = Field(..., description="ISO 8601 timestamp when stopped")
    reason: str | None = Field(None, description="Reason for stopping")
    items_processed: int | None = Field(None, description="Total items processed before stop")

    @field_validator("worker_type", mode="before")
    @classmethod
    def validate_worker_type(cls, v: str | WorkerType) -> WorkerType:
        """Convert string to WorkerType enum."""
        if isinstance(v, WorkerType):
            return v
        if isinstance(v, str):
            return WorkerType(v.lower())
        raise ValueError(f"Invalid worker type: {v}")


class WorkerHealthCheckFailedPayload(BasePayload):
    """Payload for worker.health_check_failed events."""

    worker_name: str = Field(..., description="Worker instance name")
    worker_type: WorkerType = Field(..., description="Type of worker")
    error: str = Field(..., description="Error message or description")
    error_type: str | None = Field(None, description="Categorized error type")
    failure_count: int = Field(..., ge=0, description="Number of consecutive failures")
    timestamp: str = Field(..., description="ISO 8601 timestamp")

    @field_validator("worker_type", mode="before")
    @classmethod
    def validate_worker_type(cls, v: str | WorkerType) -> WorkerType:
        """Convert string to WorkerType enum."""
        if isinstance(v, WorkerType):
            return v
        if isinstance(v, str):
            return WorkerType(v.lower())
        raise ValueError(f"Invalid worker type: {v}")


class WorkerRestartingPayload(BasePayload):
    """Payload for worker.restarting events."""

    worker_name: str = Field(..., description="Worker instance name")
    worker_type: WorkerType = Field(..., description="Type of worker")
    attempt: int = Field(..., ge=1, description="Current restart attempt number")
    max_attempts: int | None = Field(None, description="Maximum restart attempts allowed")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    reason: str | None = Field(None, description="Reason for restart")

    @field_validator("worker_type", mode="before")
    @classmethod
    def validate_worker_type(cls, v: str | WorkerType) -> WorkerType:
        """Convert string to WorkerType enum."""
        if isinstance(v, WorkerType):
            return v
        if isinstance(v, str):
            return WorkerType(v.lower())
        raise ValueError(f"Invalid worker type: {v}")


class WorkerRecoveredPayload(BasePayload):
    """Payload for worker.recovered events."""

    worker_name: str = Field(..., description="Worker instance name")
    worker_type: WorkerType = Field(..., description="Type of worker")
    previous_state: WorkerStateEnum = Field(..., description="State before recovery")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    recovery_duration_ms: float | None = Field(None, description="Time to recover in milliseconds")

    @field_validator("worker_type", mode="before")
    @classmethod
    def validate_worker_type(cls, v: str | WorkerType) -> WorkerType:
        """Convert string to WorkerType enum."""
        if isinstance(v, WorkerType):
            return v
        if isinstance(v, str):
            return WorkerType(v.lower())
        raise ValueError(f"Invalid worker type: {v}")

    @field_validator("previous_state", mode="before")
    @classmethod
    def validate_previous_state(cls, v: str | WorkerStateEnum) -> WorkerStateEnum:
        """Convert string to WorkerStateEnum."""
        if isinstance(v, WorkerStateEnum):
            return v
        if isinstance(v, str):
            return WorkerStateEnum(v.lower())
        raise ValueError(f"Invalid worker state: {v}")


class WorkerErrorPayload(BasePayload):
    """Payload for worker.error events."""

    worker_name: str = Field(..., description="Worker instance name")
    worker_type: WorkerType = Field(..., description="Type of worker")
    error: str = Field(..., description="Error message")
    error_type: str | None = Field(None, description="Categorized error type")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    recoverable: bool = Field(True, description="Whether the error is recoverable")

    @field_validator("worker_type", mode="before")
    @classmethod
    def validate_worker_type(cls, v: str | WorkerType) -> WorkerType:
        """Convert string to WorkerType enum."""
        if isinstance(v, WorkerType):
            return v
        if isinstance(v, str):
            return WorkerType(v.lower())
        raise ValueError(f"Invalid worker type: {v}")


# =============================================================================
# Connection Event Payloads
# =============================================================================


class ConnectionEstablishedPayload(BasePayload):
    """Payload for connection.established events."""

    connection_id: str = Field(..., description="Unique connection identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class ConnectionErrorPayload(BasePayload):
    """Payload for connection.error events."""

    error: str = Field(..., description="Error code/type")
    message: str = Field(..., description="Human-readable error message")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# =============================================================================
# Control Message Payloads
# =============================================================================


class ErrorPayload(BasePayload):
    """Payload for error messages."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


# =============================================================================
# Enrichment Event Payloads (NEM-3627)
# =============================================================================


class EnrichmentStatusEnum(StrEnum):
    """Enrichment status values."""

    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class EnrichmentStartedPayload(BasePayload):
    """Payload for enrichment.started events."""

    batch_id: str = Field(..., description="Unique batch identifier")
    camera_id: str = Field(..., description="Camera identifier")
    detection_count: int = Field(..., ge=0, description="Number of detections to enrich")
    timestamp: str = Field(..., description="ISO 8601 timestamp when started")
    enabled_models: list[str] | None = Field(None, description="List of enabled enrichment models")


class EnrichmentProgressPayload(BasePayload):
    """Payload for enrichment.progress events."""

    batch_id: str = Field(..., description="Unique batch identifier")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage (0-100)")
    current_step: str = Field(..., description="Current enrichment step name")
    total_steps: int | None = Field(None, ge=1, description="Total number of enrichment steps")
    completed_steps: list[str] | None = Field(None, description="List of completed step names")
    timestamp: str | None = Field(None, description="ISO 8601 timestamp")


class EnrichmentCompletedPayload(BasePayload):
    """Payload for enrichment.completed events."""

    batch_id: str = Field(..., description="Unique batch identifier")
    status: EnrichmentStatusEnum = Field(
        ..., description="Enrichment status (full, partial, failed)"
    )
    enriched_count: int = Field(..., ge=0, description="Number of successfully enriched detections")
    duration_ms: float | None = Field(
        None, ge=0, description="Total processing duration in milliseconds"
    )
    timestamp: str | None = Field(None, description="ISO 8601 timestamp when completed")
    summary: dict[str, Any] | None = Field(None, description="Enrichment summary details")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str | EnrichmentStatusEnum) -> EnrichmentStatusEnum:
        """Convert string to EnrichmentStatusEnum enum."""
        if isinstance(v, EnrichmentStatusEnum):
            return v
        if isinstance(v, str):
            return EnrichmentStatusEnum(v.lower())
        raise ValueError(f"Invalid enrichment status: {v}")


class EnrichmentFailedPayload(BasePayload):
    """Payload for enrichment.failed events."""

    batch_id: str = Field(..., description="Unique batch identifier")
    error: str = Field(..., description="Error message")
    error_type: str | None = Field(None, description="Categorized error type")
    timestamp: str | None = Field(None, description="ISO 8601 timestamp")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    recoverable: bool = Field(True, description="Whether the error is recoverable")


# =============================================================================
# Queue Metrics Event Payloads (NEM-3637)
# =============================================================================


class QueueInfo(BasePayload):
    """Information about a single queue."""

    name: str = Field(..., description="Queue name (detection, analysis, etc.)")
    depth: int = Field(..., ge=0, description="Number of items in queue")
    workers: int = Field(..., ge=0, description="Number of active workers")
    status: str | None = Field(None, description="Queue health status")


class QueueStatusPayload(BasePayload):
    """Payload for queue.status events."""

    queues: list[QueueInfo] = Field(..., description="List of queue statuses")
    total_queued: int = Field(..., ge=0, description="Total items across all queues")
    total_processing: int = Field(..., ge=0, description="Total items being processed")
    total_workers: int | None = Field(None, ge=0, description="Total active workers")
    overall_status: str = Field(..., description="Overall system status (healthy/warning/critical)")
    timestamp: str | None = Field(None, description="ISO 8601 timestamp")


class PipelineThroughputPayload(BasePayload):
    """Payload for pipeline.throughput events."""

    detections_per_minute: float = Field(..., ge=0, description="Detections processed per minute")
    events_per_minute: float = Field(..., ge=0, description="Events created per minute")
    enrichments_per_minute: float | None = Field(None, ge=0, description="Enrichments per minute")
    timestamp: str | None = Field(None, description="ISO 8601 timestamp")
    window_seconds: int | None = Field(None, description="Measurement window in seconds")


# =============================================================================
# Payload Type Mapping
# =============================================================================

# Import event types for mapping
from backend.core.websocket.event_types import WebSocketEventType  # noqa: E402

# Map event types to their payload schemas
EVENT_PAYLOAD_SCHEMAS: dict[WebSocketEventType, type[BasePayload]] = {
    # Alert events
    WebSocketEventType.ALERT_CREATED: AlertCreatedPayload,
    WebSocketEventType.ALERT_UPDATED: AlertUpdatedPayload,
    WebSocketEventType.ALERT_DELETED: AlertDeletedPayload,
    WebSocketEventType.ALERT_ACKNOWLEDGED: AlertAcknowledgedPayload,
    WebSocketEventType.ALERT_RESOLVED: AlertResolvedPayload,
    WebSocketEventType.ALERT_DISMISSED: AlertDismissedPayload,
    # Camera events
    WebSocketEventType.CAMERA_ONLINE: CameraOnlinePayload,
    WebSocketEventType.CAMERA_OFFLINE: CameraOfflinePayload,
    WebSocketEventType.CAMERA_STATUS_CHANGED: CameraStatusChangedPayload,
    WebSocketEventType.CAMERA_ERROR: CameraErrorPayload,
    WebSocketEventType.CAMERA_CONFIG_UPDATED: CameraConfigUpdatedPayload,
    # Job events
    WebSocketEventType.JOB_STARTED: JobStartedPayload,
    WebSocketEventType.JOB_PROGRESS: JobProgressPayload,
    WebSocketEventType.JOB_COMPLETED: JobCompletedPayload,
    WebSocketEventType.JOB_FAILED: JobFailedPayload,
    WebSocketEventType.JOB_CANCELLED: JobCancelledPayload,
    # System events
    WebSocketEventType.SYSTEM_HEALTH_CHANGED: SystemHealthChangedPayload,
    WebSocketEventType.SYSTEM_ERROR: SystemErrorPayload,
    WebSocketEventType.SYSTEM_STATUS: SystemStatusPayload,
    WebSocketEventType.SERVICE_STATUS_CHANGED: ServiceStatusChangedPayload,
    WebSocketEventType.GPU_STATS_UPDATED: GPUStatsUpdatedPayload,
    # Worker events (NEM-2461)
    WebSocketEventType.WORKER_STARTED: WorkerStartedPayload,
    WebSocketEventType.WORKER_STOPPED: WorkerStoppedPayload,
    WebSocketEventType.WORKER_HEALTH_CHECK_FAILED: WorkerHealthCheckFailedPayload,
    WebSocketEventType.WORKER_RESTARTING: WorkerRestartingPayload,
    WebSocketEventType.WORKER_RECOVERED: WorkerRecoveredPayload,
    WebSocketEventType.WORKER_ERROR: WorkerErrorPayload,
    # Security events
    WebSocketEventType.EVENT_CREATED: EventCreatedPayload,
    WebSocketEventType.EVENT_UPDATED: EventUpdatedPayload,
    WebSocketEventType.EVENT_DELETED: EventDeletedPayload,
    # Detection events
    WebSocketEventType.DETECTION_NEW: DetectionNewPayload,
    WebSocketEventType.DETECTION_BATCH: DetectionBatchPayload,
    # Scene change events
    WebSocketEventType.SCENE_CHANGE_DETECTED: SceneChangeDetectedPayload,
    # Prometheus alert events (NEM-3122)
    WebSocketEventType.PROMETHEUS_ALERT: PrometheusAlertPayload,
    # Connection events
    WebSocketEventType.CONNECTION_ESTABLISHED: ConnectionEstablishedPayload,
    WebSocketEventType.CONNECTION_ERROR: ConnectionErrorPayload,
    # Control messages
    WebSocketEventType.ERROR: ErrorPayload,
    # Enrichment events (NEM-3627)
    WebSocketEventType.ENRICHMENT_STARTED: EnrichmentStartedPayload,
    WebSocketEventType.ENRICHMENT_PROGRESS: EnrichmentProgressPayload,
    WebSocketEventType.ENRICHMENT_COMPLETED: EnrichmentCompletedPayload,
    WebSocketEventType.ENRICHMENT_FAILED: EnrichmentFailedPayload,
    # Queue metrics events (NEM-3637)
    WebSocketEventType.QUEUE_STATUS: QueueStatusPayload,
    WebSocketEventType.PIPELINE_THROUGHPUT: PipelineThroughputPayload,
}


def get_payload_schema(event_type: WebSocketEventType) -> type[BasePayload] | None:
    """Get the Pydantic schema for an event type's payload.

    Args:
        event_type: The event type to look up.

    Returns:
        The Pydantic model class for the payload, or None if no schema defined.
    """
    return EVENT_PAYLOAD_SCHEMAS.get(event_type)


def validate_payload(event_type: WebSocketEventType, payload: dict[str, Any]) -> BasePayload:
    """Validate a payload against the schema for an event type.

    Args:
        event_type: The event type for the payload.
        payload: The payload data to validate.

    Returns:
        Validated Pydantic model instance.

    Raises:
        ValueError: If no schema exists for the event type.
        ValidationError: If the payload doesn't match the schema.
    """
    schema = get_payload_schema(event_type)
    if schema is None:
        raise ValueError(f"No payload schema defined for event type: {event_type}")
    return schema.model_validate(payload)
