"""WebSocket token authentication middleware.

Provides optional token-based authentication for WebSocket connections.
When WEBSOCKET_TOKEN is configured, clients must provide the token as a
query parameter to establish a connection.

This is separate from the API key authentication (which uses X-API-Key header
or api_key query parameter for HTTP requests and WebSocket connections).

Security features:
- Constant-time token comparison using hmac.compare_digest to prevent timing attacks
- Token validation happens before WebSocket handshake completion
- Invalid/missing tokens result in immediate connection rejection (code 1008)

Usage:
    # In WebSocket route:
    @router.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        _: bool = Depends(validate_websocket_token),
    ):
        # Token has been validated at this point
        ...

Configuration:
    Set WEBSOCKET_TOKEN environment variable to enable token authentication.
    Leave unset or empty to disable (single-user mode).

    Example .env:
        WEBSOCKET_TOKEN=your-secret-token-here
"""

import hmac

from fastapi import Query, WebSocket, WebSocketException, status

from backend.core.config import get_settings


async def validate_websocket_token(
    websocket: WebSocket,  # noqa: ARG001  # Required for FastAPI dependency signature
    token: str | None = Query(None, alias="token"),
) -> bool:
    """Validate WebSocket connection token if configured.

    When WEBSOCKET_TOKEN is set in settings, connections must include
    the token as a query parameter: ws://host/ws?token=<token>

    This function can be used as a FastAPI dependency on WebSocket endpoints.

    Args:
        websocket: The WebSocket connection being validated.
        token: The token provided via query parameter (?token=<value>).

    Returns:
        True if validation passes (token matches or no token is configured).

    Raises:
        WebSocketException: If token is required but invalid or missing.
            Uses code 1008 (Policy Violation) per WebSocket protocol.
    """
    settings = get_settings()

    # Skip validation if no token is configured (single-user mode)
    # Treat empty string as disabled
    if not settings.websocket_token:
        return True

    # Reject if token required but not provided or empty
    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication token required",
        )

    # Validate token using constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(token, settings.websocket_token):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid authentication token",
        )

    return True
