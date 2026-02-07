"""Setup guard middleware for protecting API during initial setup.

This middleware returns 503 Service Unavailable for all endpoints except
a whitelist when no users exist in the system. This ensures the application
cannot be used until initial setup (first admin user registration) is complete.

NEM-5312: Phase 2 API Protection implementation.

Whitelist (endpoints allowed during setup):
- GET /api/auth/setup-status - Check if setup is required
- POST /api/auth/register - Register first admin user
- GET /health - Liveness probe
- GET /ready - Readiness probe
- GET / - Root health check
- GET /docs - API documentation
- GET /redoc - API documentation
- GET /openapi.json - OpenAPI schema
- GET /api/system/health/* - System health endpoints (websocket, ready, etc.)
- GET /api/system/gpu - GPU metrics for Prometheus
- GET /api/system/stats - System stats for Prometheus
- GET /api/system/telemetry - Pipeline telemetry for Prometheus
- GET /api/metrics - Native Prometheus metrics endpoint
- /ws/* - WebSocket endpoints (events, system status, detections)
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.core.logging import get_logger

logger = get_logger(__name__)

# TTL for caching the user-exists check to reduce sequential scans on the users table.
# Before setup is complete, the DB is queried at most once per this interval.
_SETUP_CHECK_TTL_SECONDS = 60.0

# Paths that are always allowed, even when setup is required
# These are essential for:
# 1. Checking setup status
# 2. Performing initial registration
# 3. Health probes (for container orchestration)
# 4. API documentation (for developers)
# 5. Prometheus metrics scraping
SETUP_WHITELIST_EXACT = frozenset(
    {
        "/",
        "/health",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/setup-status",
        "/api/auth/register",
        # Prometheus metrics endpoints (must be accessible for monitoring)
        "/api/system/gpu",
        "/api/system/stats",
        "/api/system/telemetry",
        "/api/metrics",
    }
)

# Prefixes that are always allowed
SETUP_WHITELIST_PREFIXES = (
    "/docs",
    "/redoc",
    "/api/system/health",
    # WebSocket endpoints must be reachable before setup completes so the
    # frontend can establish its real-time connection immediately.  Without
    # this, the nginx-proxied /ws/* requests hit the BaseHTTPMiddleware
    # dispatch path (HTTP upgrade negotiation uses scope "http") and get
    # blocked with 503, causing the "WebSocket max retries exhausted" loop.
    "/ws/",
)


class SetupGuardMiddleware(BaseHTTPMiddleware):
    """Middleware to guard API access until initial setup is complete.

    Returns 503 Service Unavailable for all requests (except whitelist)
    when no users exist in the database. This forces administrators to
    complete initial setup before the API is usable.

    The middleware checks user count on each request. While this adds
    a database query, it's necessary to handle the race condition where
    setup might complete between requests.

    Attributes:
        _setup_complete: Cached flag indicating setup is complete.
                        Once True, never rechecked (users can't be un-created).
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the setup guard middleware.

        Args:
            app: The ASGI application to wrap.
        """
        super().__init__(app)
        self._setup_complete = False
        # In-memory TTL cache to avoid querying users table on every request.
        # Stores (result: bool, timestamp: float). Checked before hitting DB.
        self._cached_result: bool = False
        self._cached_at: float = 0.0

    def _is_whitelisted(self, path: str) -> bool:
        """Check if a path is in the setup whitelist.

        Args:
            path: Request path to check.

        Returns:
            True if the path is whitelisted, False otherwise.
        """
        if path in SETUP_WHITELIST_EXACT:
            return True

        return any(path.startswith(prefix) for prefix in SETUP_WHITELIST_PREFIXES)

    async def _check_setup_complete(self) -> bool:
        """Check if initial setup is complete (at least one user exists).

        Uses an in-memory TTL cache to avoid querying the users table on
        every single request, which was causing excessive sequential scans
        (22k+ seq scans on a 1-row table).

        Returns:
            True if setup is complete, False if setup is required.
        """
        # Short-circuit: once setup is complete, it stays complete
        if self._setup_complete:
            return True

        # Check TTL cache before hitting the database
        now = time.monotonic()
        if (now - self._cached_at) < _SETUP_CHECK_TTL_SECONDS:
            return self._cached_result

        try:
            from backend.core.database import get_session
            from backend.models.user import User

            async with get_session() as session:
                result = await session.execute(select(func.count(User.id)))
                count = result.scalar() or 0

                if count > 0:
                    self._setup_complete = True
                    logger.info(
                        "Setup complete: found existing users",
                        extra={"user_count": count},
                    )
                    self._cached_result = True
                    self._cached_at = now
                    return True

                # Cache the negative result too, so we don't re-query for TTL seconds
                self._cached_result = False
                self._cached_at = now
                return False

        except Exception as e:
            # If we can't check the database, assume setup is complete
            # to avoid blocking legitimate traffic during DB issues
            logger.warning(
                f"Failed to check setup status, allowing request: {e}",
                extra={"error_type": type(e).__name__},
            )
            return True

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and guard against access during setup.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or endpoint.

        Returns:
            HTTP response (503 if setup required and path not whitelisted).
        """
        path = request.url.path

        # Always allow whitelisted paths
        if self._is_whitelisted(path):
            return await call_next(request)

        # Check if setup is complete
        if await self._check_setup_complete():
            return await call_next(request)

        # Setup not complete - return 503
        logger.info(
            "Request blocked: setup not complete",
            extra={
                "path": path,
                "method": request.method,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Initial setup required. Please register the first admin user.",
                "setup_url": "/api/auth/register",
                "setup_status_url": "/api/auth/setup-status",
            },
        )


def reset_setup_guard_state() -> None:
    """Reset setup guard state for testing.

    WARNING: Only use this in test fixtures. Never call in production.
    """
    # This function exists for test isolation but the actual reset
    # happens by creating a new middleware instance in tests
    pass
