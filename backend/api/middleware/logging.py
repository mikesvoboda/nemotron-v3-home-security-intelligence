"""Request/response logging middleware for API debugging (NEM-1431).

This module implements structured request/response logging middleware for FastAPI:
- Logs HTTP method, path, status code, duration
- Logs client IP and user agent
- Supports configurable verbosity (INFO, DEBUG)
- Security: Never logs sensitive data (auth headers, request/response bodies)
- Security: Masks sensitive query parameters (api_key, password, token, etc.)

Security Considerations:
- Authorization headers are NEVER logged
- Request/response bodies are NEVER logged (may contain passwords, tokens)
- Sensitive query parameters are masked with [REDACTED]
"""

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Sensitive query parameter names that should be masked
# Case-insensitive matching is performed
SENSITIVE_PARAMS = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "password",
        "passwd",
        "pwd",
        "token",
        "access_token",
        "refresh_token",
        "bearer",
        "secret",
        "key",
        "auth",
        "authorization",
        "credential",
        "credentials",
        "session",
        "session_id",
        "sessionid",
        "private_key",
        "privatekey",
    }
)


def mask_sensitive_params(params: dict[str, str]) -> dict[str, str]:
    """Mask sensitive query parameters for safe logging.

    This function replaces values of sensitive parameters with [REDACTED]
    to prevent accidental exposure of secrets in logs.

    Args:
        params: Dictionary of query parameter name-value pairs

    Returns:
        New dictionary with sensitive values replaced by [REDACTED]
    """
    if not params:
        return {}

    masked = {}
    for key, value in params.items():
        # Case-insensitive comparison
        if key.lower() in SENSITIVE_PARAMS:
            masked[key] = "[REDACTED]"
        else:
            masked[key] = value

    return masked


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request.

    Uses the same logic as rate_limit module's get_client_ip but simplified
    for logging purposes (we don't need the full trusted proxy validation here).

    Args:
        request: The HTTP request object

    Returns:
        Client IP address as string, or "unknown" if not available
    """
    if request.client:
        return str(request.client.host)
    return "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs request/response details for API debugging.

    This middleware provides structured logging for all HTTP requests:

    At INFO level:
    - HTTP method
    - Request path
    - Response status code
    - Duration in milliseconds
    - Client IP
    - Request ID (if available from RequestIDMiddleware)
    - User agent

    At DEBUG level (in addition to INFO):
    - Query parameters (sensitive values masked)
    - Response content length

    Security:
    - NEVER logs Authorization or X-API-Key headers
    - NEVER logs request or response bodies
    - Masks sensitive query parameters (api_key, password, token, etc.)

    Attributes:
        verbosity: Logging verbosity level ("INFO" or "DEBUG")
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        verbosity: str = "INFO",
    ) -> None:
        """Initialize request logging middleware.

        Args:
            app: FastAPI/Starlette application
            verbosity: Logging verbosity level. Valid values:
                - "INFO": Log basic request details (method, path, status, duration)
                - "DEBUG": Log additional details (query params, response size)

        Raises:
            ValueError: If verbosity is not "INFO" or "DEBUG"
        """
        super().__init__(app)

        valid_verbosity = {"INFO", "DEBUG"}
        if verbosity.upper() not in valid_verbosity:
            raise ValueError(
                f"Invalid verbosity '{verbosity}'. Must be one of: {', '.join(valid_verbosity)}"
            )

        self.verbosity = verbosity.upper()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and log details.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response from the handler
        """
        # Record start time with high precision
        start_time = time.perf_counter()

        # Extract request details before calling next handler
        method = request.method
        path = request.url.path
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # Get request ID from scope if set by RequestIDMiddleware
        request_id = request.headers.get("X-Request-ID")

        response_status = 500  # Default in case of exception
        response_size: int | None = None

        try:
            response = await call_next(request)
            response_status = response.status_code

            # Get response size from content-length header if available
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    response_size = int(content_length)
                except ValueError:
                    pass

            return response

        except Exception:
            # Re-raise exception but still log the request
            raise

        finally:
            # Calculate duration in milliseconds
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Build log entry
            self._log_request(
                method=method,
                path=path,
                status=response_status,
                duration_ms=duration_ms,
                client_ip=client_ip,
                request_id=request_id,
                user_agent=user_agent,
                query_params=dict(request.query_params),
                response_size=response_size,
            )

    def _log_request(
        self,
        *,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        client_ip: str,
        request_id: str | None,
        user_agent: str,
        query_params: dict[str, str],
        response_size: int | None,
    ) -> None:
        """Log request details with structured fields.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            status: Response status code
            duration_ms: Request duration in milliseconds
            client_ip: Client IP address
            request_id: Request ID from RequestIDMiddleware (if present)
            user_agent: User-Agent header value
            query_params: Query parameters (will be masked for sensitive values)
            response_size: Response content length in bytes (if available)
        """
        # Base log message
        message = f"request_completed: {method} {path} - {status} - {duration_ms:.2f}ms"

        # Base extra fields (always included at INFO level)
        extra: dict[str, str | int | float | None] = {
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip,
            "user_agent": user_agent,
        }

        if request_id:
            extra["request_id"] = request_id

        # Add DEBUG-level fields
        if self.verbosity == "DEBUG":
            if query_params:
                # Mask sensitive parameters before logging
                masked_params = mask_sensitive_params(query_params)
                extra["query_params"] = str(masked_params)

            if response_size is not None:
                extra["response_size"] = response_size

            # Log at DEBUG level with additional details
            logger.debug(message, extra=extra)
        else:
            # Log at INFO level with basic details
            logger.info(message, extra=extra)
