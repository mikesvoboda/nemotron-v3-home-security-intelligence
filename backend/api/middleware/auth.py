"""API key authentication middleware."""

import hashlib
import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, WebSocket, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.api.middleware.websocket_auth import (
    WebSocketAuthMethod,
    verify_websocket_auth,
)
from backend.core import get_settings
from backend.core.logging import get_logger, mask_ip

logger = get_logger(__name__)


def _hash_key(key: str) -> str:
    """Hash API key using SHA-256.

    Args:
        key: Plain text API key

    Returns:
        SHA-256 hash of the key
    """
    return hashlib.sha256(key.encode()).hexdigest()


def _get_valid_key_hashes() -> set[str]:
    """Get the set of valid API key hashes from settings.

    Returns:
        Set of SHA-256 hashes of valid API keys
    """
    settings = get_settings()
    # Support both SecretStr and str for api_keys
    hashes = set()
    for key in settings.api_keys:
        key_value = key.get_secret_value() if hasattr(key, "get_secret_value") else key
        hashes.add(_hash_key(str(key_value)))
    return hashes


def _validate_key_hash_constant_time(key_hash: str, valid_hashes: set[str]) -> bool:
    """Validate API key hash using constant-time comparison.

    Uses hmac.compare_digest to prevent timing attacks (OWASP A07:2021).
    Compares the key hash against all valid hashes using constant-time
    comparison to avoid leaking information about which keys are valid.

    Args:
        key_hash: SHA-256 hash of the API key to validate
        valid_hashes: Set of valid API key hashes

    Returns:
        True if the key hash matches any valid hash, False otherwise
    """
    return any(hmac.compare_digest(key_hash, valid_hash) for valid_hash in valid_hashes)


async def validate_websocket_api_key(websocket: WebSocket) -> bool:
    """Validate API key for WebSocket connections.

    Checks if API key authentication is enabled and validates the key
    provided via query parameter or Sec-WebSocket-Protocol header.

    Args:
        websocket: WebSocket connection to validate

    Returns:
        True if authentication is disabled or key is valid, False otherwise
    """
    settings = get_settings()

    # Skip authentication if disabled
    if not settings.api_key_enabled:
        return True

    # Extract API key from query parameter
    api_key = websocket.query_params.get("api_key")

    # Fall back to Sec-WebSocket-Protocol header
    if not api_key:
        # The Sec-WebSocket-Protocol header can contain multiple protocols
        # We look for one that starts with "api-key." followed by the key
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        for protocol in protocols.split(","):
            stripped_protocol = protocol.strip()
            if stripped_protocol.startswith("api-key."):
                api_key = stripped_protocol[8:]  # Extract key after "api-key."
                break

    # No API key provided
    if not api_key:
        logger.warning(
            "WebSocket authentication attempt without API key",
            extra={
                "path": str(websocket.url.path),
                "client_ip": mask_ip(websocket.client.host if websocket.client else "unknown"),
                "security_event": True,
                "event_type": "ws_auth_missing_key",
            },
        )
        return False

    # Validate the API key using constant-time comparison (OWASP A07:2021)
    key_hash = _hash_key(api_key)
    valid_hashes = _get_valid_key_hashes()
    is_valid = _validate_key_hash_constant_time(key_hash, valid_hashes)

    if not is_valid:
        logger.warning(
            "WebSocket authentication attempt with invalid API key",
            extra={
                "path": str(websocket.url.path),
                "client_ip": mask_ip(websocket.client.host if websocket.client else "unknown"),
                "security_event": True,
                "event_type": "ws_auth_invalid_key",
            },
        )

    return is_valid


async def authenticate_websocket(websocket: WebSocket) -> bool:
    """Authenticate a WebSocket connection using hybrid authentication.

    Supports multiple authentication methods in priority order:
    1. Cookie authentication (web UI clients)
    2. JWT token in query parameter (API/mobile clients)
    3. API key (existing functionality for backward compatibility)

    If authentication fails, the connection is first accepted and then closed
    with an appropriate code. This is required because in the WebSocket protocol,
    you cannot send a close frame without first completing the handshake.

    Note: Attempting to close without accepting would result in the HTTP layer
    returning a 403 Forbidden, which is not a proper WebSocket close.

    Close codes:
    - 4001: Authentication failure (invalid/missing credentials)
    - 4002: Token expired
    - 1008: Policy violation (API key failure)

    IMPORTANT: This function does NOT accept the WebSocket on success.
    The caller (route) is responsible for accepting via broadcaster.connect()
    or websocket.accept().

    Args:
        websocket: WebSocket connection to authenticate

    Returns:
        True if authenticated successfully, False if connection was rejected
    """
    # Check if hybrid auth credentials are present (cookie or JWT token)
    has_cookie = websocket.cookies.get("session") is not None
    has_jwt_token = websocket.query_params.get("token") is not None

    # Try hybrid auth first if credentials are present
    if has_cookie or has_jwt_token:
        success, auth_method = await verify_websocket_auth(websocket, timeout=5.0)
        if success:
            logger.info(
                f"WebSocket authenticated via {auth_method.value}",
                extra={
                    "path": str(websocket.url.path),
                    "auth_method": auth_method.value,
                },
            )
            # Do NOT accept here - let the route/broadcaster handle it
            return True
        # verify_websocket_auth already closed the connection on failure
        if auth_method != WebSocketAuthMethod.NONE:
            return False

    # Fall back to API key authentication
    if not await validate_websocket_api_key(websocket):
        # Must accept the WebSocket before we can close it with a proper close frame.
        # Without accept(), calling close() results in HTTP 403 during handshake.
        await websocket.accept()
        # Use 4001 (authentication failure) for consistency with hybrid auth
        await websocket.close(code=4001)
        return False

    # API key auth succeeded - do NOT accept here, let the caller handle it
    return True


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce API key authentication."""

    def __init__(self, app: ASGIApp, valid_key_hashes: set[str] | None = None):
        """Initialize authentication middleware.

        Args:
            app: FastAPI application
            valid_key_hashes: Set of valid API key hashes (SHA-256). If None, loads from settings.
        """
        super().__init__(app)
        self.valid_key_hashes = valid_key_hashes or self._load_key_hashes()

    def _load_key_hashes(self) -> set[str]:
        """Load and hash API keys from settings."""
        settings = get_settings()
        # Support both SecretStr and str for api_keys
        hashes = set()
        for key in settings.api_keys:
            key_value = key.get_secret_value() if hasattr(key, "get_secret_value") else key
            hashes.add(self._hash_key(str(key_value)))
        return hashes

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash API key using SHA-256.

        Args:
            key: Plain text API key

        Returns:
            SHA-256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()

    def _validate_key_hash(self, key_hash: str) -> bool:
        """Validate API key hash using constant-time comparison.

        Uses hmac.compare_digest to prevent timing attacks (OWASP A07:2021).
        Compares the key hash against all valid hashes using constant-time
        comparison to avoid leaking information about which keys are valid.

        Args:
            key_hash: SHA-256 hash of the API key to validate

        Returns:
            True if the key hash matches any valid hash, False otherwise
        """
        return any(
            hmac.compare_digest(key_hash, valid_hash) for valid_hash in self.valid_key_hashes
        )

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from authentication.

        SECURITY RATIONALE FOR EXEMPT PATHS:

        Health Check Endpoints (required for container orchestration):
        - /               : Basic status check for load balancers
        - /health         : Canonical liveness probe (Docker/K8s HEALTHCHECK)
        - /ready          : Canonical readiness probe (K8s readiness)
        - /api/system/health       : Detailed health check (includes AI service status)
        - /api/system/health/ready : Detailed readiness probe with service breakdown

        Prometheus Metrics (required for monitoring):
        - /api/metrics    : Prometheus scraping endpoint
          NOTE: Consider restricting to internal network only in production

        API Documentation (development convenience):
        - /docs           : Swagger UI
        - /redoc          : ReDoc documentation
        - /openapi.json   : OpenAPI schema

        Media Endpoints (static content accessed by browsers):
        - /api/media/*    : Camera media and thumbnails
        - /api/detections/{id}/image : Detection thumbnail images
        - /api/detections/{id}/video : Detection video streams
        - /api/detections/{id}/video/thumbnail : Video thumbnail frames
        - /api/cameras/{id}/snapshot : Latest camera snapshot

        Security controls for media endpoints:
        1. Path traversal protection (rejects ".." and absolute paths)
        2. File type allowlist (only images and videos)
        3. Base directory validation (prevents symlink escapes)
        4. Rate limiting (MEDIA tier - configurable requests/minute)
        5. Detection IDs require prior knowledge (not enumerable)

        Args:
            path: Request path

        Returns:
            True if path should bypass authentication
        """
        # Health check endpoints - required for container orchestration
        exempt_paths = [
            "/",
            "/health",  # Canonical liveness probe
            "/ready",  # Canonical readiness probe
            "/api/system/health",  # Detailed health check (includes AI services)
            "/api/system/health/ready",  # Detailed readiness probe
            "/api/metrics",  # Prometheus scraping endpoint
            "/docs",
            "/redoc",
            "/openapi.json",
            # Auth endpoints (NEM-5312: Phase 2 API Protection)
            # These are exempt because:
            # 1. Setup status must be checkable without auth
            # 2. Registration must work when no users exist
            # 3. Login endpoint needs to be accessible to authenticate
            "/api/auth/setup-status",
            "/api/auth/register",
            "/api/auth/login",
        ]

        # Exempt prefix paths (for dynamic routes)
        exempt_prefixes = [
            "/docs",
            "/redoc",
            # Media endpoints are exempt because they:
            # 1. Are accessed directly by browsers via <img>/<video> tags
            # 2. Have their own security (path traversal protection, file type allowlist, rate limiting)
            # 3. Would require api_key in every image URL otherwise
            "/api/media/",
        ]

        if path in exempt_paths:
            return True

        for prefix in exempt_prefixes:
            if path.startswith(prefix):
                return True

        # Exempt detection media endpoints (images, videos, thumbnails)
        # These have rate limiting and require knowing detection IDs
        # Pattern: /api/detections/{id}/image, /api/detections/{id}/video, /api/detections/{id}/video/thumbnail
        if path.startswith("/api/detections/") and ("/image" in path or "/video" in path):
            return True

        # Exempt camera snapshot endpoints
        # These have rate limiting and path traversal protection
        # Pattern: /api/cameras/{id}/snapshot
        return path.startswith("/api/cameras/") and path.endswith("/snapshot")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and validate API key if authentication is enabled.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint

        Returns:
            HTTP response
        """
        settings = get_settings()

        # Skip authentication if disabled
        if not settings.api_key_enabled:
            return await call_next(request)

        # Skip authentication for exempt paths
        if self._is_exempt_path(request.url.path):
            return await call_next(request)

        # Extract API key from header or query parameter
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            api_key = request.query_params.get("api_key")

        # Reject if no API key provided
        if not api_key:
            logger.warning(
                "Authentication attempt without API key",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": mask_ip(request.client.host if request.client else "unknown"),
                    "security_event": True,
                    "event_type": "auth_missing_key",
                },
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "API key required. Provide via X-API-Key header or api_key query parameter."
                },
            )

        # Hash and validate API key using constant-time comparison (OWASP A07:2021)
        key_hash = self._hash_key(api_key)
        if not self._validate_key_hash(key_hash):
            logger.warning(
                "Authentication attempt with invalid API key",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": mask_ip(request.client.host if request.client else "unknown"),
                    "security_event": True,
                    "event_type": "auth_invalid_key",
                },
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid API key"},
            )

        # API key is valid, proceed with request
        return await call_next(request)
