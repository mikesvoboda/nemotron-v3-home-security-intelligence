"""WebSocket routes for real-time event streaming.

This module provides WebSocket endpoints for clients to receive real-time
security event notifications as they occur.

WebSocket Authentication:
    When API key authentication is enabled (api_key_enabled=true in settings),
    WebSocket connections must provide a valid API key via one of:
    1. Query parameter: ws://host/ws/events?api_key=YOUR_KEY
    2. Sec-WebSocket-Protocol header: "api-key.YOUR_KEY"

    Connections without a valid API key will be rejected with code 1008
    (Policy Violation).

WebSocket Message Validation:
    All incoming messages are validated for proper JSON structure and schema.
    Invalid messages receive an error response with details about the issue.
    Supported message types: ping, subscribe, unsubscribe.

WebSocket Idle Timeout:
    Connections that do not send any messages within the configured idle
    timeout (default: 300 seconds) will be automatically closed. Clients
    should send periodic ping messages to keep the connection alive.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from pydantic import ValidationError

from backend.api.middleware import authenticate_websocket, check_websocket_rate_limit
from backend.api.schemas.websocket import (
    WebSocketErrorCode,
    WebSocketErrorResponse,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketPongResponse,
)
from backend.core.config import get_settings
from backend.core.redis import RedisClient, get_redis
from backend.services.event_broadcaster import get_broadcaster
from backend.services.system_broadcaster import get_system_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def validate_websocket_message(
    websocket: WebSocket, raw_data: str
) -> WebSocketMessage | None:
    """Validate an incoming WebSocket message.

    Attempts to parse the raw data as JSON and validate it against the
    WebSocketMessage schema. If validation fails, sends an error response
    to the client and returns None.

    Args:
        websocket: The WebSocket connection to send error responses to.
        raw_data: The raw string data received from the client.

    Returns:
        A validated WebSocketMessage if successful, None if validation failed.
    """
    # Try to parse as JSON
    try:
        message_data: dict[str, Any] = json.loads(raw_data)
    except json.JSONDecodeError as e:
        logger.warning(f"WebSocket received invalid JSON: {e}")
        error_response = WebSocketErrorResponse(
            error=WebSocketErrorCode.INVALID_JSON,
            message="Message must be valid JSON",
            details={"raw_data_preview": raw_data[:100] if raw_data else None},
        )
        await websocket.send_text(error_response.model_dump_json())
        return None

    # Validate message structure
    try:
        message = WebSocketMessage.model_validate(message_data)
        return message
    except ValidationError as e:
        logger.warning(f"WebSocket received invalid message format: {e}")
        error_response = WebSocketErrorResponse(
            error=WebSocketErrorCode.INVALID_MESSAGE_FORMAT,
            message="Message does not match expected schema",
            details={"validation_errors": e.errors()},
        )
        await websocket.send_text(error_response.model_dump_json())
        return None


async def handle_validated_message(websocket: WebSocket, message: WebSocketMessage) -> None:
    """Handle a validated WebSocket message.

    Dispatches the message to the appropriate handler based on its type.
    Unknown message types receive an error response.

    Args:
        websocket: The WebSocket connection.
        message: The validated WebSocket message.
    """
    message_type = message.type.lower()

    if message_type == WebSocketMessageType.PING.value:
        # Respond with pong
        pong_response = WebSocketPongResponse()
        await websocket.send_text(pong_response.model_dump_json())
        logger.debug("Sent pong response to WebSocket client")

    elif message_type == WebSocketMessageType.SUBSCRIBE.value:
        # Future: handle subscription
        logger.debug(f"Received subscribe message: {message.data}")
        # For now, just acknowledge (subscription logic TBD)

    elif message_type == WebSocketMessageType.UNSUBSCRIBE.value:
        # Future: handle unsubscription
        logger.debug(f"Received unsubscribe message: {message.data}")
        # For now, just acknowledge (unsubscription logic TBD)

    else:
        # Unknown message type
        logger.warning(f"WebSocket received unknown message type: {message_type}")
        error_response = WebSocketErrorResponse(
            error=WebSocketErrorCode.UNKNOWN_MESSAGE_TYPE,
            message=f"Unknown message type: {message_type}",
            details={"supported_types": [t.value for t in WebSocketMessageType]},
        )
        await websocket.send_text(error_response.model_dump_json())


@router.websocket("/ws/events")
async def websocket_events_endpoint(
    websocket: WebSocket,
    redis: RedisClient = Depends(get_redis),
) -> None:
    """WebSocket endpoint for streaming security events in real-time.

    Clients connect to this endpoint to receive real-time notifications
    about security events as they are detected and analyzed.

    Authentication:
        When API key authentication is enabled, provide the key via:
        - Query parameter: ws://host/ws/events?api_key=YOUR_KEY
        - Sec-WebSocket-Protocol header: "api-key.YOUR_KEY"

    The connection lifecycle:
    1. Client connects and is authenticated (if auth enabled)
    2. Client is registered with the broadcaster
    3. Client receives events as JSON messages in the format:
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

       Field descriptions:
       - id: Unique event identifier
       - event_id: Legacy alias for id (for backward compatibility)
       - batch_id: Detection batch identifier
       - camera_id: UUID of the camera that captured the event
       - risk_score: Risk assessment score (0-100)
       - risk_level: Risk classification ("low", "medium", "high", "critical")
       - summary: Human-readable description of the event
       - started_at: ISO 8601 timestamp when the event started

    4. Connection is maintained until client disconnects

    Args:
        websocket: WebSocket connection instance
        redis: Redis client for pub/sub communication

    Example JavaScript client:
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/ws/events?api_key=YOUR_KEY');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('New event:', data);
        };
        ```
    """
    # Check rate limit before accepting connection
    if not await check_websocket_rate_limit(websocket, redis):
        logger.warning("WebSocket connection rejected: rate limit exceeded for /ws/events")
        await websocket.close(code=1008)  # Policy Violation
        return

    # Authenticate WebSocket connection before accepting
    if not await authenticate_websocket(websocket):
        logger.warning("WebSocket connection rejected: authentication failed for /ws/events")
        return

    broadcaster = await get_broadcaster(redis)
    settings = get_settings()
    idle_timeout = settings.websocket_idle_timeout_seconds

    try:
        # Register the WebSocket connection
        await broadcaster.connect(websocket)
        logger.info("WebSocket client connected to /ws/events")

        # Keep the connection alive by waiting for messages
        # Clients can send ping messages for keep-alive and other commands
        while True:
            try:
                # Wait for any message from the client with idle timeout
                # Connections that don't send messages within the timeout are closed
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=idle_timeout,
                )
                logger.debug(f"Received message from WebSocket client: {data}")

                # Support legacy plain "ping" string for backward compatibility
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')
                    continue

                # Validate and handle JSON messages
                message = await validate_websocket_message(websocket, data)
                if message is not None:
                    await handle_validated_message(websocket, message)

            except TimeoutError:
                logger.info(f"WebSocket idle timeout ({idle_timeout}s) - closing connection")
                await websocket.close(code=1000, reason="Idle timeout")
                break
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                # Check if the connection is still open
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.info("WebSocket client disconnected")
                    break
                logger.error(f"Error receiving WebSocket message: {e}")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected during handshake")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Ensure the connection is properly cleaned up
        await broadcaster.disconnect(websocket)
        logger.info("WebSocket connection cleaned up")


@router.websocket("/ws/system")
async def websocket_system_status(
    websocket: WebSocket,
    redis: RedisClient = Depends(get_redis),
) -> None:
    """WebSocket endpoint for real-time system status updates.

    Authentication:
        When API key authentication is enabled, provide the key via:
        - Query parameter: ws://host/ws/system?api_key=YOUR_KEY
        - Sec-WebSocket-Protocol header: "api-key.YOUR_KEY"

    Sends periodic system status updates including:
    - GPU utilization and memory stats
    - Active camera counts
    - Processing queue status
    - Overall system health

    Message format:
    ```json
    {
        "type": "system_status",
        "data": {
            "gpu": {
                "utilization": 45.5,
                "memory_used": 8192,
                "memory_total": 24576,
                "temperature": 65.0,
                "inference_fps": 30.5
            },
            "cameras": {
                "active": 4,
                "total": 6
            },
            "queue": {
                "pending": 2,
                "processing": 1
            },
            "health": "healthy"
        },
        "timestamp": "2025-12-23T10:30:00.000Z"
    }
    ```

    Args:
        websocket: WebSocket connection
        redis: Redis client for rate limiting

    Notes:
        - Status updates are sent every 5 seconds
        - Connection will remain open until client disconnects
        - Failed sends will automatically disconnect the client

    Example JavaScript client:
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/ws/system?api_key=YOUR_KEY');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('System status:', data);
        };
        ```
    """
    # Check rate limit before accepting connection
    if not await check_websocket_rate_limit(websocket, redis):
        logger.warning("WebSocket connection rejected: rate limit exceeded for /ws/system")
        await websocket.close(code=1008)  # Policy Violation
        return

    # Authenticate WebSocket connection before accepting
    if not await authenticate_websocket(websocket):
        logger.warning("WebSocket connection rejected: authentication failed for /ws/system")
        return

    broadcaster = get_system_broadcaster()
    settings = get_settings()
    idle_timeout = settings.websocket_idle_timeout_seconds

    try:
        # Add connection to broadcaster
        await broadcaster.connect(websocket)
        logger.info("WebSocket client connected to /ws/system")

        # Keep connection alive and handle messages
        # Clients can send ping messages for keep-alive and other commands
        while True:
            try:
                # Wait for any message from the client with idle timeout
                # Connections that don't send messages within the timeout are closed
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=idle_timeout,
                )
                logger.debug(f"Received message from WebSocket client: {data}")

                # Support legacy plain "ping" string for backward compatibility
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')
                    continue

                # Validate and handle JSON messages
                message = await validate_websocket_message(websocket, data)
                if message is not None:
                    await handle_validated_message(websocket, message)

            except TimeoutError:
                logger.info(f"WebSocket idle timeout ({idle_timeout}s) - closing connection")
                await websocket.close(code=1000, reason="Idle timeout")
                break
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                # Check if the connection is still open
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.info("WebSocket client disconnected")
                    break
                logger.error(f"Error receiving WebSocket message: {e}")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected during handshake")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Ensure the connection is properly cleaned up
        await broadcaster.disconnect(websocket)
        logger.info("WebSocket connection cleaned up")
