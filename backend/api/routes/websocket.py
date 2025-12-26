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
"""

import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from backend.api.middleware import authenticate_websocket
from backend.core.redis import RedisClient, get_redis
from backend.services.event_broadcaster import get_broadcaster
from backend.services.system_broadcaster import get_system_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


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
               "camera_id": "...",
               "camera_name": "...",
               "risk_score": 75,
               "risk_level": "high",
               "summary": "...",
               "timestamp": "2025-12-23T12:00:00Z"
           }
       }
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
    # Authenticate WebSocket connection before accepting
    if not await authenticate_websocket(websocket):
        logger.warning("WebSocket connection rejected: authentication failed for /ws/events")
        return

    broadcaster = await get_broadcaster(redis)

    try:
        # Register the WebSocket connection
        await broadcaster.connect(websocket)
        logger.info("WebSocket client connected to /ws/events")

        # Keep the connection alive by waiting for messages
        # In this case, we don't expect clients to send messages, but we need
        # to keep the connection open to send events to them
        while True:
            try:
                # Wait for any message from the client (mostly keep-alive)
                # We don't process client messages, just keep the connection alive
                data = await websocket.receive_text()
                logger.debug(f"Received message from WebSocket client: {data}")

                # Optionally send a pong response for keep-alive
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')

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
async def websocket_system_status(websocket: WebSocket) -> None:
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
    # Authenticate WebSocket connection before accepting
    if not await authenticate_websocket(websocket):
        logger.warning("WebSocket connection rejected: authentication failed for /ws/system")
        return

    broadcaster = get_system_broadcaster()

    try:
        # Add connection to broadcaster
        await broadcaster.connect(websocket)
        logger.info("WebSocket client connected to /ws/system")

        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for any message from the client (mostly keep-alive)
                # We don't process client messages, just keep the connection alive
                data = await websocket.receive_text()
                logger.debug(f"Received message from WebSocket client: {data}")

                # Optionally send a pong response for keep-alive
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')

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
