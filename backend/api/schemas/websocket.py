"""Pydantic schemas for WebSocket message validation.

This module defines schemas for validating incoming WebSocket message payloads.
Clients can send messages to WebSocket endpoints, and these schemas ensure
proper structure and type validation before processing.

Supported message types:
- ping: Keep-alive heartbeat (responds with pong)
- pong: Response to server-initiated ping
- subscribe: Subscribe to specific event channels
- unsubscribe: Unsubscribe from event channels
- resync: Request resync after detecting sequence gap (responds with resync_ack)
"""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    field_validator,
    model_validator,
)


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
    RESYNC = auto()


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
    """Valid service status values for WebSocket health monitoring messages.

    Includes both health states and worker lifecycle states for comprehensive
    status reporting across services and workers.
    """

    # Health states
    HEALTHY = auto()
    UNHEALTHY = auto()
    # Worker lifecycle states
    RUNNING = auto()
    STOPPED = auto()
    CRASHED = auto()
    DISABLED = auto()  # Service intentionally disabled
    # Transition states
    RESTARTING = auto()
    RESTART_FAILED = auto()
    FAILED = auto()


class WebSocketServiceStatusData(BaseModel):
    """Data payload for service status messages.

    Broadcast by the health monitor when a service's status changes.

    Note: Accepts both 'service' and 'name' fields for compatibility with
    ServiceInfo schema used by container orchestrator.
    """

    service: str = Field(
        ...,
        validation_alias=AliasChoices("service", "name"),
        description="Name of the service (redis, rtdetr, nemotron)",
    )
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
        extra="ignore",  # Allow extra fields from ServiceInfo
        json_schema_extra={
            "example": {
                "service": "redis",
                "status": "healthy",
                "message": "Service responding normally",
            }
        },
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


class WebSocketCameraEventType(StrEnum):
    """Camera event types for WebSocket messages (NEM-2295).

    Distinguishes between different types of camera status changes:
    - camera.online: Camera came online
    - camera.offline: Camera went offline
    - camera.error: Camera encountered an error
    - camera.updated: Camera configuration was updated
    """

    CAMERA_ONLINE = "camera.online"
    CAMERA_OFFLINE = "camera.offline"
    CAMERA_ERROR = "camera.error"
    CAMERA_UPDATED = "camera.updated"


class WebSocketCameraStatusData(BaseModel):
    """Data payload for camera status messages.

    Broadcast when a camera's status changes (online, offline, error, unknown).

    NEM-2295: Added event_type, camera_name, timestamp, and details fields.
    """

    event_type: WebSocketCameraEventType = Field(
        ...,
        description="Type of camera event (camera.online, camera.offline, camera.error, camera.updated)",
    )
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    camera_name: str = Field(..., description="Human-readable camera name")
    status: WebSocketCameraStatus = Field(..., description="Current camera status")
    timestamp: str = Field(..., description="ISO 8601 timestamp when the event occurred")
    previous_status: WebSocketCameraStatus | None = Field(
        None, description="Previous camera status before this change"
    )
    reason: str | None = Field(None, description="Optional reason for the status change")
    details: dict[str, Any] | None = Field(None, description="Optional additional details")

    @field_validator("event_type", mode="before")
    @classmethod
    def validate_event_type(cls, v: str | WebSocketCameraEventType) -> WebSocketCameraEventType:
        """Validate and convert event_type to WebSocketCameraEventType enum."""
        if isinstance(v, WebSocketCameraEventType):
            return v
        if isinstance(v, str):
            # Try direct value match first
            for event_type in WebSocketCameraEventType:
                if event_type.value == v:
                    return event_type
            valid_values = [e.value for e in WebSocketCameraEventType]
            raise ValueError(f"Invalid event_type '{v}'. Must be one of: {valid_values}")
        raise ValueError(
            f"event_type must be a string or WebSocketCameraEventType enum, got {type(v)}"
        )

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
                "event_type": "camera.offline",
                "camera_id": "front_door",
                "camera_name": "Front Door Camera",
                "status": "offline",
                "timestamp": "2026-01-09T10:30:00Z",
                "previous_status": "online",
                "reason": "No activity detected for 5 minutes",
                "details": None,
            }
        }
    )


class WebSocketCameraStatusMessage(BaseModel):
    """Complete camera status message envelope.

    This is the canonical format for camera status messages broadcast via WebSocket.
    Consistent with other message types, data is wrapped in a standard envelope.

    NEM-2295: Added event_type, camera_name, timestamp, and details fields.

    Format:
        {
            "type": "camera_status",
            "data": {
                "event_type": "camera.offline",
                "camera_id": "front_door",
                "camera_name": "Front Door Camera",
                "status": "offline",
                "timestamp": "2026-01-09T10:30:00Z",
                "previous_status": "online",
                "reason": "No activity detected",
                "details": null
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
                    "event_type": "camera.offline",
                    "camera_id": "front_door",
                    "camera_name": "Front Door Camera",
                    "status": "offline",
                    "timestamp": "2026-01-09T10:30:00Z",
                    "previous_status": "online",
                    "reason": "No activity detected for 5 minutes",
                    "details": None,
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


# =============================================================================
# Detection WebSocket Message Schemas (NEM-2506)
# =============================================================================


class WebSocketDetectionBbox(BaseModel):
    """Bounding box coordinates for a detection.

    Coordinates are normalized values (0.0 to 1.0) relative to the image dimensions.
    """

    x: float = Field(..., ge=0.0, le=1.0, description="Normalized X coordinate (left edge)")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized Y coordinate (top edge)")
    width: float = Field(..., ge=0.0, le=1.0, description="Normalized width")
    height: float = Field(..., ge=0.0, le=1.0, description="Normalized height")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "x": 0.25,
                "y": 0.15,
                "width": 0.1,
                "height": 0.25,
            }
        }
    )


class WebSocketDetectionNewData(BaseModel):
    """Data payload for detection.new messages broadcast to WebSocket clients.

    This schema defines the contract for individual detection data sent from
    the backend to WebSocket clients when a new detection is added to a batch.

    Fields:
        detection_id: Unique detection identifier (database ID)
        batch_id: Batch identifier this detection belongs to
        camera_id: Normalized camera ID (e.g., "front_door")
        label: Detection class label (e.g., "person", "vehicle")
        confidence: Detection confidence score (0.0-1.0)
        bbox: Bounding box coordinates (optional)
        timestamp: ISO 8601 timestamp when the detection occurred
    """

    detection_id: int = Field(..., description="Unique detection identifier (database ID)")
    batch_id: str = Field(..., description="Batch identifier this detection belongs to")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    label: str = Field(..., description="Detection class label (e.g., 'person', 'vehicle')")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Detection confidence score (0.0-1.0)"
    )
    bbox: WebSocketDetectionBbox | None = Field(
        None, description="Bounding box coordinates (optional)"
    )
    timestamp: str = Field(..., description="ISO 8601 timestamp when the detection occurred")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection_id": 123,
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "label": "person",
                "confidence": 0.95,
                "bbox": {"x": 0.25, "y": 0.15, "width": 0.1, "height": 0.25},
                "timestamp": "2026-01-13T12:00:00.000Z",
            }
        }
    )


class WebSocketDetectionNewMessage(BaseModel):
    """Complete detection.new message envelope sent to WebSocket clients.

    This is the canonical format for new detection messages broadcast via WebSocket.
    The message wraps detection data in a standard envelope with a type field.

    Format:
        {
            "type": "detection.new",
            "data": {
                "detection_id": 123,
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "label": "person",
                "confidence": 0.95,
                "timestamp": "2026-01-13T12:00:00.000Z"
            }
        }
    """

    type: Literal["detection.new"] = Field(
        default="detection.new",
        description="Message type, always 'detection.new' for new detection messages",
    )
    data: WebSocketDetectionNewData = Field(..., description="Detection data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "detection.new",
                "data": {
                    "detection_id": 123,
                    "batch_id": "batch_abc123",
                    "camera_id": "front_door",
                    "label": "person",
                    "confidence": 0.95,
                    "bbox": {"x": 0.25, "y": 0.15, "width": 0.1, "height": 0.25},
                    "timestamp": "2026-01-13T12:00:00.000Z",
                },
            }
        }
    )


class WebSocketDetectionBatchData(BaseModel):
    """Data payload for detection.batch messages broadcast to WebSocket clients.

    This schema defines the contract for batch detection data sent from the
    backend to WebSocket clients when a batch is closed and ready for analysis.

    Fields:
        batch_id: Unique batch identifier
        camera_id: Normalized camera ID (e.g., "front_door")
        detection_ids: List of detection IDs in this batch
        detection_count: Number of detections in the batch
        started_at: ISO 8601 timestamp when the batch started
        closed_at: ISO 8601 timestamp when the batch was closed
        close_reason: Reason for batch closure (timeout, idle, max_size)
    """

    batch_id: str = Field(..., description="Unique batch identifier")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    detection_ids: list[int] = Field(..., description="List of detection IDs in this batch")
    detection_count: int = Field(..., ge=0, description="Number of detections in the batch")
    started_at: str = Field(..., description="ISO 8601 timestamp when the batch started")
    closed_at: str = Field(..., description="ISO 8601 timestamp when the batch was closed")
    close_reason: str | None = Field(
        None, description="Reason for batch closure (timeout, idle, max_size)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "detection_ids": [123, 124, 125],
                "detection_count": 3,
                "started_at": "2026-01-13T12:00:00.000Z",
                "closed_at": "2026-01-13T12:01:30.000Z",
                "close_reason": "timeout",
            }
        }
    )


class WebSocketDetectionBatchMessage(BaseModel):
    """Complete detection.batch message envelope sent to WebSocket clients.

    This is the canonical format for batch detection messages broadcast via WebSocket.
    The message wraps batch data in a standard envelope with a type field.

    Format:
        {
            "type": "detection.batch",
            "data": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "detection_ids": [123, 124, 125],
                "detection_count": 3,
                "started_at": "2026-01-13T12:00:00.000Z",
                "closed_at": "2026-01-13T12:01:30.000Z"
            }
        }
    """

    type: Literal["detection.batch"] = Field(
        default="detection.batch",
        description="Message type, always 'detection.batch' for batch detection messages",
    )
    data: WebSocketDetectionBatchData = Field(..., description="Batch detection data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "detection.batch",
                "data": {
                    "batch_id": "batch_abc123",
                    "camera_id": "front_door",
                    "detection_ids": [123, 124, 125],
                    "detection_count": 3,
                    "started_at": "2026-01-13T12:00:00.000Z",
                    "closed_at": "2026-01-13T12:01:30.000Z",
                    "close_reason": "timeout",
                },
            }
        }
    )


# =============================================================================
# Batch Analysis Status WebSocket Message Schemas (NEM-3607)
# =============================================================================


class WebSocketBatchAnalysisStartedData(BaseModel):
    """Data payload for batch.analysis_started messages broadcast to WebSocket clients.

    This schema defines the contract for batch analysis status data sent from the
    backend to WebSocket clients when a batch is dequeued and starts LLM analysis.

    Fields:
        batch_id: Unique batch identifier
        camera_id: Normalized camera ID (e.g., "front_door")
        detection_count: Number of detections in the batch
        queue_position: Optional position in queue when dequeued (0 = front)
        started_at: ISO 8601 timestamp when analysis started
    """

    batch_id: str = Field(..., description="Unique batch identifier")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    detection_count: int = Field(..., ge=0, description="Number of detections in the batch")
    queue_position: int | None = Field(
        None, ge=0, description="Position in queue when dequeued (0 = front)"
    )
    started_at: str = Field(..., description="ISO 8601 timestamp when analysis started")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "detection_count": 3,
                "queue_position": 0,
                "started_at": "2026-01-13T12:01:30.000Z",
            }
        }
    )


class WebSocketBatchAnalysisStartedMessage(BaseModel):
    """Complete batch.analysis_started message envelope sent to WebSocket clients.

    This is the canonical format for batch analysis started messages broadcast via WebSocket.
    The message wraps batch data in a standard envelope with a type field.

    Format:
        {
            "type": "batch.analysis_started",
            "data": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "detection_count": 3,
                "queue_position": 0,
                "started_at": "2026-01-13T12:01:30.000Z"
            }
        }
    """

    type: Literal["batch.analysis_started"] = Field(
        default="batch.analysis_started",
        description="Message type, always 'batch.analysis_started' for analysis started messages",
    )
    data: WebSocketBatchAnalysisStartedData = Field(
        ..., description="Batch analysis started data payload"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "batch.analysis_started",
                "data": {
                    "batch_id": "batch_abc123",
                    "camera_id": "front_door",
                    "detection_count": 3,
                    "queue_position": 0,
                    "started_at": "2026-01-13T12:01:30.000Z",
                },
            }
        }
    )


class WebSocketBatchAnalysisCompletedData(BaseModel):
    """Data payload for batch.analysis_completed messages broadcast to WebSocket clients.

    This schema defines the contract for batch analysis completion data sent from the
    backend to WebSocket clients when LLM analysis finishes successfully.

    Fields:
        batch_id: Unique batch identifier
        camera_id: Normalized camera ID (e.g., "front_door")
        event_id: ID of the created Event record
        risk_score: Risk score assigned by LLM (0-100)
        risk_level: Risk level (low, medium, high, critical)
        duration_ms: Analysis duration in milliseconds
        completed_at: ISO 8601 timestamp when analysis completed
    """

    batch_id: str = Field(..., description="Unique batch identifier")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    event_id: int = Field(..., description="ID of the created Event record")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score assigned by LLM (0-100)")
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    duration_ms: int = Field(..., ge=0, description="Analysis duration in milliseconds")
    completed_at: str = Field(..., description="ISO 8601 timestamp when analysis completed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "event_id": 42,
                "risk_score": 75,
                "risk_level": "high",
                "duration_ms": 2500,
                "completed_at": "2026-01-13T12:01:35.000Z",
            }
        }
    )


class WebSocketBatchAnalysisCompletedMessage(BaseModel):
    """Complete batch.analysis_completed message envelope sent to WebSocket clients.

    This is the canonical format for batch analysis completed messages broadcast via WebSocket.
    The message wraps batch data in a standard envelope with a type field.

    Format:
        {
            "type": "batch.analysis_completed",
            "data": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "event_id": 42,
                "risk_score": 75,
                "risk_level": "high",
                "duration_ms": 2500,
                "completed_at": "2026-01-13T12:01:35.000Z"
            }
        }
    """

    type: Literal["batch.analysis_completed"] = Field(
        default="batch.analysis_completed",
        description="Message type, always 'batch.analysis_completed' for analysis completed messages",
    )
    data: WebSocketBatchAnalysisCompletedData = Field(
        ..., description="Batch analysis completed data payload"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "batch.analysis_completed",
                "data": {
                    "batch_id": "batch_abc123",
                    "camera_id": "front_door",
                    "event_id": 42,
                    "risk_score": 75,
                    "risk_level": "high",
                    "duration_ms": 2500,
                    "completed_at": "2026-01-13T12:01:35.000Z",
                },
            }
        }
    )


class WebSocketBatchAnalysisFailedData(BaseModel):
    """Data payload for batch.analysis_failed messages broadcast to WebSocket clients.

    This schema defines the contract for batch analysis failure data sent from the
    backend to WebSocket clients when LLM analysis fails with an error.

    Fields:
        batch_id: Unique batch identifier
        camera_id: Normalized camera ID (e.g., "front_door")
        error: Error message describing the failure
        error_type: Categorized error type for UI display
        retryable: Whether the operation can be retried
        failed_at: ISO 8601 timestamp when analysis failed
    """

    batch_id: str = Field(..., description="Unique batch identifier")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    error: str = Field(..., description="Error message describing the failure")
    error_type: str = Field(
        ..., description="Categorized error type (timeout, connection, validation, processing)"
    )
    retryable: bool = Field(..., description="Whether the operation can be retried")
    failed_at: str = Field(..., description="ISO 8601 timestamp when analysis failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "error": "LLM service timeout after 120 seconds",
                "error_type": "timeout",
                "retryable": True,
                "failed_at": "2026-01-13T12:03:30.000Z",
            }
        }
    )


class WebSocketBatchAnalysisFailedMessage(BaseModel):
    """Complete batch.analysis_failed message envelope sent to WebSocket clients.

    This is the canonical format for batch analysis failed messages broadcast via WebSocket.
    The message wraps batch data in a standard envelope with a type field.

    Format:
        {
            "type": "batch.analysis_failed",
            "data": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "error": "LLM service timeout after 120 seconds",
                "error_type": "timeout",
                "retryable": true,
                "failed_at": "2026-01-13T12:03:30.000Z"
            }
        }
    """

    type: Literal["batch.analysis_failed"] = Field(
        default="batch.analysis_failed",
        description="Message type, always 'batch.analysis_failed' for analysis failed messages",
    )
    data: WebSocketBatchAnalysisFailedData = Field(
        ..., description="Batch analysis failed data payload"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "batch.analysis_failed",
                "data": {
                    "batch_id": "batch_abc123",
                    "camera_id": "front_door",
                    "error": "LLM service timeout after 120 seconds",
                    "error_type": "timeout",
                    "retryable": True,
                    "failed_at": "2026-01-13T12:03:30.000Z",
                },
            }
        }
    )


# =============================================================================
# Alert WebSocket Message Schemas (NEM-1981)
# =============================================================================


class WebSocketAlertEventType(StrEnum):
    """WebSocket event types for alert state changes.

    Event types:
    - ALERT_CREATED: New alert triggered from rule evaluation
    - ALERT_UPDATED: Alert modified (e.g., metadata, channels updated)
    - ALERT_DELETED: Alert permanently deleted from the system
    - ALERT_ACKNOWLEDGED: Alert marked as seen by user
    - ALERT_RESOLVED: Alert resolved (long-running issues cleared)
    - ALERT_DISMISSED: Alert dismissed by user
    """

    ALERT_CREATED = auto()
    ALERT_UPDATED = auto()
    ALERT_DELETED = auto()
    ALERT_ACKNOWLEDGED = auto()
    ALERT_RESOLVED = auto()
    ALERT_DISMISSED = auto()


class WebSocketAlertSeverity(StrEnum):
    """Alert severity levels for WebSocket messages.

    Mirrors backend.models.alert.AlertSeverityEnum for WebSocket message validation.
    """

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class WebSocketAlertStatus(StrEnum):
    """Alert status values for WebSocket messages.

    Mirrors backend.models.alert.AlertStatusEnum for WebSocket message validation.
    """

    PENDING = auto()
    DELIVERED = auto()
    ACKNOWLEDGED = auto()
    DISMISSED = auto()


class WebSocketAlertData(BaseModel):
    """Data payload for alert messages broadcast to /ws/events clients.

    This schema defines the contract for alert data sent from the backend
    to WebSocket clients when alerts are created, acknowledged, or dismissed.

    Fields:
        id: Unique alert identifier (UUID)
        event_id: Event ID that triggered this alert
        rule_id: Alert rule UUID that matched (nullable)
        severity: Alert severity level (low, medium, high, critical)
        status: Current alert status (pending, delivered, acknowledged, dismissed)
        dedup_key: Deduplication key for alert grouping
        created_at: ISO 8601 timestamp when the alert was created
        updated_at: ISO 8601 timestamp when the alert was last updated
    """

    id: str = Field(..., description="Unique alert identifier (UUID)")
    event_id: int = Field(..., description="Event ID that triggered this alert")
    rule_id: str | None = Field(None, description="Alert rule UUID that matched")
    severity: WebSocketAlertSeverity = Field(
        ..., description='Alert severity level ("low", "medium", "high", "critical")'
    )
    status: WebSocketAlertStatus = Field(
        ...,
        description='Current alert status ("pending", "delivered", "acknowledged", "dismissed")',
    )
    dedup_key: str = Field(..., description="Deduplication key for alert grouping")
    created_at: str = Field(..., description="ISO 8601 timestamp when the alert was created")
    updated_at: str = Field(..., description="ISO 8601 timestamp when the alert was last updated")

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, v: str | WebSocketAlertSeverity) -> WebSocketAlertSeverity:
        """Validate and convert severity to WebSocketAlertSeverity enum.

        Accepts string values for backward compatibility with existing clients.
        """
        if isinstance(v, WebSocketAlertSeverity):
            return v
        if isinstance(v, str):
            try:
                return WebSocketAlertSeverity(v.lower())
            except ValueError:
                valid_values = [level.value for level in WebSocketAlertSeverity]
                raise ValueError(
                    f"Invalid severity '{v}'. Must be one of: {valid_values}"
                ) from None
        raise ValueError(f"severity must be a string or WebSocketAlertSeverity enum, got {type(v)}")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str | WebSocketAlertStatus) -> WebSocketAlertStatus:
        """Validate and convert status to WebSocketAlertStatus enum.

        Accepts string values for backward compatibility with existing clients.
        """
        if isinstance(v, WebSocketAlertStatus):
            return v
        if isinstance(v, str):
            try:
                return WebSocketAlertStatus(v.lower())
            except ValueError:
                valid_values = [status.value for status in WebSocketAlertStatus]
                raise ValueError(f"Invalid status '{v}'. Must be one of: {valid_values}") from None
        raise ValueError(f"status must be a string or WebSocketAlertStatus enum, got {type(v)}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                "severity": "high",
                "status": "pending",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-09T12:00:00Z",
                "updated_at": "2026-01-09T12:00:00Z",
            }
        }
    )


class WebSocketAlertCreatedMessage(BaseModel):
    """Complete alert created message envelope sent to /ws/events clients.

    This is the canonical format for alert creation messages broadcast via WebSocket.
    The message wraps alert data in a standard envelope with a type field.

    Format:
        {
            "type": "alert_created",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                "severity": "high",
                "status": "pending",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-09T12:00:00Z",
                "updated_at": "2026-01-09T12:00:00Z"
            }
        }
    """

    type: Literal["alert_created"] = Field(
        default="alert_created",
        description="Message type, always 'alert_created' for alert creation messages",
    )
    data: WebSocketAlertData = Field(..., description="Alert data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "alert_created",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_id": 123,
                    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                    "severity": "high",
                    "status": "pending",
                    "dedup_key": "front_door:person:rule1",
                    "created_at": "2026-01-09T12:00:00Z",
                    "updated_at": "2026-01-09T12:00:00Z",
                },
            }
        }
    )


class WebSocketAlertAcknowledgedMessage(BaseModel):
    """Complete alert acknowledged message envelope sent to /ws/events clients.

    This is the canonical format for alert acknowledgment messages broadcast via WebSocket.
    The message wraps alert data in a standard envelope with a type field.

    Format:
        {
            "type": "alert_acknowledged",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                "severity": "high",
                "status": "acknowledged",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-09T12:00:00Z",
                "updated_at": "2026-01-09T12:01:00Z"
            }
        }
    """

    type: Literal["alert_acknowledged"] = Field(
        default="alert_acknowledged",
        description="Message type, always 'alert_acknowledged' for alert acknowledgment messages",
    )
    data: WebSocketAlertData = Field(..., description="Alert data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "alert_acknowledged",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_id": 123,
                    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                    "severity": "high",
                    "status": "acknowledged",
                    "dedup_key": "front_door:person:rule1",
                    "created_at": "2026-01-09T12:00:00Z",
                    "updated_at": "2026-01-09T12:01:00Z",
                },
            }
        }
    )


class WebSocketAlertDismissedMessage(BaseModel):
    """Complete alert dismissed message envelope sent to /ws/events clients.

    This is the canonical format for alert dismissal messages broadcast via WebSocket.
    The message wraps alert data in a standard envelope with a type field.

    Format:
        {
            "type": "alert_dismissed",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                "severity": "high",
                "status": "dismissed",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-09T12:00:00Z",
                "updated_at": "2026-01-09T12:02:00Z"
            }
        }
    """

    type: Literal["alert_dismissed"] = Field(
        default="alert_dismissed",
        description="Message type, always 'alert_dismissed' for alert dismissal messages",
    )
    data: WebSocketAlertData = Field(..., description="Alert data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "alert_dismissed",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_id": 123,
                    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                    "severity": "high",
                    "status": "dismissed",
                    "dedup_key": "front_door:person:rule1",
                    "created_at": "2026-01-09T12:00:00Z",
                    "updated_at": "2026-01-09T12:02:00Z",
                },
            }
        }
    )


class WebSocketAlertUpdatedMessage(BaseModel):
    """Complete alert updated message envelope sent to /ws/events clients.

    This is the canonical format for alert update messages broadcast via WebSocket.
    Sent when an alert is modified (e.g., metadata, channels, or other properties updated).
    The message wraps alert data in a standard envelope with a type field.

    Format:
        {
            "type": "alert_updated",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                "severity": "high",
                "status": "pending",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-09T12:00:00Z",
                "updated_at": "2026-01-09T12:00:30Z"
            }
        }
    """

    type: Literal["alert_updated"] = Field(
        default="alert_updated",
        description="Message type, always 'alert_updated' for alert update messages",
    )
    data: WebSocketAlertData = Field(..., description="Alert data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "alert_updated",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_id": 123,
                    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                    "severity": "high",
                    "status": "pending",
                    "dedup_key": "front_door:person:rule1",
                    "created_at": "2026-01-09T12:00:00Z",
                    "updated_at": "2026-01-09T12:00:30Z",
                },
            }
        }
    )


class WebSocketAlertDeletedData(BaseModel):
    """Data payload for alert deleted messages broadcast to /ws/events clients.

    This schema is used when an alert is permanently deleted. It contains only
    the alert ID and optional reason, as the full alert data is no longer available.

    Fields:
        id: UUID of the deleted alert
        reason: Optional reason for deletion
    """

    id: str = Field(..., description="Deleted alert UUID")
    reason: str | None = Field(None, description="Reason for deletion")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "reason": "Duplicate alert",
            }
        }
    )


class WebSocketAlertDeletedMessage(BaseModel):
    """Complete alert deleted message envelope sent to /ws/events clients.

    This is the canonical format for alert deletion messages broadcast via WebSocket.
    Sent when an alert is permanently deleted from the system.
    The message wraps deletion data in a standard envelope with a type field.

    Format:
        {
            "type": "alert_deleted",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "reason": "Duplicate alert"
            }
        }
    """

    type: Literal["alert_deleted"] = Field(
        default="alert_deleted",
        description="Message type, always 'alert_deleted' for alert deletion messages",
    )
    data: WebSocketAlertDeletedData = Field(..., description="Alert deletion data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "alert_deleted",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "reason": "Duplicate alert",
                },
            }
        }
    )


class WebSocketAlertResolvedMessage(BaseModel):
    """Complete alert resolved message envelope sent to /ws/events clients.

    This is the canonical format for alert resolution messages broadcast via WebSocket.
    Sent when an alert is resolved/dismissed. Semantically similar to dismissed but
    provides a clearer event name for resolution workflows.
    The message wraps alert data in a standard envelope with a type field.

    Format:
        {
            "type": "alert_resolved",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                "severity": "high",
                "status": "dismissed",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-09T12:00:00Z",
                "updated_at": "2026-01-09T12:02:00Z"
            }
        }
    """

    type: Literal["alert_resolved"] = Field(
        default="alert_resolved",
        description="Message type, always 'alert_resolved' for alert resolution messages",
    )
    data: WebSocketAlertData = Field(..., description="Alert data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "alert_resolved",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_id": 123,
                    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                    "severity": "high",
                    "status": "dismissed",
                    "dedup_key": "front_door:person:rule1",
                    "created_at": "2026-01-09T12:00:00Z",
                    "updated_at": "2026-01-09T12:02:00Z",
                },
            }
        }
    )


# =============================================================================
# Worker Status WebSocket Message Schemas (NEM-2461)
# =============================================================================


class WebSocketWorkerType(StrEnum):
    """Valid worker types for WebSocket worker status messages."""

    DETECTION = auto()
    ANALYSIS = auto()
    TIMEOUT = auto()
    METRICS = auto()


class WebSocketWorkerState(StrEnum):
    """Valid worker state values for WebSocket messages."""

    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()


class WebSocketWorkerStatusData(BaseModel):
    """Data payload for worker status messages.

    Broadcast when a pipeline worker's state changes (started, stopped, error, etc.).
    """

    event_type: str = Field(
        ...,
        description="Type of worker event (worker.started, worker.stopped, worker.error, etc.)",
    )
    worker_name: str = Field(..., description="Worker instance name")
    worker_type: WebSocketWorkerType = Field(..., description="Type of worker")
    timestamp: str = Field(..., description="ISO 8601 timestamp when the event occurred")
    error: str | None = Field(None, description="Error message if applicable")
    error_type: str | None = Field(None, description="Categorized error type")
    failure_count: int | None = Field(None, description="Number of consecutive failures")
    items_processed: int | None = Field(None, description="Total items processed")
    reason: str | None = Field(None, description="Reason for state change")
    previous_state: str | None = Field(None, description="Previous worker state")
    attempt: int | None = Field(None, description="Current restart attempt number")
    max_attempts: int | None = Field(None, description="Maximum restart attempts allowed")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")

    @field_validator("worker_type", mode="before")
    @classmethod
    def validate_worker_type(cls, v: str | WebSocketWorkerType) -> WebSocketWorkerType:
        """Validate and convert worker_type to WebSocketWorkerType enum."""
        if isinstance(v, WebSocketWorkerType):
            return v
        if isinstance(v, str):
            try:
                return WebSocketWorkerType(v.lower())
            except ValueError:
                valid_values = [wt.value for wt in WebSocketWorkerType]
                raise ValueError(
                    f"Invalid worker_type '{v}'. Must be one of: {valid_values}"
                ) from None
        raise ValueError(f"worker_type must be a string or WebSocketWorkerType enum, got {type(v)}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "worker.started",
                "worker_name": "detection_worker",
                "worker_type": "detection",
                "timestamp": "2026-01-13T10:30:00Z",
                "error": None,
                "error_type": None,
                "failure_count": None,
                "items_processed": None,
                "reason": None,
                "previous_state": None,
                "attempt": None,
                "max_attempts": None,
                "metadata": None,
            }
        }
    )


class WebSocketWorkerStatusMessage(BaseModel):
    """Complete worker status message envelope.

    This is the canonical format for worker status messages broadcast via WebSocket.
    Consistent with other message types, data is wrapped in a standard envelope.

    Format:
        {
            "type": "worker_status",
            "data": {
                "event_type": "worker.started",
                "worker_name": "detection_worker",
                "worker_type": "detection",
                "timestamp": "2026-01-13T10:30:00Z"
            },
            "timestamp": "2026-01-13T10:30:00Z"
        }
    """

    type: Literal["worker_status"] = Field(
        default="worker_status",
        description="Message type, always 'worker_status' for worker status messages",
    )
    data: WebSocketWorkerStatusData = Field(..., description="Worker status data payload")
    timestamp: str | None = Field(None, description="ISO 8601 timestamp of the status change")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "worker_status",
                "data": {
                    "event_type": "worker.started",
                    "worker_name": "detection_worker",
                    "worker_type": "detection",
                    "timestamp": "2026-01-13T10:30:00Z",
                },
                "timestamp": "2026-01-13T10:30:00Z",
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
    ALERT_UPDATED = "alert.updated"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"
    ALERT_DISMISSED = "alert.dismissed"  # Alias for alert.resolved (backward compat)

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

    # Legacy job event types (underscore format - NEM-2505)
    # These map to the actual WebSocketJob*Message schemas used over the wire
    LEGACY_JOB_PROGRESS = "job_progress"  # Maps to WebSocketJobProgressMessage
    LEGACY_JOB_COMPLETED = "job_completed"  # Maps to WebSocketJobCompletedMessage
    LEGACY_JOB_FAILED = "job_failed"  # Maps to WebSocketJobFailedMessage


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
    WSEventType.ALERT_UPDATED: {
        "description": "Alert modified (metadata, channels, or properties updated)",
        "channel": "alerts",
        "payload_schema": {
            "alert_id": {"type": "string", "format": "uuid", "description": "Alert UUID"},
            "event_id": {"type": "integer", "description": "Associated event ID"},
            "rule_id": {
                "type": "string",
                "format": "uuid",
                "description": "Alert rule UUID (nullable)",
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Alert severity level",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "delivered", "acknowledged", "dismissed"],
                "description": "Alert status",
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "description": "Update timestamp",
            },
        },
        "example": {
            "alert_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 1,
            "rule_id": "550e8400-e29b-41d4-a716-446655440001",
            "severity": "high",
            "status": "pending",
            "updated_at": "2026-01-09T12:00:30.000Z",
        },
    },
    WSEventType.ALERT_ACKNOWLEDGED: {
        "description": "Alert acknowledged by user",
        "channel": "alerts",
        "payload_schema": {
            "alert_id": {"type": "string", "format": "uuid", "description": "Alert UUID"},
            "event_id": {"type": "integer", "description": "Associated event ID"},
            "acknowledged_at": {
                "type": "string",
                "format": "date-time",
                "description": "Acknowledgment timestamp",
            },
        },
        "example": {
            "alert_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 42,
            "acknowledged_at": "2026-01-09T12:05:00.000Z",
        },
    },
    WSEventType.ALERT_RESOLVED: {
        "description": "Alert resolved/dismissed by user",
        "channel": "alerts",
        "payload_schema": {
            "alert_id": {"type": "string", "format": "uuid", "description": "Alert UUID"},
            "event_id": {"type": "integer", "description": "Associated event ID"},
            "resolved_at": {
                "type": "string",
                "format": "date-time",
                "description": "Resolution timestamp",
            },
        },
        "example": {
            "alert_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 42,
            "resolved_at": "2026-01-09T12:05:00.000Z",
        },
    },
    WSEventType.ALERT_DISMISSED: {
        "description": "Alert dismissed by user (alias for alert.resolved)",
        "channel": "alerts",
        "payload_schema": {
            "alert_id": {"type": "string", "format": "uuid", "description": "Alert UUID"},
            "event_id": {"type": "integer", "description": "Associated event ID"},
            "dismissed_at": {
                "type": "string",
                "format": "date-time",
                "description": "Dismissal timestamp",
            },
            "reason": {"type": "string", "description": "Dismissal reason (optional)"},
        },
        "example": {
            "alert_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 42,
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
                "enum": [
                    "healthy",
                    "unhealthy",
                    "running",
                    "stopped",
                    "crashed",
                    "restarting",
                    "restart_failed",
                    "failed",
                ],
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


# Outgoing message schemas with sequence numbers (NEM-2019)


class WebSocketSequencedMessage(BaseModel):
    """Base schema for sequenced WebSocket messages.

    All outgoing WebSocket messages include a monotonically increasing
    sequence number per channel, enabling:
    - Frontend event ordering
    - Gap detection
    - Duplicate filtering
    - Resync requests

    Fields:
        type: Message type identifier
        sequence: Monotonically increasing sequence number (1+)
        timestamp: ISO 8601 timestamp when the message was created
        requires_ack: Whether the client should acknowledge receipt
        replay: Whether this is a replayed message from buffer
    """

    type: str = Field(
        ...,
        description="Message type identifier",
        min_length=1,
        max_length=50,
    )
    sequence: int = Field(
        ...,
        ge=1,
        description="Monotonically increasing sequence number (starting from 1)",
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp when the message was created",
    )
    requires_ack: bool = Field(
        default=False,
        description="Whether the client should acknowledge receipt of this message",
    )
    replay: bool = Field(
        default=False,
        description="Whether this is a replayed message from the buffer (on reconnection)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "event",
                "sequence": 42,
                "timestamp": "2025-12-23T12:00:00.000Z",
                "requires_ack": False,
                "replay": False,
            }
        }
    )


class WebSocketResyncRequest(BaseModel):
    """Request schema for frontend to request missed messages.

    When the frontend detects a gap in sequence numbers that exceeds
    the threshold, it sends a resync request to the backend to retrieve
    missed messages from the buffer.

    Fields:
        type: Must be "resync"
        last_sequence: Last sequence number successfully received (0 if none)
        channel: Channel to resync (e.g., "events", "system")
    """

    type: Literal["resync"] = Field(
        default="resync",
        description="Message type, must be 'resync'",
    )
    last_sequence: int = Field(
        ...,
        ge=0,
        description="Last sequence number successfully received (0 if none received)",
    )
    channel: str = Field(
        ...,
        description="Channel to resync (e.g., 'events', 'system')",
        min_length=1,
        max_length=50,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "resync",
                "last_sequence": 42,
                "channel": "events",
            }
        }
    )


class WebSocketAckMessage(BaseModel):
    """Acknowledgment message from frontend to backend.

    Sent by the frontend to acknowledge receipt of high-priority messages
    (events with risk_score >= 80 or risk_level == 'critical').

    Fields:
        type: Must be "ack"
        sequence: Sequence number being acknowledged
    """

    type: Literal["ack"] = Field(
        default="ack",
        description="Message type, must be 'ack'",
    )
    sequence: int = Field(
        ...,
        ge=1,
        description="Sequence number of the message being acknowledged",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "ack",
                "sequence": 42,
            }
        }
    )


# =============================================================================
# Infrastructure Alert Messages (Alertmanager Webhooks)
# =============================================================================


class WebSocketInfrastructureAlertSeverity(StrEnum):
    """Severity levels for infrastructure alerts from Alertmanager."""

    INFO = auto()
    WARNING = auto()
    HIGH = auto()
    CRITICAL = auto()


class WebSocketInfrastructureAlertStatus(StrEnum):
    """Status of infrastructure alerts."""

    FIRING = auto()
    RESOLVED = auto()


class WebSocketInfrastructureAlertData(BaseModel):
    """Data payload for infrastructure alert messages.

    Infrastructure alerts come from Prometheus/Alertmanager and represent
    system health issues (GPU memory, database connections, pipeline health, etc.)
    separate from AI-generated security alerts.
    """

    alertname: str = Field(..., description="Name of the alert (e.g., HSIGPUMemoryHigh)")
    status: WebSocketInfrastructureAlertStatus = Field(..., description="Alert status")
    severity: WebSocketInfrastructureAlertSeverity = Field(
        default=WebSocketInfrastructureAlertSeverity.INFO,
        description="Alert severity level",
    )
    component: str = Field(
        default="unknown", description="Infrastructure component (gpu, database, redis)"
    )
    summary: str = Field(default="", description="Brief alert summary")
    description: str = Field(default="", description="Detailed alert description")
    started_at: str | None = Field(None, description="ISO 8601 timestamp when alert started firing")
    fingerprint: str = Field(..., description="Unique alert fingerprint for deduplication")
    receiver: str = Field(default="default", description="Alertmanager receiver that matched")

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(
        cls, v: str | WebSocketInfrastructureAlertSeverity
    ) -> WebSocketInfrastructureAlertSeverity:
        """Validate and convert severity to enum."""
        if isinstance(v, WebSocketInfrastructureAlertSeverity):
            return v
        if isinstance(v, str):
            try:
                return WebSocketInfrastructureAlertSeverity(v.lower())
            except ValueError:
                # Default to INFO for unknown severities
                return WebSocketInfrastructureAlertSeverity.INFO
        return WebSocketInfrastructureAlertSeverity.INFO

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(
        cls, v: str | WebSocketInfrastructureAlertStatus
    ) -> WebSocketInfrastructureAlertStatus:
        """Validate and convert status to enum."""
        if isinstance(v, WebSocketInfrastructureAlertStatus):
            return v
        if isinstance(v, str):
            try:
                return WebSocketInfrastructureAlertStatus(v.lower())
            except ValueError:
                valid_values = [s.value for s in WebSocketInfrastructureAlertStatus]
                raise ValueError(f"Invalid status '{v}'. Must be one of: {valid_values}") from None
        raise ValueError(f"status must be a string or enum, got {type(v)}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alertname": "HSIGPUMemoryHigh",
                "status": "firing",
                "severity": "warning",
                "component": "gpu",
                "summary": "GPU memory usage is high",
                "description": "GPU memory usage is above 90% for 5 minutes",
                "started_at": "2026-01-17T12:22:56Z",
                "fingerprint": "abc123def456",  # pragma: allowlist secret
                "receiver": "critical-receiver",
            }
        }
    )


class WebSocketInfrastructureAlertMessage(BaseModel):
    """Complete infrastructure alert message envelope.

    This is the format for infrastructure alerts broadcast via WebSocket,
    originating from Prometheus Alertmanager webhooks.

    Format:
        {
            "type": "infrastructure_alert",
            "data": {
                "alertname": "HSIGPUMemoryHigh",
                "status": "firing",
                "severity": "warning",
                "component": "gpu",
                ...
            }
        }
    """

    type: Literal["infrastructure_alert"] = Field(
        default="infrastructure_alert",
        description="Message type, always 'infrastructure_alert'",
    )
    data: WebSocketInfrastructureAlertData = Field(
        ..., description="Infrastructure alert data payload"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "infrastructure_alert",
                "data": {
                    "alertname": "HSIGPUMemoryHigh",
                    "status": "firing",
                    "severity": "warning",
                    "component": "gpu",
                    "summary": "GPU memory usage is high",
                    "description": "GPU memory usage is above 90%",
                    "started_at": "2026-01-17T12:22:56Z",
                    "fingerprint": "abc123def456",  # pragma: allowlist secret
                    "receiver": "critical-receiver",
                },
            }
        }
    )


# =============================================================================
# Summary WebSocket Message Schemas (NEM-2893)
# =============================================================================


class WebSocketSummaryData(BaseModel):
    """Data payload for individual summary in summary_update messages.

    This schema defines the contract for summary data sent via WebSocket
    when new summaries are generated by the background job.

    Fields:
        id: Unique summary identifier
        content: LLM-generated narrative text (2-4 sentences)
        event_count: Number of high/critical events included
        window_start: ISO 8601 timestamp of the time window start
        window_end: ISO 8601 timestamp of the time window end
        generated_at: ISO 8601 timestamp when the LLM produced this summary
    """

    id: int = Field(..., description="Unique summary identifier")
    content: str = Field(..., description="LLM-generated narrative text (2-4 sentences)")
    event_count: int = Field(
        ..., ge=0, description="Number of high/critical events included in this summary"
    )
    window_start: str = Field(..., description="ISO 8601 timestamp of the time window start")
    window_end: str = Field(..., description="ISO 8601 timestamp of the time window end")
    generated_at: str = Field(
        ..., description="ISO 8601 timestamp when the LLM produced this summary"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "content": (
                    "Over the past hour, one critical event occurred at 2:15 PM "
                    "when an unrecognized person approached the front door. "
                    "The individual remained at the door for approximately 45 seconds "
                    "before leaving via the driveway."
                ),
                "event_count": 1,
                "window_start": "2026-01-18T14:00:00Z",
                "window_end": "2026-01-18T15:00:00Z",
                "generated_at": "2026-01-18T14:55:00Z",
            }
        }
    )


class WebSocketSummaryUpdateData(BaseModel):
    """Data payload for summary_update messages broadcast to WebSocket clients.

    Contains the latest hourly and/or daily summaries. Either field can be
    null if no new summary was generated for that time period.

    Fields:
        hourly: Latest hourly summary (past 60 minutes), null if none
        daily: Latest daily summary (since midnight), null if none
    """

    hourly: WebSocketSummaryData | None = Field(
        None, description="Latest hourly summary (past 60 minutes), null if none"
    )
    daily: WebSocketSummaryData | None = Field(
        None, description="Latest daily summary (since midnight), null if none"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hourly": {
                    "id": 1,
                    "content": (
                        "Over the past hour, one critical event occurred at 2:15 PM "
                        "when an unrecognized person approached the front door."
                    ),
                    "event_count": 1,
                    "window_start": "2026-01-18T14:00:00Z",
                    "window_end": "2026-01-18T15:00:00Z",
                    "generated_at": "2026-01-18T14:55:00Z",
                },
                "daily": {
                    "id": 2,
                    "content": (
                        "Today has seen minimal high-priority activity. "
                        "The only notable event was at 2:15 PM at the front door."
                    ),
                    "event_count": 1,
                    "window_start": "2026-01-18T00:00:00Z",
                    "window_end": "2026-01-18T15:00:00Z",
                    "generated_at": "2026-01-18T14:55:00Z",
                },
            }
        }
    )


class WebSocketSummaryUpdateMessage(BaseModel):
    """Complete summary_update message envelope sent to /ws/events clients.

    This is the canonical format for summary update messages broadcast via WebSocket.
    The message wraps summary data in a standard envelope with a type field.

    Broadcast when new summaries are generated by the background job (every 5 minutes).

    Format:
        {
            "type": "summary_update",
            "data": {
                "hourly": {
                    "id": 1,
                    "content": "Over the past hour...",
                    "event_count": 1,
                    "window_start": "2026-01-18T14:00:00Z",
                    "window_end": "2026-01-18T15:00:00Z",
                    "generated_at": "2026-01-18T14:55:00Z"
                },
                "daily": { ... }
            }
        }
    """

    type: Literal["summary_update"] = Field(
        default="summary_update",
        description="Message type, always 'summary_update' for summary update messages",
    )
    data: WebSocketSummaryUpdateData = Field(..., description="Summary update data payload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "summary_update",
                "data": {
                    "hourly": {
                        "id": 1,
                        "content": (
                            "Over the past hour, one critical event occurred at 2:15 PM "
                            "when an unrecognized person approached the front door."
                        ),
                        "event_count": 1,
                        "window_start": "2026-01-18T14:00:00Z",
                        "window_end": "2026-01-18T15:00:00Z",
                        "generated_at": "2026-01-18T14:55:00Z",
                    },
                    "daily": {
                        "id": 2,
                        "content": (
                            "Today has seen minimal high-priority activity. "
                            "The only notable event was at 2:15 PM at the front door."
                        ),
                        "event_count": 1,
                        "window_start": "2026-01-18T00:00:00Z",
                        "window_end": "2026-01-18T15:00:00Z",
                        "generated_at": "2026-01-18T14:55:00Z",
                    },
                },
            }
        }
    )


# =============================================================================
# Discriminated Unions for WebSocket Messages (NEM-3394)
# =============================================================================
#
# These discriminated unions use the 'type' field as a discriminator for
# automatic message routing. This provides 2-5x faster validation compared
# to generic Union types because Pydantic can immediately identify the
# correct model based on the discriminator value.
#
# Benefits:
# - Faster validation: O(1) model lookup instead of trying each model
# - Better error messages: Reports invalid discriminator values clearly
# - Type safety: IDE support for narrowing types based on discriminator


# -----------------------------------------------------------------------------
# Incoming Message Discriminated Union
# -----------------------------------------------------------------------------
# Messages sent from client to server

WebSocketIncomingMessage = Annotated[
    WebSocketPingMessage
    | WebSocketSubscribeMessage
    | WebSocketUnsubscribeMessage
    | WebSocketResyncRequest
    | WebSocketAckMessage,
    Discriminator("type"),
]
"""Discriminated union for all incoming WebSocket messages (client -> server).

Uses the 'type' field as a discriminator for automatic routing:
- "ping" -> WebSocketPingMessage
- "subscribe" -> WebSocketSubscribeMessage
- "unsubscribe" -> WebSocketUnsubscribeMessage
- "resync" -> WebSocketResyncRequest
- "ack" -> WebSocketAckMessage

Example:
    from pydantic import TypeAdapter

    adapter = TypeAdapter(WebSocketIncomingMessage)
    message = adapter.validate_python({"type": "ping"})
    # message is now a WebSocketPingMessage instance
"""


# -----------------------------------------------------------------------------
# Outgoing Message Discriminated Union
# -----------------------------------------------------------------------------
# Messages sent from server to client

WebSocketOutgoingMessage = Annotated[
    WebSocketPongResponse
    | WebSocketErrorResponse
    | WebSocketEventMessage
    | WebSocketServiceStatusMessage
    | WebSocketCameraStatusMessage
    | WebSocketSceneChangeMessage
    | WebSocketDetectionNewMessage
    | WebSocketDetectionBatchMessage
    | WebSocketBatchAnalysisStartedMessage
    | WebSocketBatchAnalysisCompletedMessage
    | WebSocketBatchAnalysisFailedMessage
    | WebSocketAlertCreatedMessage
    | WebSocketAlertAcknowledgedMessage
    | WebSocketAlertDismissedMessage
    | WebSocketAlertUpdatedMessage
    | WebSocketAlertDeletedMessage
    | WebSocketAlertResolvedMessage
    | WebSocketWorkerStatusMessage
    | WebSocketJobProgressMessage
    | WebSocketJobCompletedMessage
    | WebSocketJobFailedMessage
    | WebSocketInfrastructureAlertMessage
    | WebSocketSummaryUpdateMessage,
    Discriminator("type"),
]
"""Discriminated union for all outgoing WebSocket messages (server -> client).

Uses the 'type' field as a discriminator for automatic routing:
- "pong" -> WebSocketPongResponse
- "error" -> WebSocketErrorResponse
- "event" -> WebSocketEventMessage
- "service_status" -> WebSocketServiceStatusMessage
- "camera_status" -> WebSocketCameraStatusMessage
- "scene_change" -> WebSocketSceneChangeMessage
- "detection.new" -> WebSocketDetectionNewMessage
- "detection.batch" -> WebSocketDetectionBatchMessage
- "batch.analysis_started" -> WebSocketBatchAnalysisStartedMessage
- "batch.analysis_completed" -> WebSocketBatchAnalysisCompletedMessage
- "batch.analysis_failed" -> WebSocketBatchAnalysisFailedMessage
- "alert_created" -> WebSocketAlertCreatedMessage
- "alert_acknowledged" -> WebSocketAlertAcknowledgedMessage
- "alert_dismissed" -> WebSocketAlertDismissedMessage
- "alert_updated" -> WebSocketAlertUpdatedMessage
- "alert_deleted" -> WebSocketAlertDeletedMessage
- "alert_resolved" -> WebSocketAlertResolvedMessage
- "worker_status" -> WebSocketWorkerStatusMessage
- "job_progress" -> WebSocketJobProgressMessage
- "job_completed" -> WebSocketJobCompletedMessage
- "job_failed" -> WebSocketJobFailedMessage
- "infrastructure_alert" -> WebSocketInfrastructureAlertMessage
- "summary_update" -> WebSocketSummaryUpdateMessage

Example:
    from pydantic import TypeAdapter

    adapter = TypeAdapter(WebSocketOutgoingMessage)
    message = adapter.validate_python({"type": "pong"})
    # message is now a WebSocketPongResponse instance
"""
