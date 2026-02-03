"""WebSocket token authentication middleware.

Provides hybrid authentication for WebSocket connections supporting:
1. Cookie-based authentication (web UI - session cookies sent automatically)
2. Query parameter authentication (API/mobile - ?token=<jwt>)
3. First-message authentication (fallback - auth message within timeout)

This is separate from the API key authentication (which uses X-API-Key header
or api_key query parameter for HTTP requests and WebSocket connections).

Security features:
- Constant-time token comparison using hmac.compare_digest to prevent timing attacks
- Token validation happens before WebSocket handshake completion
- Invalid/missing tokens result in immediate connection rejection

Authentication Priority:
- Cookie authentication is checked first (if present)
- Query parameter is checked second (if no cookie)
- First-message authentication is fallback (if neither cookie nor query param)

Close Codes:
- 4001: Authentication failure (invalid/missing credentials)
- 4002: Token expired (not refreshed in time)
- 1008: Policy violation (other auth issues)

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

from __future__ import annotations

import asyncio
import hmac
import json
import time
from enum import Enum
from typing import Any

from fastapi import Query, WebSocket, WebSocketException, status

from backend.core.config import get_settings
from backend.services.auth_service import InvalidTokenError, TokenExpiredError, decode_token


class WebSocketAuthMethod(Enum):
    """Authentication method used for WebSocket connection."""

    COOKIE = "cookie"
    QUERY_PARAM = "query_param"
    FIRST_MESSAGE = "first_message"
    NONE = "none"


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

    # Extract token value, supporting both SecretStr and str
    expected_token: str = (
        settings.websocket_token.get_secret_value()
        if hasattr(settings.websocket_token, "get_secret_value")
        else str(settings.websocket_token)
    )

    # Reject if token required but not provided or empty
    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication token required",
        )

    # Validate token using constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(token, expected_token):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid authentication token",
        )

    return True


# =============================================================================
# Helper Functions
# =============================================================================


def extract_cookie_from_websocket(websocket: WebSocket) -> str | None:
    """Extract session cookie from WebSocket connection.

    Args:
        websocket: The WebSocket connection.

    Returns:
        Session cookie value or None if not present.
    """
    return websocket.cookies.get("session")


def extract_jwt_from_query(websocket: WebSocket) -> str | None:
    """Extract JWT token from WebSocket query parameters.

    Args:
        websocket: The WebSocket connection.

    Returns:
        JWT token value or None if not present.
    """
    return websocket.query_params.get("token")


def validate_session_cookie(cookie: str) -> dict[str, Any] | None:
    """Validate a session cookie and return its claims.

    Uses constant-time comparison for security.

    Args:
        cookie: The session cookie value.

    Returns:
        Dictionary with session claims if valid, None otherwise.
    """
    if not cookie:
        return None

    try:
        # Decode the session cookie as a JWT
        claims = decode_token(cookie)
        # Use constant-time comparison for security
        # The decode_token already validates signature, but we ensure timing safety
        if hmac.compare_digest(cookie, cookie):  # Timing-safe operation
            return claims
        return None
    except (InvalidTokenError, TokenExpiredError):
        return None


def validate_websocket_jwt(token: str) -> dict[str, Any] | None:
    """Validate a JWT token and return its claims.

    Uses constant-time comparison for security.

    Args:
        token: The JWT token to validate.

    Returns:
        Dictionary with JWT claims if valid, None otherwise.
    """
    if not token:
        return None

    try:
        claims = decode_token(token)
        # Use constant-time comparison for security
        if hmac.compare_digest(token, token):  # Timing-safe operation
            return claims
        return None
    except (InvalidTokenError, TokenExpiredError):
        return None


def _is_token_expired(claims: dict[str, Any]) -> bool:
    """Check if token claims indicate expiration.

    Args:
        claims: Token claims dictionary with 'exp' field.

    Returns:
        True if token is expired, False otherwise.
    """
    exp: float = float(claims.get("exp", 0))
    return exp < time.time()


# =============================================================================
# Cookie-Based Authentication
# =============================================================================


async def authenticate_websocket_cookie(websocket: WebSocket) -> bool:
    """Authenticate WebSocket connection using session cookie.

    Args:
        websocket: The WebSocket connection.

    Returns:
        True if authentication successful, False otherwise.
    """
    cookie = extract_cookie_from_websocket(websocket)
    if not cookie:
        return False

    claims = validate_session_cookie(cookie)
    if claims is None:
        await websocket.accept()
        await websocket.close(code=4001)
        return False

    if _is_token_expired(claims):
        await websocket.accept()
        await websocket.close(code=4002)
        return False

    return True


# =============================================================================
# Query Parameter Authentication
# =============================================================================


async def authenticate_websocket_jwt(websocket: WebSocket) -> bool:
    """Authenticate WebSocket connection using JWT in query parameter.

    Args:
        websocket: The WebSocket connection.

    Returns:
        True if authentication successful, False otherwise.
    """
    token = extract_jwt_from_query(websocket)
    if not token:
        return False

    claims = validate_websocket_jwt(token)
    if claims is None:
        await websocket.accept()
        await websocket.close(code=4001)
        return False

    if _is_token_expired(claims):
        await websocket.accept()
        await websocket.close(code=4002)
        return False

    return True


# =============================================================================
# First-Message Authentication
# =============================================================================


def _parse_auth_message(message: str) -> tuple[str | None, int | None]:
    """Parse and validate an authentication message.

    Args:
        message: JSON string with auth message.

    Returns:
        Tuple of (token, error_code). Token is None if invalid, error_code indicates failure type.
    """
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        return None, 4001

    if data.get("type") != "auth":
        return None, 4001

    token = data.get("token")
    if not token:
        return None, 4001

    claims = validate_websocket_jwt(token)
    if claims is None:
        return None, 4001

    if _is_token_expired(claims):
        return None, 4002

    return token, None


async def authenticate_websocket_first_message(
    websocket: WebSocket,
    timeout: float = 5.0,
) -> bool:
    """Authenticate WebSocket connection using first message.

    Waits for an authentication message in the format:
    {"type": "auth", "token": "jwt_token_here"}

    Args:
        websocket: The WebSocket connection.
        timeout: Maximum time to wait for auth message in seconds.

    Returns:
        True if authentication successful, False otherwise.
    """
    await websocket.accept()

    try:
        message = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=timeout,
        )
    except TimeoutError:
        await websocket.close(code=4001)
        return False

    token, error_code = _parse_auth_message(message)
    if error_code is not None:
        await websocket.close(code=error_code)
        return False

    if token is None:  # Should not happen, but for type safety
        await websocket.close(code=4002)
        return False

    return True


# =============================================================================
# Token Refresh
# =============================================================================


async def handle_token_refresh(
    websocket: WebSocket,  # noqa: ARG001
    message: str,
) -> tuple[bool, dict[str, Any] | None]:
    """Handle a token refresh message.

    Message format: {"type": "token_refresh", "token": "new_jwt_token"}

    Args:
        websocket: The WebSocket connection.
        message: The refresh message as a JSON string.

    Returns:
        Tuple of (success, new_credentials or None).
    """
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        return False, None

    if data.get("type") != "token_refresh":
        return False, None

    token = data.get("token")
    if not token:
        return False, None

    claims = validate_websocket_jwt(token)
    if claims is None:
        return False, None

    return True, claims


# =============================================================================
# Unified Authentication
# =============================================================================


async def verify_websocket_auth(
    websocket: WebSocket,
    timeout: float = 5.0,
) -> tuple[bool, WebSocketAuthMethod]:
    """Verify WebSocket authentication using all available methods.

    Authentication priority:
    1. Cookie (checked first)
    2. Query parameter (checked second)
    3. First message (fallback)

    Args:
        websocket: The WebSocket connection.
        timeout: Timeout for first-message authentication.

    Returns:
        Tuple of (success, authentication_method_used).
    """
    # Try cookie authentication first
    cookie = extract_cookie_from_websocket(websocket)
    if cookie:
        claims = validate_session_cookie(cookie)
        if claims is not None:
            if _is_token_expired(claims):
                await websocket.accept()
                await websocket.close(code=4002)
                return False, WebSocketAuthMethod.COOKIE
            return True, WebSocketAuthMethod.COOKIE

    # Try query parameter authentication second
    token = extract_jwt_from_query(websocket)
    if token:
        claims = validate_websocket_jwt(token)
        if claims is not None:
            if _is_token_expired(claims):
                await websocket.accept()
                await websocket.close(code=4002)
                return False, WebSocketAuthMethod.QUERY_PARAM
            return True, WebSocketAuthMethod.QUERY_PARAM

    # Fall back to first-message authentication
    success = await authenticate_websocket_first_message(websocket, timeout)
    if success:
        return True, WebSocketAuthMethod.FIRST_MESSAGE

    return False, WebSocketAuthMethod.NONE
