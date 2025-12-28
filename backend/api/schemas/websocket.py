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

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WebSocketMessageType(str, Enum):
    """Valid WebSocket message types."""

    PING = "ping"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


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
        camera_id: UUID of the camera that captured the event
        risk_score: Risk assessment score (0-100)
        risk_level: Risk classification ("low", "medium", "high", "critical")
        summary: Human-readable description of the event
        started_at: ISO 8601 timestamp when the event started (nullable)
    """

    id: int = Field(..., description="Unique event identifier")
    event_id: int = Field(..., description="Legacy alias for id (backward compatibility)")
    batch_id: str = Field(..., description="Detection batch identifier")
    camera_id: str = Field(..., description="UUID of the camera that captured the event")
    risk_score: int = Field(..., ge=0, le=100, description="Risk assessment score (0-100)")
    risk_level: str = Field(
        ..., description='Risk classification ("low", "medium", "high", "critical")'
    )
    summary: str = Field(..., description="Human-readable description of the event")
    started_at: str | None = Field(None, description="ISO 8601 timestamp when the event started")

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
                    "started_at": "2025-12-23T12:00:00",
                },
            }
        }
    )
