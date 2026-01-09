"""Pydantic schemas for WebSocket message validation.

This module defines schemas for validating incoming WebSocket message payloads.
Clients can send messages to WebSocket endpoints, and these schemas ensure
proper structure and type validation before processing.

Supported message types:
- ping: Keep-alive heartbeat (responds with pong)
- subscribe: Subscribe to specific event channels (future)
- unsubscribe: Unsubscribe from event channels (future)
"""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RiskLevel(StrEnum):
    """Valid risk levels for security events.

    This enum mirrors backend.models.enums.Severity but is specifically
    for WebSocket message validation. The values are:
    - low: Routine activity, no concern
    - medium: Notable activity, worth reviewing
    - high: Concerning activity, review soon
    - critical: Immediate attention required
    """

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class WebSocketMessageType(StrEnum):
    """Valid WebSocket message types."""

    PING = auto()
    PONG = auto()
    SUBSCRIBE = auto()
    UNSUBSCRIBE = auto()


class WebSocketPingMessage(BaseModel):
    """Ping message for keep-alive heartbeat.

    Clients can send ping messages to verify the connection is alive.
    Server responds with {"type": "pong"}.
    """

    type: Literal["ping"] = Field(
        ...,
        description="Message type, must be 'ping'",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "ping",
            }
        }
    )


class WebSocketSubscribeMessage(BaseModel):
    """Subscribe message to register interest in specific channels.

    Future enhancement: allow clients to filter which events they receive.
    """

    type: Literal["subscribe"] = Field(
        ...,
        description="Message type, must be 'subscribe'",
    )
    channels: list[str] = Field(
        ...,
        description="List of channel names to subscribe to",
        min_length=1,
        max_length=10,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "subscribe",
                "channels": ["events", "detections"],
            }
        }
    )


class WebSocketUnsubscribeMessage(BaseModel):
    """Unsubscribe message to stop receiving events from specific channels."""

    type: Literal["unsubscribe"] = Field(
        ...,
        description="Message type, must be 'unsubscribe'",
    )
    channels: list[str] = Field(
        ...,
        description="List of channel names to unsubscribe from",
        min_length=1,
        max_length=10,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "unsubscribe",
                "channels": ["events"],
            }
        }
    )


class WebSocketMessage(BaseModel):
    """Generic WebSocket message for initial type detection.

    This schema is used to validate the basic structure of incoming messages
    and determine the message type before dispatching to type-specific handlers.
    """

    type: str = Field(
        ...,
        description="Message type identifier",
        min_length=1,
        max_length=50,
    )
    data: dict[str, Any] | None = Field(
        None,
        description="Optional message payload data",
    )

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields for forward compatibility
        json_schema_extra={
            "example": {
                "type": "ping",
            }
        },
    )

    @model_validator(mode="after")
    def validate_type(self) -> WebSocketMessage:
        """Validate that the message type is a known type."""
        # Note: We allow unknown types for forward compatibility
        # but they will be logged and ignored
        return self


class WebSocketErrorResponse(BaseModel):
    """Error response sent to client for invalid messages."""

    type: Literal["error"] = Field(
        default="error",
        description="Message type, always 'error'",
    )
    error: str = Field(
        ...,
        description="Error code identifying the type of error",
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
    )
    details: dict[str, Any] | None = Field(
        None,
        description="Additional error context",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "error",
                "error": "invalid_message",
                "message": "Message must be valid JSON",
                "details": None,
            }
        }
    )


class WebSocketPongResponse(BaseModel):
    """Pong response sent in reply to ping messages."""

    type: Literal["pong"] = Field(
        default="pong",
        description="Message type, always 'pong'",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "pong",
            }
        }
    )


# Error codes for WebSocket validation errors
class WebSocketErrorCode:
    """Standard error codes for WebSocket validation errors."""

    INVALID_JSON = "invalid_json"
    INVALID_MESSAGE_FORMAT = "invalid_message_format"
    UNKNOWN_MESSAGE_TYPE = "unknown_message_type"
    VALIDATION_ERROR = "validation_error"


# Outgoing message schemas (server -> client)


class WebSocketEventData(BaseModel):
    """Data payload for event messages broadcast to /ws/events clients.

    This schema defines the contract for event data sent from the backend
    to WebSocket clients. Any changes to this schema must be reflected in:
    - backend/api/routes/websocket.py docstring
    - backend/services/nemotron_analyzer.py _broadcast_event()
    - frontend WebSocket event handlers

    Fields:
        id: Unique event identifier
        event_id: Legacy alias for id (for backward compatibility)
        batch_id: Detection batch identifier
        camera_id: Normalized camera ID (e.g., "front_door")
        risk_score: Risk assessment score (0-100)
        risk_level: Risk classification (validated against RiskLevel enum)
        summary: Human-readable description of the event
        reasoning: LLM reasoning for the risk assessment
        started_at: ISO 8601 timestamp when the event started (nullable)
    """

    id: int = Field(..., description="Unique event identifier")
    event_id: int = Field(..., description="Legacy alias for id (backward compatibility)")
    batch_id: str = Field(..., description="Detection batch identifier")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    risk_score: int = Field(..., ge=0, le=100, description="Risk assessment score (0-100)")
    risk_level: RiskLevel = Field(
        ..., description='Risk classification ("low", "medium", "high", "critical")'
    )
    summary: str = Field(..., description="Human-readable description of the event")
    reasoning: str = Field(..., description="LLM reasoning for the risk assessment")
    started_at: str | None = Field(None, description="ISO 8601 timestamp when the event started")

    @field_validator("risk_level", mode="before")
    @classmethod
    def validate_risk_level(cls, v: str | RiskLevel) -> RiskLevel:
        """Validate and convert risk_level to RiskLevel enum.

        Accepts string values for backward compatibility with existing
        WebSocket clients that send lowercase strings.
        """
        if isinstance(v, RiskLevel):
            return v
        if isinstance(v, str):
            try:
                return RiskLevel(v.lower())
            except ValueError:
                valid_values = [level.value for level in RiskLevel]
                raise ValueError(
                    f"Invalid risk_level '{v}'. Must be one of: {valid_values}"
                ) from None
        raise ValueError(f"risk_level must be a string or RiskLevel enum, got {type(v)}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_abc123",
                "camera_id": "cam-uuid",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected at front door",
                "reasoning": "Person approaching entrance during evening hours, behavior appears normal",
                "started_at": "2025-12-23T12:00:00",
            }
        }
    )


class WebSocketEventMessage(BaseModel):
    """Complete event message envelope sent to /ws/events clients.

    This is the canonical format for event messages broadcast via WebSocket.
    The message wraps event data in a standard envelope with a type field.

    Format:
        {
            "type": "event",
            "data": {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_abc123",
                "camera_id": "cam-uuid",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected at front door",
                "reasoning": "Person approaching entrance during evening hours, behavior appears normal",
                "started_at": "2025-12-23T12:00:00"
            }
        }
    """

    type: Literal["event"] = Field(
        default="event", description="Message type, always 'event' for event messages"
    )
    data: WebSocketEventData = Field(..., description="Event data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "event",
                "data": {
                    "id": 1,
                    "event_id": 1,
                    "batch_id": "batch_abc123",
                    "camera_id": "cam-uuid",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Person detected at front door",
                    "reasoning": "Person approaching entrance during evening hours, behavior appears normal",
                    "started_at": "2025-12-23T12:00:00",
                },
            }
        }
    )


class WebSocketServiceStatus(StrEnum):
    """Valid service status values for WebSocket health monitoring messages."""

    HEALTHY = auto()
    UNHEALTHY = auto()
    RESTARTING = auto()
    RESTART_FAILED = auto()
    FAILED = auto()


class WebSocketServiceStatusData(BaseModel):
    """Data payload for service status messages.

    Broadcast by the health monitor when a service's status changes.
    """

    service: str = Field(..., description="Name of the service (redis, rtdetr, nemotron)")
    status: WebSocketServiceStatus = Field(..., description="Current service status")
    message: str | None = Field(None, description="Optional descriptive message")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str | WebSocketServiceStatus) -> WebSocketServiceStatus:
        """Validate and convert status to WebSocketServiceStatus enum."""
        if isinstance(v, WebSocketServiceStatus):
            return v
        if isinstance(v, str):
            try:
                return WebSocketServiceStatus(v.lower())
            except ValueError:
                valid_values = [s.value for s in WebSocketServiceStatus]
                raise ValueError(f"Invalid status '{v}'. Must be one of: {valid_values}") from None
        raise ValueError(f"status must be a string or WebSocketServiceStatus enum, got {type(v)}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "redis",
                "status": "healthy",
                "message": "Service responding normally",
            }
        }
    )


class WebSocketServiceStatusMessage(BaseModel):
    """Complete service status message envelope.

    This is the canonical format for service status messages broadcast via WebSocket.
    Consistent with other message types, data is wrapped in a standard envelope.

    Format:
        {
            "type": "service_status",
            "data": {
                "service": "redis",
                "status": "healthy",
                "message": "Service responding normally"
            },
            "timestamp": "2025-12-23T12:00:00.000Z"
        }
    """

    type: Literal["service_status"] = Field(
        default="service_status",
        description="Message type, always 'service_status' for service status messages",
    )
    data: WebSocketServiceStatusData = Field(..., description="Service status data payload")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the status change")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "service_status",
                "data": {
                    "service": "redis",
                    "status": "healthy",
                    "message": "Service responding normally",
                },
                "timestamp": "2025-12-23T12:00:00.000Z",
            }
        }
    )


class WebSocketCameraStatus(StrEnum):
    """Valid camera status values for WebSocket messages."""

    ONLINE = auto()
    OFFLINE = auto()
    ERROR = auto()
    UNKNOWN = auto()


class WebSocketCameraStatusData(BaseModel):
    """Data payload for camera status messages.

    Broadcast when a camera's status changes (online, offline, error, unknown).
    """

    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    status: WebSocketCameraStatus = Field(..., description="Current camera status")
    previous_status: WebSocketCameraStatus | None = Field(
        None, description="Previous camera status before this change"
    )
    reason: str | None = Field(None, description="Optional reason for the status change")

    @field_validator("status", "previous_status", mode="before")
    @classmethod
    def validate_status(cls, v: str | WebSocketCameraStatus | None) -> WebSocketCameraStatus | None:
        """Validate and convert status to WebSocketCameraStatus enum."""
        if v is None:
            return None
        if isinstance(v, WebSocketCameraStatus):
            return v
        if isinstance(v, str):
            try:
                return WebSocketCameraStatus(v.lower())
            except ValueError:
                valid_values = [s.value for s in WebSocketCameraStatus]
                raise ValueError(f"Invalid status '{v}'. Must be one of: {valid_values}") from None
        raise ValueError(f"status must be a string or WebSocketCameraStatus enum, got {type(v)}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "status": "offline",
                "previous_status": "online",
                "reason": "No activity detected for 5 minutes",
            }
        }
    )


class WebSocketCameraStatusMessage(BaseModel):
    """Complete camera status message envelope.

    This is the canonical format for camera status messages broadcast via WebSocket.
    Consistent with other message types, data is wrapped in a standard envelope.

    Format:
        {
            "type": "camera_status",
            "data": {
                "camera_id": "front_door",
                "status": "offline",
                "previous_status": "online",
                "reason": "No activity detected"
            }
        }
    """

    type: Literal["camera_status"] = Field(
        default="camera_status",
        description="Message type, always 'camera_status' for camera status messages",
    )
    data: WebSocketCameraStatusData = Field(..., description="Camera status data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "camera_status",
                "data": {
                    "camera_id": "front_door",
                    "status": "offline",
                    "previous_status": "online",
                    "reason": "No activity detected for 5 minutes",
                },
            }
        }
    )


class WebSocketSceneChangeData(BaseModel):
    """Data payload for scene change messages broadcast to /ws/events clients.

    This schema defines the contract for scene change data sent from the backend
    to WebSocket clients when a camera view change is detected.

    Fields:
        id: Unique scene change identifier
        camera_id: Normalized camera ID (e.g., "front_door")
        detected_at: ISO 8601 timestamp when the change was detected
        change_type: Type of change (view_blocked, angle_changed, view_tampered, unknown)
        similarity_score: SSIM score (0-1, lower means more different from baseline)
    """

    id: int = Field(..., description="Unique scene change identifier")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    detected_at: str = Field(..., description="ISO 8601 timestamp when the change was detected")
    change_type: str = Field(
        ..., description="Type of change (view_blocked, angle_changed, view_tampered, unknown)"
    )
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="SSIM score (0-1, lower means more different)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "detected_at": "2026-01-03T10:30:00Z",
                "change_type": "view_blocked",
                "similarity_score": 0.23,
            }
        }
    )


class WebSocketSceneChangeMessage(BaseModel):
    """Complete scene change message envelope sent to /ws/events clients.

    This is the canonical format for scene change messages broadcast via WebSocket.
    The message wraps scene change data in a standard envelope with a type field.

    Format:
        {
            "type": "scene_change",
            "data": {
                "id": 1,
                "camera_id": "front_door",
                "detected_at": "2026-01-03T10:30:00Z",
                "change_type": "view_blocked",
                "similarity_score": 0.23
            }
        }
    """

    type: Literal["scene_change"] = Field(
        default="scene_change",
        description="Message type, always 'scene_change' for scene change messages",
    )
    data: WebSocketSceneChangeData = Field(..., description="Scene change data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "scene_change",
                "data": {
                    "id": 1,
                    "camera_id": "front_door",
                    "detected_at": "2026-01-03T10:30:00Z",
                    "change_type": "view_blocked",
                    "similarity_score": 0.23,
                },
            }
        }
    )


# Job tracking WebSocket schemas


class WebSocketJobStatus(StrEnum):
    """Valid job status values for WebSocket job tracking messages."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class WebSocketJobProgressData(BaseModel):
    """Data payload for job progress messages.

    Broadcast when a background job's progress changes (throttled to 10% increments).
    """

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job (export, cleanup, backup, sync)")
    progress: int = Field(..., ge=0, le=100, description="Job progress percentage (0-100)")
    status: str = Field(..., description="Current job status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "progress": 50,
                "status": "running",
            }
        }
    )


class WebSocketJobProgressMessage(BaseModel):
    """Complete job progress message envelope.

    Format:
        {
            "type": "job_progress",
            "data": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "progress": 50,
                "status": "running"
            }
        }
    """

    type: Literal["job_progress"] = Field(
        default="job_progress",
        description="Message type, always 'job_progress' for job progress messages",
    )
    data: WebSocketJobProgressData = Field(..., description="Job progress data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "job_progress",
                "data": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "job_type": "export",
                    "progress": 50,
                    "status": "running",
                },
            }
        }
    )


class WebSocketJobCompletedData(BaseModel):
    """Data payload for job completed messages.

    Broadcast when a background job finishes successfully.
    """

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job (export, cleanup, backup, sync)")
    result: Any = Field(None, description="Optional result data from the job")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "result": {"file_path": "/exports/events_2026-01-09.json"},
            }
        }
    )


class WebSocketJobCompletedMessage(BaseModel):
    """Complete job completed message envelope.

    Format:
        {
            "type": "job_completed",
            "data": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "result": {"file_path": "/exports/events_2026-01-09.json"}
            }
        }
    """

    type: Literal["job_completed"] = Field(
        default="job_completed",
        description="Message type, always 'job_completed' for job completed messages",
    )
    data: WebSocketJobCompletedData = Field(..., description="Job completed data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "job_completed",
                "data": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "job_type": "export",
                    "result": {"file_path": "/exports/events_2026-01-09.json"},
                },
            }
        }
    )


class WebSocketJobFailedData(BaseModel):
    """Data payload for job failed messages.

    Broadcast when a background job fails.
    """

    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job (export, cleanup, backup, sync)")
    error: str = Field(..., description="Error message describing the failure")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "error": "Database connection failed",
            }
        }
    )


class WebSocketJobFailedMessage(BaseModel):
    """Complete job failed message envelope.

    Format:
        {
            "type": "job_failed",
            "data": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "error": "Database connection failed"
            }
        }
    """

    type: Literal["job_failed"] = Field(
        default="job_failed",
        description="Message type, always 'job_failed' for job failed messages",
    )
    data: WebSocketJobFailedData = Field(..., description="Job failed data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "job_failed",
                "data": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "job_type": "export",
                    "error": "Database connection failed",
                },
            }
        }
    )


# ============================================================================
# WebSocket Event Type Registry (NEM-1984)
# ============================================================================


class WSEventType(StrEnum):
    """Comprehensive WebSocket event type registry.

    This enum defines all WebSocket event types used in the system.
    Event types follow a hierarchical naming convention: {domain}.{action}

    Domains:
    - detection: AI detection events from the pipeline
    - event: Security event lifecycle events
    - alert: Alert notifications and state changes
    - camera: Camera status and configuration changes
    - job: Background job lifecycle events
    - system: System health and status events
    - gpu: GPU monitoring events
    """

    # Detection events - AI pipeline results
    DETECTION_NEW = "detection.new"
    DETECTION_BATCH = "detection.batch"

    # Event events - Security event lifecycle
    EVENT_CREATED = "event.created"
    EVENT_UPDATED = "event.updated"
    EVENT_DELETED = "event.deleted"

    # Alert events - Alert notifications
    ALERT_CREATED = "alert.created"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_DISMISSED = "alert.dismissed"

    # Camera events - Camera status changes
    CAMERA_STATUS_CHANGED = "camera.status_changed"
    CAMERA_ENABLED = "camera.enabled"
    CAMERA_DISABLED = "camera.disabled"

    # Job events - Background job lifecycle
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"

    # System events - System health monitoring
    SYSTEM_HEALTH_CHANGED = "system.health_changed"
    SYSTEM_STATUS = "system.status"

    # GPU events - GPU monitoring
    GPU_STATS_UPDATED = "gpu.stats_updated"

    # Service events - Container/service status
    SERVICE_STATUS_CHANGED = "service.status_changed"

    # Scene change events - Camera view monitoring
    SCENE_CHANGE_DETECTED = "scene_change.detected"

    # Legacy event types for backward compatibility
    # These map to the existing message types in the codebase
    EVENT = "event"  # Maps to WebSocketEventMessage
    SERVICE_STATUS = "service_status"  # Maps to WebSocketServiceStatusMessage
    SCENE_CHANGE = "scene_change"  # Maps to WebSocketSceneChangeMessage
    PING = "ping"  # Heartbeat ping
    PONG = "pong"  # Heartbeat pong
    ERROR = "error"  # Error response


class WSEvent(BaseModel):
    """Generic WebSocket event wrapper with type, payload, and metadata.

    This model provides a standardized envelope for all WebSocket events,
    enabling consistent handling across different event types.
    """

    type: WSEventType = Field(..., description="Event type from WSEventType enum")
    payload: dict[str, Any] = Field(..., description="Event-specific payload data")
    timestamp: str = Field(..., description="ISO 8601 timestamp when the event occurred")
    channel: str | None = Field(
        None, description="Optional channel identifier (e.g., 'events', 'system')"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "detection.new",
                "payload": {
                    "detection_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_id": "660e8400-e29b-41d4-a716-446655440001",
                    "label": "person",
                    "confidence": 0.95,
                },
                "timestamp": "2026-01-09T12:00:00.000Z",
                "channel": "detections",
            }
        }
    )


# Event registry with comprehensive documentation for each event type
EVENT_REGISTRY: dict[WSEventType, dict[str, Any]] = {
    # Detection events
    WSEventType.DETECTION_NEW: {
        "description": "New detection from AI pipeline",
        "channel": "detections",
        "payload_schema": {
            "detection_id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique detection identifier",
            },
            "event_id": {
                "type": "string",
                "format": "uuid",
                "description": "Associated event identifier",
            },
            "label": {
                "type": "string",
                "description": "Detection class label (e.g., 'person', 'vehicle')",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Detection confidence score",
            },
            "bbox": {
                "type": "object",
                "description": "Bounding box coordinates",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                },
            },
            "camera_id": {"type": "string", "description": "Camera identifier"},
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "Detection timestamp",
            },
        },
        "example": {
            "detection_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": "660e8400-e29b-41d4-a716-446655440001",
            "label": "person",
            "confidence": 0.95,
            "bbox": {"x": 100, "y": 150, "width": 80, "height": 200},
            "camera_id": "front_door",
            "timestamp": "2026-01-09T12:00:00.000Z",
        },
    },
    WSEventType.DETECTION_BATCH: {
        "description": "Batch of detections from a single frame or time window",
        "channel": "detections",
        "payload_schema": {
            "batch_id": {"type": "string", "description": "Unique batch identifier"},
            "detections": {
                "type": "array",
                "items": {"$ref": "#/detection_new"},
                "description": "Array of detection objects",
            },
            "frame_timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "Frame capture timestamp",
            },
            "camera_id": {"type": "string", "description": "Camera identifier"},
        },
        "example": {
            "batch_id": "batch_abc123",
            "detections": [],
            "frame_timestamp": "2026-01-09T12:00:00.000Z",
            "camera_id": "front_door",
        },
    },
    # Event events
    WSEventType.EVENT_CREATED: {
        "description": "New security event created after AI analysis",
        "channel": "events",
        "payload_schema": {
            "id": {"type": "integer", "description": "Event database ID"},
            "event_id": {"type": "integer", "description": "Legacy alias for id"},
            "batch_id": {"type": "string", "description": "Detection batch identifier"},
            "camera_id": {"type": "string", "description": "Camera identifier"},
            "risk_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "AI-determined risk score",
            },
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Risk classification",
            },
            "summary": {"type": "string", "description": "Human-readable event summary"},
            "reasoning": {"type": "string", "description": "LLM reasoning for risk assessment"},
            "started_at": {
                "type": "string",
                "format": "date-time",
                "description": "Event start timestamp",
            },
        },
        "example": {
            "id": 1,
            "event_id": 1,
            "batch_id": "batch_abc123",
            "camera_id": "front_door",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected at front door",
            "reasoning": "Unknown individual approaching entrance during nighttime hours",
            "started_at": "2026-01-09T12:00:00.000Z",
        },
    },
    WSEventType.EVENT_UPDATED: {
        "description": "Existing security event updated",
        "channel": "events",
        "payload_schema": {
            "id": {"type": "integer", "description": "Event database ID"},
            "updated_fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of updated field names",
            },
            "risk_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Updated risk score (if changed)",
            },
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Updated risk level (if changed)",
            },
        },
        "example": {
            "id": 1,
            "updated_fields": ["risk_score", "risk_level"],
            "risk_score": 85,
            "risk_level": "critical",
        },
    },
    WSEventType.EVENT_DELETED: {
        "description": "Security event deleted",
        "channel": "events",
        "payload_schema": {
            "id": {"type": "integer", "description": "Deleted event ID"},
            "reason": {"type": "string", "description": "Deletion reason (optional)"},
        },
        "example": {"id": 1, "reason": "User dismissed as false positive"},
    },
    # Alert events
    WSEventType.ALERT_CREATED: {
        "description": "New alert generated from a security event",
        "channel": "alerts",
        "payload_schema": {
            "alert_id": {"type": "integer", "description": "Alert database ID"},
            "event_id": {"type": "integer", "description": "Associated event ID"},
            "severity": {
                "type": "string",
                "enum": ["info", "warning", "error", "critical"],
                "description": "Alert severity level",
            },
            "message": {"type": "string", "description": "Alert message"},
            "created_at": {
                "type": "string",
                "format": "date-time",
                "description": "Alert creation timestamp",
            },
        },
        "example": {
            "alert_id": 42,
            "event_id": 1,
            "severity": "warning",
            "message": "Person detected at front door after hours",
            "created_at": "2026-01-09T12:00:00.000Z",
        },
    },
    WSEventType.ALERT_ACKNOWLEDGED: {
        "description": "Alert acknowledged by user",
        "channel": "alerts",
        "payload_schema": {
            "alert_id": {"type": "integer", "description": "Alert database ID"},
            "acknowledged_at": {
                "type": "string",
                "format": "date-time",
                "description": "Acknowledgment timestamp",
            },
        },
        "example": {"alert_id": 42, "acknowledged_at": "2026-01-09T12:05:00.000Z"},
    },
    WSEventType.ALERT_DISMISSED: {
        "description": "Alert dismissed by user",
        "channel": "alerts",
        "payload_schema": {
            "alert_id": {"type": "integer", "description": "Alert database ID"},
            "dismissed_at": {
                "type": "string",
                "format": "date-time",
                "description": "Dismissal timestamp",
            },
            "reason": {"type": "string", "description": "Dismissal reason (optional)"},
        },
        "example": {
            "alert_id": 42,
            "dismissed_at": "2026-01-09T12:05:00.000Z",
            "reason": "False positive",
        },
    },
    # Camera events
    WSEventType.CAMERA_STATUS_CHANGED: {
        "description": "Camera status change (online/offline/error)",
        "channel": "cameras",
        "payload_schema": {
            "camera_id": {"type": "string", "description": "Camera identifier"},
            "status": {
                "type": "string",
                "enum": ["online", "offline", "error", "unknown"],
                "description": "New camera status",
            },
            "previous_status": {
                "type": "string",
                "enum": ["online", "offline", "error", "unknown"],
                "description": "Previous camera status",
            },
            "message": {"type": "string", "description": "Status change message (optional)"},
        },
        "example": {
            "camera_id": "front_door",
            "status": "online",
            "previous_status": "offline",
            "message": "Camera reconnected",
        },
    },
    WSEventType.CAMERA_ENABLED: {
        "description": "Camera enabled for monitoring",
        "channel": "cameras",
        "payload_schema": {
            "camera_id": {"type": "string", "description": "Camera identifier"},
            "enabled_at": {
                "type": "string",
                "format": "date-time",
                "description": "Enable timestamp",
            },
        },
        "example": {"camera_id": "front_door", "enabled_at": "2026-01-09T12:00:00.000Z"},
    },
    WSEventType.CAMERA_DISABLED: {
        "description": "Camera disabled from monitoring",
        "channel": "cameras",
        "payload_schema": {
            "camera_id": {"type": "string", "description": "Camera identifier"},
            "disabled_at": {
                "type": "string",
                "format": "date-time",
                "description": "Disable timestamp",
            },
            "reason": {"type": "string", "description": "Disable reason (optional)"},
        },
        "example": {
            "camera_id": "front_door",
            "disabled_at": "2026-01-09T12:00:00.000Z",
            "reason": "Maintenance",
        },
    },
    # Job events
    WSEventType.JOB_STARTED: {
        "description": "Background job started",
        "channel": "jobs",
        "payload_schema": {
            "job_id": {"type": "string", "description": "Job identifier"},
            "job_type": {
                "type": "string",
                "description": "Type of job (e.g., 'cleanup', 'reindex')",
            },
            "started_at": {
                "type": "string",
                "format": "date-time",
                "description": "Job start timestamp",
            },
            "estimated_duration": {
                "type": "integer",
                "description": "Estimated duration in seconds (optional)",
            },
        },
        "example": {
            "job_id": "job_abc123",
            "job_type": "cleanup",
            "started_at": "2026-01-09T12:00:00.000Z",
            "estimated_duration": 300,
        },
    },
    WSEventType.JOB_PROGRESS: {
        "description": "Background job progress update",
        "channel": "jobs",
        "payload_schema": {
            "job_id": {"type": "string", "description": "Job identifier"},
            "progress": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Progress percentage",
            },
            "message": {"type": "string", "description": "Progress message (optional)"},
        },
        "example": {"job_id": "job_abc123", "progress": 50, "message": "Processing batch 5 of 10"},
    },
    WSEventType.JOB_COMPLETED: {
        "description": "Background job completed successfully",
        "channel": "jobs",
        "payload_schema": {
            "job_id": {"type": "string", "description": "Job identifier"},
            "completed_at": {
                "type": "string",
                "format": "date-time",
                "description": "Completion timestamp",
            },
            "result": {"type": "object", "description": "Job result data (optional)"},
        },
        "example": {
            "job_id": "job_abc123",
            "completed_at": "2026-01-09T12:05:00.000Z",
            "result": {"items_processed": 100},
        },
    },
    WSEventType.JOB_FAILED: {
        "description": "Background job failed",
        "channel": "jobs",
        "payload_schema": {
            "job_id": {"type": "string", "description": "Job identifier"},
            "failed_at": {
                "type": "string",
                "format": "date-time",
                "description": "Failure timestamp",
            },
            "error": {"type": "string", "description": "Error message"},
            "retryable": {"type": "boolean", "description": "Whether the job can be retried"},
        },
        "example": {
            "job_id": "job_abc123",
            "failed_at": "2026-01-09T12:05:00.000Z",
            "error": "Connection timeout",
            "retryable": True,
        },
    },
    # System events
    WSEventType.SYSTEM_HEALTH_CHANGED: {
        "description": "System health status changed",
        "channel": "system",
        "payload_schema": {
            "health": {
                "type": "string",
                "enum": ["healthy", "degraded", "unhealthy"],
                "description": "Overall system health",
            },
            "previous_health": {
                "type": "string",
                "enum": ["healthy", "degraded", "unhealthy"],
                "description": "Previous health state",
            },
            "components": {
                "type": "object",
                "description": "Health status of individual components",
                "additionalProperties": {
                    "type": "string",
                    "enum": ["healthy", "degraded", "unhealthy"],
                },
            },
        },
        "example": {
            "health": "degraded",
            "previous_health": "healthy",
            "components": {"database": "healthy", "redis": "degraded", "ai_pipeline": "healthy"},
        },
    },
    WSEventType.SYSTEM_STATUS: {
        "description": "Periodic system status broadcast",
        "channel": "system",
        "payload_schema": {
            "gpu": {
                "type": "object",
                "description": "GPU metrics",
                "properties": {
                    "utilization": {"type": "number", "description": "GPU utilization percentage"},
                    "memory_used": {"type": "integer", "description": "GPU memory used in bytes"},
                    "memory_total": {"type": "integer", "description": "Total GPU memory in bytes"},
                    "temperature": {"type": "number", "description": "GPU temperature in Celsius"},
                    "inference_fps": {"type": "number", "description": "Current inference FPS"},
                },
            },
            "cameras": {
                "type": "object",
                "description": "Camera statistics",
                "properties": {
                    "active": {"type": "integer", "description": "Active camera count"},
                    "total": {"type": "integer", "description": "Total configured cameras"},
                },
            },
            "queue": {
                "type": "object",
                "description": "Processing queue status",
                "properties": {
                    "pending": {"type": "integer", "description": "Items pending processing"},
                    "processing": {"type": "integer", "description": "Items currently processing"},
                },
            },
            "health": {
                "type": "string",
                "enum": ["healthy", "degraded", "unhealthy"],
                "description": "Overall system health",
            },
        },
        "example": {
            "gpu": {
                "utilization": 45.5,
                "memory_used": 8192000000,
                "memory_total": 24576000000,
                "temperature": 65.0,
                "inference_fps": 30.5,
            },
            "cameras": {"active": 4, "total": 6},
            "queue": {"pending": 2, "processing": 1},
            "health": "healthy",
        },
    },
    # GPU events
    WSEventType.GPU_STATS_UPDATED: {
        "description": "GPU statistics update",
        "channel": "system",
        "payload_schema": {
            "utilization": {"type": "number", "description": "GPU utilization percentage (0-100)"},
            "memory_used": {"type": "integer", "description": "GPU memory used in bytes"},
            "memory_total": {"type": "integer", "description": "Total GPU memory in bytes"},
            "temperature": {"type": "number", "description": "GPU temperature in Celsius"},
            "inference_fps": {
                "type": "number",
                "description": "Current inference frames per second",
            },
        },
        "example": {
            "utilization": 45.5,
            "memory_used": 8192000000,
            "memory_total": 24576000000,
            "temperature": 65.0,
            "inference_fps": 30.5,
        },
    },
    # Service events
    WSEventType.SERVICE_STATUS_CHANGED: {
        "description": "Container/service status changed",
        "channel": "system",
        "payload_schema": {
            "service": {
                "type": "string",
                "description": "Service name (e.g., 'redis', 'rtdetr', 'nemotron')",
            },
            "status": {
                "type": "string",
                "enum": ["healthy", "unhealthy", "restarting", "restart_failed", "failed"],
                "description": "Service status",
            },
            "previous_status": {"type": "string", "description": "Previous service status"},
            "message": {"type": "string", "description": "Status message (optional)"},
        },
        "example": {
            "service": "rtdetr",
            "status": "healthy",
            "previous_status": "restarting",
            "message": "Service recovered",
        },
    },
    # Scene change events
    WSEventType.SCENE_CHANGE_DETECTED: {
        "description": "Camera scene change detected (potential tampering)",
        "channel": "events",
        "payload_schema": {
            "id": {"type": "integer", "description": "Scene change record ID"},
            "camera_id": {"type": "string", "description": "Camera identifier"},
            "detected_at": {
                "type": "string",
                "format": "date-time",
                "description": "Detection timestamp",
            },
            "change_type": {
                "type": "string",
                "enum": ["view_blocked", "angle_changed", "view_tampered", "unknown"],
                "description": "Type of scene change",
            },
            "similarity_score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "SSIM similarity score (lower = more different)",
            },
        },
        "example": {
            "id": 1,
            "camera_id": "front_door",
            "detected_at": "2026-01-09T12:00:00.000Z",
            "change_type": "view_blocked",
            "similarity_score": 0.23,
        },
    },
    # Legacy event types (for backward compatibility)
    WSEventType.EVENT: {
        "description": "Legacy event message (maps to WebSocketEventMessage)",
        "channel": "events",
        "payload_schema": {"$ref": "#/event_created"},
        "deprecated": True,
        "replacement": "event.created",
    },
    WSEventType.SERVICE_STATUS: {
        "description": "Legacy service status message (maps to WebSocketServiceStatusMessage)",
        "channel": "system",
        "payload_schema": {
            "service": {"type": "string"},
            "status": {"type": "string"},
            "message": {"type": "string"},
        },
        "deprecated": True,
        "replacement": "service.status_changed",
    },
    WSEventType.SCENE_CHANGE: {
        "description": "Legacy scene change message (maps to WebSocketSceneChangeMessage)",
        "channel": "events",
        "payload_schema": {"$ref": "#/scene_change_detected"},
        "deprecated": True,
        "replacement": "scene_change.detected",
    },
    WSEventType.PING: {
        "description": "Heartbeat ping message",
        "channel": None,
        "payload_schema": {},
        "example": {},
    },
    WSEventType.PONG: {
        "description": "Heartbeat pong response",
        "channel": None,
        "payload_schema": {},
        "example": {},
    },
    WSEventType.ERROR: {
        "description": "Error response message",
        "channel": None,
        "payload_schema": {
            "error": {"type": "string", "description": "Error code"},
            "message": {"type": "string", "description": "Error message"},
            "details": {"type": "object", "description": "Additional error details"},
        },
        "example": {
            "error": "invalid_json",
            "message": "Message must be valid JSON",
            "details": None,
        },
    },
}


class EventTypeInfo(BaseModel):
    """Information about a single WebSocket event type."""

    type: str = Field(..., description="Event type identifier")
    description: str = Field(..., description="Human-readable description")
    channel: str | None = Field(None, description="WebSocket channel this event is broadcast on")
    payload_schema: dict[str, Any] = Field(..., description="JSON Schema for the event payload")
    example: dict[str, Any] | None = Field(None, description="Example payload")
    deprecated: bool = Field(False, description="Whether this event type is deprecated")
    replacement: str | None = Field(None, description="Replacement event type if deprecated")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "detection.new",
                "description": "New detection from AI pipeline",
                "channel": "detections",
                "payload_schema": {
                    "detection_id": {"type": "string", "format": "uuid"},
                    "label": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "example": {"detection_id": "123", "label": "person", "confidence": 0.95},
                "deprecated": False,
                "replacement": None,
            }
        }
    )


class EventRegistryResponse(BaseModel):
    """Response containing the complete WebSocket event registry."""

    event_types: list[EventTypeInfo] = Field(..., description="List of all available event types")
    channels: list[str] = Field(..., description="List of all available WebSocket channels")
    total_count: int = Field(..., description="Total number of event types")
    deprecated_count: int = Field(..., description="Number of deprecated event types")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_types": [],
                "channels": ["detections", "events", "alerts", "cameras", "jobs", "system"],
                "total_count": 25,
                "deprecated_count": 3,
            }
        }
    )


def get_event_registry_response() -> EventRegistryResponse:
    """Build the event registry response from EVENT_REGISTRY.

    Returns:
        EventRegistryResponse: Complete event registry with all event types.
    """
    event_types: list[EventTypeInfo] = []
    channels: set[str] = set()
    deprecated_count = 0

    for event_type, info in EVENT_REGISTRY.items():
        event_info = EventTypeInfo(
            type=event_type.value,
            description=info.get("description", ""),
            channel=info.get("channel"),
            payload_schema=info.get("payload_schema", {}),
            example=info.get("example"),
            deprecated=info.get("deprecated", False),
            replacement=info.get("replacement"),
        )
        event_types.append(event_info)

        if info.get("channel"):
            channels.add(info["channel"])

        if info.get("deprecated", False):
            deprecated_count += 1

    return EventRegistryResponse(
        event_types=sorted(event_types, key=lambda x: x.type),
        channels=sorted(channels),
        total_count=len(event_types),
        deprecated_count=deprecated_count,
    )
