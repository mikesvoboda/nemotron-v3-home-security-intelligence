"""API schemas for request/response validation."""

from .camera import CameraCreate, CameraListResponse, CameraResponse, CameraUpdate
from .websocket import (
    WebSocketErrorCode,
    WebSocketErrorResponse,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketPingMessage,
    WebSocketPongResponse,
    WebSocketSubscribeMessage,
    WebSocketUnsubscribeMessage,
)

__all__ = [
    "CameraCreate",
    "CameraListResponse",
    "CameraResponse",
    "CameraUpdate",
    # WebSocket schemas
    "WebSocketErrorCode",
    "WebSocketErrorResponse",
    "WebSocketMessage",
    "WebSocketMessageType",
    "WebSocketPingMessage",
    "WebSocketPongResponse",
    "WebSocketSubscribeMessage",
    "WebSocketUnsubscribeMessage",
]
