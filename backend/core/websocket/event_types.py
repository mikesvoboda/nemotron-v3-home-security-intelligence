"""WebSocket event type registry and base infrastructure.

This module provides a centralized registry of all WebSocket event types
used throughout the application for real-time event broadcasting.

Event types follow a hierarchical naming convention: {domain}.{action}

Domains:
- alert: Alert notifications and state changes
- camera: Camera status and configuration changes
- job: Background job lifecycle events
- system: System health and status events
- event: Security event lifecycle events (AI-analyzed events)
- detection: Raw AI detection events

Example Usage:
    from backend.core.websocket.event_types import WebSocketEventType, WebSocketEvent
    from datetime import datetime, UTC

    # Create an event
    event = WebSocketEvent(
        type=WebSocketEventType.ALERT_CREATED,
        payload={"alert_id": "123", "severity": "high"},
        timestamp=datetime.now(UTC).isoformat(),
        correlation_id="req-abc123",
    )
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypedDict


class WebSocketEventType(StrEnum):
    """Centralized registry of all WebSocket event types.

    Event types follow the pattern: {domain}.{action}

    This enum serves as the single source of truth for all event types
    that can be emitted via WebSocket connections.
    """

    # ==========================================================================
    # Alert Events - Alert notifications and state changes
    # ==========================================================================
    ALERT_CREATED = "alert.created"
    """New alert triggered from rule evaluation."""

    ALERT_UPDATED = "alert.updated"
    """Alert modified (metadata, channels, properties updated)."""

    ALERT_DELETED = "alert.deleted"
    """Alert permanently deleted from the system."""

    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    """Alert marked as seen by user."""

    ALERT_RESOLVED = "alert.resolved"
    """Alert resolved/closed (long-running issues cleared)."""

    ALERT_DISMISSED = "alert.dismissed"
    """Alert dismissed by user without resolution."""

    # ==========================================================================
    # Camera Events - Camera status and configuration changes
    # ==========================================================================
    CAMERA_ONLINE = "camera.online"
    """Camera came online and is now streaming."""

    CAMERA_OFFLINE = "camera.offline"
    """Camera went offline (no recent activity)."""

    CAMERA_STATUS_CHANGED = "camera.status_changed"
    """Camera status changed (online, offline, error, unknown)."""

    CAMERA_ENABLED = "camera.enabled"
    """Camera enabled for monitoring."""

    CAMERA_DISABLED = "camera.disabled"
    """Camera disabled from monitoring."""

    CAMERA_ERROR = "camera.error"
    """Camera encountered an error condition."""

    CAMERA_CONFIG_UPDATED = "camera.config_updated"
    """Camera configuration was updated."""

    # ==========================================================================
    # Job Events - Background job lifecycle
    # ==========================================================================
    JOB_STARTED = "job.started"
    """Background job started execution."""

    JOB_PROGRESS = "job.progress"
    """Background job progress update (throttled to 10% increments)."""

    JOB_COMPLETED = "job.completed"
    """Background job completed successfully."""

    JOB_FAILED = "job.failed"
    """Background job failed with error."""

    JOB_CANCELLED = "job.cancelled"
    """Background job was cancelled."""

    # ==========================================================================
    # Legacy Job Events (underscore format - NEM-2505)
    # These match the actual WebSocket schema message types sent over the wire
    # ==========================================================================
    LEGACY_JOB_PROGRESS = "job_progress"
    """Job progress event (legacy underscore format)."""

    LEGACY_JOB_COMPLETED = "job_completed"
    """Job completed event (legacy underscore format)."""

    LEGACY_JOB_FAILED = "job_failed"
    """Job failed event (legacy underscore format)."""

    # ==========================================================================
    # System Events - System health and monitoring
    # ==========================================================================
    SYSTEM_HEALTH_CHANGED = "system.health_changed"
    """Overall system health status changed."""

    SYSTEM_ERROR = "system.error"
    """System-level error occurred."""

    SYSTEM_STATUS = "system.status"
    """Periodic system status update."""

    SERVICE_STATUS_CHANGED = "service.status_changed"
    """Individual service (container) status changed."""

    GPU_STATS_UPDATED = "gpu.stats_updated"
    """GPU statistics updated."""

    # ==========================================================================
    # Worker Events - Pipeline worker lifecycle (NEM-2461)
    # ==========================================================================
    WORKER_STARTED = "worker.started"
    """Pipeline worker started and is now processing."""

    WORKER_STOPPED = "worker.stopped"
    """Pipeline worker stopped gracefully."""

    WORKER_HEALTH_CHECK_FAILED = "worker.health_check_failed"
    """Pipeline worker health check failed."""

    WORKER_RESTARTING = "worker.restarting"
    """Pipeline worker is restarting after failure."""

    WORKER_RECOVERED = "worker.recovered"
    """Pipeline worker recovered from error state."""

    WORKER_ERROR = "worker.error"
    """Pipeline worker encountered an error."""

    # ==========================================================================
    # Event Events - Security event lifecycle (AI-analyzed)
    # ==========================================================================
    EVENT_CREATED = "event.created"
    """New security event created after AI analysis."""

    EVENT_UPDATED = "event.updated"
    """Existing security event updated."""

    EVENT_DELETED = "event.deleted"
    """Security event deleted/removed."""

    # ==========================================================================
    # Detection Events - Raw AI detection results
    # ==========================================================================
    DETECTION_NEW = "detection.new"
    """New detection from AI pipeline (single object)."""

    DETECTION_BATCH = "detection.batch"
    """Batch of detections from a single frame/time window."""

    # ==========================================================================
    # Scene Change Events - Camera view monitoring
    # ==========================================================================
    SCENE_CHANGE_DETECTED = "scene_change.detected"
    """Camera scene change detected (potential tampering)."""

    SCENE_CHANGE_ACKNOWLEDGED = "scene_change.acknowledged"
    """Camera scene change acknowledged by user (NEM-3555)."""

    # ==========================================================================
    # Prometheus Alert Events - Infrastructure monitoring (NEM-3122)
    # ==========================================================================
    PROMETHEUS_ALERT = "prometheus.alert"
    """Prometheus/Alertmanager alert received (infrastructure monitoring)."""

    # ==========================================================================
    # Enrichment Events - Detection enrichment pipeline (NEM-3627)
    # ==========================================================================
    ENRICHMENT_STARTED = "enrichment.started"
    """Enrichment pipeline started processing a detection batch."""

    ENRICHMENT_PROGRESS = "enrichment.progress"
    """Enrichment pipeline progress update (step completion)."""

    ENRICHMENT_COMPLETED = "enrichment.completed"
    """Enrichment pipeline completed processing successfully."""

    ENRICHMENT_FAILED = "enrichment.failed"
    """Enrichment pipeline failed with error."""

    # ==========================================================================
    # Queue Metrics Events - Pipeline queue status (NEM-3637)
    # ==========================================================================
    QUEUE_STATUS = "queue.status"
    """Pipeline queue status update (depths, workers, health)."""

    PIPELINE_THROUGHPUT = "pipeline.throughput"
    """Pipeline throughput metrics (detections/events per minute)."""

    # ==========================================================================
    # Connection Events - WebSocket connection lifecycle
    # ==========================================================================
    CONNECTION_ESTABLISHED = "connection.established"
    """WebSocket connection successfully established."""

    CONNECTION_ERROR = "connection.error"
    """WebSocket connection error occurred."""

    # ==========================================================================
    # Control Messages - Protocol-level messages
    # ==========================================================================
    PING = "ping"
    """Heartbeat ping message."""

    PONG = "pong"
    """Heartbeat pong response."""

    ERROR = "error"
    """Error response message."""


class WebSocketEvent(TypedDict, total=False):
    """Standard WebSocket event envelope structure.

    All WebSocket events follow this structure to ensure consistent
    handling across the application.

    Attributes:
        type: Event type from WebSocketEventType enum.
        payload: Event-specific payload data (varies by event type).
        timestamp: ISO 8601 timestamp when the event occurred.
        correlation_id: Optional ID to correlate related events/requests.
        sequence: Optional monotonically increasing sequence number.
        channel: Optional channel identifier for routing.
    """

    type: WebSocketEventType
    payload: dict[str, Any]
    timestamp: str
    correlation_id: str | None
    sequence: int | None
    channel: str | None


def create_event(
    event_type: WebSocketEventType,
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
    channel: str | None = None,
) -> WebSocketEvent:
    """Create a WebSocket event with standard envelope.

    Factory function to create properly structured WebSocket events
    with automatic timestamp generation.

    Args:
        event_type: The type of event from WebSocketEventType.
        payload: Event-specific payload data.
        correlation_id: Optional ID to correlate related events.
        channel: Optional channel identifier for routing.

    Returns:
        WebSocketEvent dict with all required fields populated.

    Example:
        >>> event = create_event(
        ...     WebSocketEventType.ALERT_CREATED,
        ...     {"alert_id": "123", "severity": "high"},
        ...     correlation_id="req-abc123",
        ... )
        >>> event["type"]
        <WebSocketEventType.ALERT_CREATED: 'alert.created'>
    """
    return WebSocketEvent(
        type=event_type,
        payload=payload,
        timestamp=datetime.now(UTC).isoformat(),
        correlation_id=correlation_id,
        channel=channel,
    )


# Event type metadata registry with documentation and validation info
EVENT_TYPE_METADATA: dict[WebSocketEventType, dict[str, Any]] = {
    # Alert events
    WebSocketEventType.ALERT_CREATED: {
        "description": "New alert triggered from rule evaluation",
        "channel": "alerts",
        "requires_payload": True,
        "payload_fields": ["id", "event_id", "severity", "status", "created_at"],
    },
    WebSocketEventType.ALERT_UPDATED: {
        "description": "Alert modified (metadata, channels, properties updated)",
        "channel": "alerts",
        "requires_payload": True,
        "payload_fields": ["id", "updated_at"],
    },
    WebSocketEventType.ALERT_DELETED: {
        "description": "Alert permanently deleted from the system",
        "channel": "alerts",
        "requires_payload": True,
        "payload_fields": ["id"],
    },
    WebSocketEventType.ALERT_ACKNOWLEDGED: {
        "description": "Alert marked as seen by user",
        "channel": "alerts",
        "requires_payload": True,
        "payload_fields": ["id", "acknowledged_at"],
    },
    WebSocketEventType.ALERT_RESOLVED: {
        "description": "Alert resolved/closed",
        "channel": "alerts",
        "requires_payload": True,
        "payload_fields": ["id", "resolved_at"],
    },
    WebSocketEventType.ALERT_DISMISSED: {
        "description": "Alert dismissed by user without resolution",
        "channel": "alerts",
        "requires_payload": True,
        "payload_fields": ["id", "dismissed_at"],
    },
    # Camera events
    WebSocketEventType.CAMERA_ONLINE: {
        "description": "Camera came online and is now streaming",
        "channel": "cameras",
        "requires_payload": True,
        "payload_fields": ["camera_id", "camera_name", "timestamp"],
    },
    WebSocketEventType.CAMERA_OFFLINE: {
        "description": "Camera went offline (no recent activity)",
        "channel": "cameras",
        "requires_payload": True,
        "payload_fields": ["camera_id", "camera_name", "timestamp"],
    },
    WebSocketEventType.CAMERA_STATUS_CHANGED: {
        "description": "Camera status changed",
        "channel": "cameras",
        "requires_payload": True,
        "payload_fields": ["camera_id", "status", "previous_status"],
    },
    WebSocketEventType.CAMERA_ENABLED: {
        "description": "Camera enabled for monitoring",
        "channel": "cameras",
        "requires_payload": True,
        "payload_fields": ["camera_id", "enabled_at"],
    },
    WebSocketEventType.CAMERA_DISABLED: {
        "description": "Camera disabled from monitoring",
        "channel": "cameras",
        "requires_payload": True,
        "payload_fields": ["camera_id", "disabled_at"],
    },
    WebSocketEventType.CAMERA_ERROR: {
        "description": "Camera encountered an error condition",
        "channel": "cameras",
        "requires_payload": True,
        "payload_fields": ["camera_id", "error", "timestamp"],
    },
    WebSocketEventType.CAMERA_CONFIG_UPDATED: {
        "description": "Camera configuration was updated",
        "channel": "cameras",
        "requires_payload": True,
        "payload_fields": ["camera_id", "updated_fields"],
    },
    # Job events
    WebSocketEventType.JOB_STARTED: {
        "description": "Background job started execution",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "job_type", "started_at"],
    },
    WebSocketEventType.JOB_PROGRESS: {
        "description": "Background job progress update",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "progress", "status"],
    },
    WebSocketEventType.JOB_COMPLETED: {
        "description": "Background job completed successfully",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "completed_at"],
    },
    WebSocketEventType.JOB_FAILED: {
        "description": "Background job failed with error",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "error", "failed_at"],
    },
    WebSocketEventType.JOB_CANCELLED: {
        "description": "Background job was cancelled",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "cancelled_at"],
    },
    # Legacy job events (underscore format - NEM-2505)
    WebSocketEventType.LEGACY_JOB_PROGRESS: {
        "description": "Job progress event (legacy underscore format)",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "progress", "status"],
    },
    WebSocketEventType.LEGACY_JOB_COMPLETED: {
        "description": "Job completed event (legacy underscore format)",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "completed_at"],
    },
    WebSocketEventType.LEGACY_JOB_FAILED: {
        "description": "Job failed event (legacy underscore format)",
        "channel": "jobs",
        "requires_payload": True,
        "payload_fields": ["job_id", "error", "failed_at"],
    },
    # System events
    WebSocketEventType.SYSTEM_HEALTH_CHANGED: {
        "description": "Overall system health status changed",
        "channel": "system",
        "requires_payload": True,
        "payload_fields": ["health", "previous_health", "components"],
    },
    WebSocketEventType.SYSTEM_ERROR: {
        "description": "System-level error occurred",
        "channel": "system",
        "requires_payload": True,
        "payload_fields": ["error", "message", "timestamp"],
    },
    WebSocketEventType.SYSTEM_STATUS: {
        "description": "Periodic system status update",
        "channel": "system",
        "requires_payload": True,
        "payload_fields": ["gpu", "cameras", "queue", "health"],
    },
    WebSocketEventType.SERVICE_STATUS_CHANGED: {
        "description": "Individual service status changed",
        "channel": "system",
        "requires_payload": True,
        "payload_fields": ["service", "status", "previous_status"],
    },
    WebSocketEventType.GPU_STATS_UPDATED: {
        "description": "GPU statistics updated",
        "channel": "system",
        "requires_payload": True,
        "payload_fields": ["utilization", "memory_used", "memory_total", "temperature"],
    },
    # Worker events (NEM-2461)
    WebSocketEventType.WORKER_STARTED: {
        "description": "Pipeline worker started and is now processing",
        "channel": "workers",
        "requires_payload": True,
        "payload_fields": ["worker_name", "worker_type", "timestamp"],
    },
    WebSocketEventType.WORKER_STOPPED: {
        "description": "Pipeline worker stopped gracefully",
        "channel": "workers",
        "requires_payload": True,
        "payload_fields": ["worker_name", "worker_type", "timestamp", "reason"],
    },
    WebSocketEventType.WORKER_HEALTH_CHECK_FAILED: {
        "description": "Pipeline worker health check failed",
        "channel": "workers",
        "requires_payload": True,
        "payload_fields": ["worker_name", "worker_type", "error", "failure_count", "timestamp"],
    },
    WebSocketEventType.WORKER_RESTARTING: {
        "description": "Pipeline worker is restarting after failure",
        "channel": "workers",
        "requires_payload": True,
        "payload_fields": ["worker_name", "worker_type", "attempt", "max_attempts", "timestamp"],
    },
    WebSocketEventType.WORKER_RECOVERED: {
        "description": "Pipeline worker recovered from error state",
        "channel": "workers",
        "requires_payload": True,
        "payload_fields": ["worker_name", "worker_type", "previous_state", "timestamp"],
    },
    WebSocketEventType.WORKER_ERROR: {
        "description": "Pipeline worker encountered an error",
        "channel": "workers",
        "requires_payload": True,
        "payload_fields": ["worker_name", "worker_type", "error", "error_type", "timestamp"],
    },
    # Event events
    WebSocketEventType.EVENT_CREATED: {
        "description": "New security event created after AI analysis",
        "channel": "events",
        "requires_payload": True,
        "payload_fields": ["id", "camera_id", "risk_score", "risk_level", "summary"],
    },
    WebSocketEventType.EVENT_UPDATED: {
        "description": "Existing security event updated",
        "channel": "events",
        "requires_payload": True,
        "payload_fields": ["id", "updated_fields"],
    },
    WebSocketEventType.EVENT_DELETED: {
        "description": "Security event deleted/removed",
        "channel": "events",
        "requires_payload": True,
        "payload_fields": ["id", "reason"],
    },
    # Detection events
    WebSocketEventType.DETECTION_NEW: {
        "description": "New detection from AI pipeline",
        "channel": "detections",
        "requires_payload": True,
        "payload_fields": ["detection_id", "label", "confidence", "camera_id"],
    },
    WebSocketEventType.DETECTION_BATCH: {
        "description": "Batch of detections from a single frame",
        "channel": "detections",
        "requires_payload": True,
        "payload_fields": ["batch_id", "detections", "camera_id"],
    },
    # Scene change events
    WebSocketEventType.SCENE_CHANGE_DETECTED: {
        "description": "Camera scene change detected (potential tampering)",
        "channel": "events",
        "requires_payload": True,
        "payload_fields": ["id", "camera_id", "change_type", "similarity_score"],
    },
    WebSocketEventType.SCENE_CHANGE_ACKNOWLEDGED: {
        "description": "Camera scene change acknowledged by user (NEM-3555)",
        "channel": "events",
        "requires_payload": True,
        "payload_fields": ["id", "camera_id", "acknowledged", "acknowledged_at"],
    },
    # Prometheus alert events (NEM-3122)
    WebSocketEventType.PROMETHEUS_ALERT: {
        "description": "Prometheus/Alertmanager alert received",
        "channel": "alerts",
        "requires_payload": True,
        "payload_fields": ["fingerprint", "status", "alertname", "severity", "starts_at"],
    },
    # Enrichment events (NEM-3627)
    WebSocketEventType.ENRICHMENT_STARTED: {
        "description": "Enrichment pipeline started processing a detection batch",
        "channel": "enrichment",
        "requires_payload": True,
        "payload_fields": ["batch_id", "camera_id", "detection_count", "timestamp"],
    },
    WebSocketEventType.ENRICHMENT_PROGRESS: {
        "description": "Enrichment pipeline progress update",
        "channel": "enrichment",
        "requires_payload": True,
        "payload_fields": ["batch_id", "progress", "current_step", "total_steps"],
    },
    WebSocketEventType.ENRICHMENT_COMPLETED: {
        "description": "Enrichment pipeline completed processing",
        "channel": "enrichment",
        "requires_payload": True,
        "payload_fields": ["batch_id", "status", "enriched_count", "duration_ms"],
    },
    WebSocketEventType.ENRICHMENT_FAILED: {
        "description": "Enrichment pipeline failed with error",
        "channel": "enrichment",
        "requires_payload": True,
        "payload_fields": ["batch_id", "error", "error_type", "timestamp"],
    },
    # Queue metrics events (NEM-3637)
    WebSocketEventType.QUEUE_STATUS: {
        "description": "Pipeline queue status update",
        "channel": "system",
        "requires_payload": True,
        "payload_fields": ["queues", "total_queued", "total_processing", "overall_status"],
    },
    WebSocketEventType.PIPELINE_THROUGHPUT: {
        "description": "Pipeline throughput metrics",
        "channel": "system",
        "requires_payload": True,
        "payload_fields": ["detections_per_minute", "events_per_minute", "timestamp"],
    },
    # Connection events
    WebSocketEventType.CONNECTION_ESTABLISHED: {
        "description": "WebSocket connection successfully established",
        "channel": None,
        "requires_payload": False,
        "payload_fields": [],
    },
    WebSocketEventType.CONNECTION_ERROR: {
        "description": "WebSocket connection error occurred",
        "channel": None,
        "requires_payload": True,
        "payload_fields": ["error", "message"],
    },
    # Control messages
    WebSocketEventType.PING: {
        "description": "Heartbeat ping message",
        "channel": None,
        "requires_payload": False,
        "payload_fields": [],
    },
    WebSocketEventType.PONG: {
        "description": "Heartbeat pong response",
        "channel": None,
        "requires_payload": False,
        "payload_fields": [],
    },
    WebSocketEventType.ERROR: {
        "description": "Error response message",
        "channel": None,
        "requires_payload": True,
        "payload_fields": ["error", "message"],
    },
}


def get_event_channel(event_type: WebSocketEventType) -> str | None:
    """Get the default channel for an event type.

    Args:
        event_type: The event type to look up.

    Returns:
        The channel name or None if the event has no default channel.
    """
    metadata = EVENT_TYPE_METADATA.get(event_type, {})
    return metadata.get("channel")


def get_event_description(event_type: WebSocketEventType) -> str:
    """Get the description for an event type.

    Args:
        event_type: The event type to look up.

    Returns:
        Human-readable description of the event type.
    """
    metadata = EVENT_TYPE_METADATA.get(event_type, {})
    description = metadata.get("description")
    if description is not None:
        return str(description)
    return f"Event type: {event_type.value}"


def get_required_payload_fields(event_type: WebSocketEventType) -> list[str]:
    """Get the required payload fields for an event type.

    Args:
        event_type: The event type to look up.

    Returns:
        List of required field names in the payload.
    """
    metadata = EVENT_TYPE_METADATA.get(event_type, {})
    payload_fields = metadata.get("payload_fields")
    if payload_fields is not None:
        return list(payload_fields)
    return []


def validate_event_type(event_type: str) -> WebSocketEventType | None:
    """Validate and convert a string to a WebSocketEventType.

    Args:
        event_type: String representation of event type.

    Returns:
        WebSocketEventType if valid, None if invalid.
    """
    try:
        return WebSocketEventType(event_type)
    except ValueError:
        return None


def get_all_event_types() -> list[WebSocketEventType]:
    """Get all registered event types.

    Returns:
        List of all WebSocketEventType enum values.
    """
    return list(WebSocketEventType)


def get_event_types_by_channel(channel: str) -> list[WebSocketEventType]:
    """Get all event types that belong to a specific channel.

    Args:
        channel: The channel name to filter by.

    Returns:
        List of event types for the given channel.
    """
    return [
        event_type
        for event_type, metadata in EVENT_TYPE_METADATA.items()
        if metadata.get("channel") == channel
    ]


def get_all_channels() -> list[str]:
    """Get all unique channel names from the registry.

    Returns:
        List of unique channel names (excluding None).
    """
    channels: set[str] = set()
    for metadata in EVENT_TYPE_METADATA.values():
        channel = metadata.get("channel")
        if channel is not None:
            channels.add(str(channel))
    return sorted(channels)
