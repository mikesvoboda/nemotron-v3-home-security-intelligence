"""Request/Response logging middleware for structured observability.

NEM-1638: This middleware provides structured logging for HTTP requests,
enabling log aggregation and analysis in tools like Grafana Loki or ELK.

Features:
- Logs request start and completion with timing
- Includes trace context (trace_id, span_id) for log-to-trace correlation
- Includes correlation_id and request_id for request tracing
- Configurable log levels based on response status codes
- Excludes noisy endpoints (health checks, metrics) from logging
- Masks sensitive data (client IPs)

Usage:
    from backend.api.middleware.request_logging import RequestLoggingMiddleware

    app.add_middleware(RequestLoggingMiddleware)

    # Or with custom configuration:
    app.add_middleware(
        RequestLoggingMiddleware,
        excluded_paths=["/health", "/ready", "/metrics", "/custom-health"],
        log_level=logging.DEBUG,
    )
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.api.middleware.request_id import get_correlation_id
from backend.core.logging import (
    get_current_trace_context,
    get_logger,
    get_request_id,
    mask_ip,
)

# Default paths to exclude from request logging (reduce noise)
DEFAULT_EXCLUDED_PATHS = frozenset(
    {
        "/health",
        "/ready",
        "/metrics",
        "/",
        "/api/system/health",
        "/api/system/health/ready",
    }
)

# Logger for request logging
_logger = get_logger(__name__)


def format_request_log(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: str,
    request_id: str | None = None,
    correlation_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    user_agent: str | None = None,
    content_length: int | None = None,
) -> dict[str, Any]:
    """Format request log data as a structured dictionary.

    This function creates a structured log entry that can be easily parsed
    by log aggregation systems like Loki, ELK, or Splunk.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP response status code
        duration_ms: Request duration in milliseconds
        client_ip: Client IP address (masked for privacy)
        request_id: Request correlation ID
        correlation_id: Cross-service correlation ID
        trace_id: OpenTelemetry trace ID
        span_id: OpenTelemetry span ID
        user_agent: User-Agent header
        content_length: Response content length in bytes

    Returns:
        Structured dictionary with all request metadata.
    """
    log_data: dict[str, Any] = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "client_ip": client_ip,
    }

    # Add optional correlation fields
    if request_id:
        log_data["request_id"] = request_id
    if correlation_id:
        log_data["correlation_id"] = correlation_id
    if trace_id:
        log_data["trace_id"] = trace_id
    if span_id:
        log_data["span_id"] = span_id
    if user_agent:
        log_data["user_agent"] = user_agent
    if content_length is not None:
        log_data["content_length"] = content_length

    return log_data


def _get_log_level_for_status(status_code: int, default_level: int = logging.INFO) -> int:
    """Get appropriate log level based on HTTP status code.

    Args:
        status_code: HTTP response status code
        default_level: Default log level for 2xx/3xx responses

    Returns:
        logging level (INFO, WARNING, or ERROR)
    """
    if status_code >= 500:
        return logging.ERROR
    elif status_code >= 400:
        return logging.WARNING
    return default_level


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured HTTP request/response logging.

    This middleware logs all HTTP requests with structured data suitable
    for log aggregation and analysis. It integrates with OpenTelemetry
    trace context for log-to-trace correlation.

    Features:
    - Logs request completion with timing, status code, and correlation IDs
    - Excludes configurable paths (health checks, metrics) from logging
    - Uses appropriate log levels (ERROR for 5xx, WARNING for 4xx)
    - Masks client IP addresses for privacy
    - Includes trace context for observability correlation

    NEM-1638: Enhanced structured logging with trace context.
    """

    def __init__(
        self,
        app: Any,
        excluded_paths: list[str] | None = None,
        log_level: int = logging.INFO,
        dispatch: Callable[..., Any] | None = None,  # noqa: ARG002
    ) -> None:
        """Initialize the middleware.

        Args:
            app: ASGI application
            excluded_paths: List of path prefixes to exclude from logging.
                           Defaults to health check and metrics endpoints.
            log_level: Default log level for successful requests (2xx/3xx).
                      4xx uses WARNING, 5xx uses ERROR.
            dispatch: Unused, for BaseHTTPMiddleware compatibility.
        """
        super().__init__(app)
        self.excluded_paths = set(excluded_paths) if excluded_paths else set(DEFAULT_EXCLUDED_PATHS)
        self.default_log_level = log_level

    def _should_log_request(self, path: str) -> bool:
        """Check if request should be logged based on path.

        Args:
            path: Request path

        Returns:
            True if request should be logged, False otherwise.
        """
        # Exact match
        if path in self.excluded_paths:
            return False

        # Prefix match for excluded paths that represent directories
        # The excluded path must be longer than just "/" to be a prefix matcher
        for excluded in self.excluded_paths:
            if len(excluded) > 1 and excluded.endswith("/") and path.startswith(excluded):
                return False

        return True

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        """Process request and log completion with timing.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response from the application
        """
        path = request.url.path
        method = request.method

        # Skip logging for excluded paths
        if not self._should_log_request(path):
            response: Response = await call_next(request)
            return response

        # Record start time
        start_time = time.perf_counter()

        # Get trace context before calling next (context is set by middleware)
        trace_ctx = get_current_trace_context()
        request_id = get_request_id()
        correlation_id = get_correlation_id()

        # Get client IP (masked for privacy)
        client_ip = self._get_client_ip(request)
        client_ip_masked = mask_ip(client_ip)

        # Get user agent
        user_agent = request.headers.get("user-agent", None)

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Get response content length if available
            content_length = response.headers.get("content-length")
            content_length_int = int(content_length) if content_length else None

            # Format structured log data
            log_data = format_request_log(
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_ip_masked,
                request_id=request_id,
                correlation_id=correlation_id,
                trace_id=trace_ctx.get("trace_id"),
                span_id=trace_ctx.get("span_id"),
                user_agent=user_agent,
                content_length=content_length_int,
            )

            # Determine log level based on status code
            log_level = _get_log_level_for_status(response.status_code, self.default_log_level)

            # Log the request completion
            _logger.log(
                log_level,
                f"{method} {path} completed with {response.status_code} in {duration_ms:.2f}ms",
                extra=log_data,
            )

            return response

        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log error with context
            log_data = format_request_log(
                method=method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
                client_ip=client_ip_masked,
                request_id=request_id,
                correlation_id=correlation_id,
                trace_id=trace_ctx.get("trace_id"),
                span_id=trace_ctx.get("span_id"),
            )
            log_data["error_type"] = type(e).__name__

            _logger.error(
                f"{method} {path} failed with exception after {duration_ms:.2f}ms",
                extra=log_data,
                exc_info=True,
            )

            raise

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request.

        Checks X-Forwarded-For header first (for proxied requests),
        falls back to client.host.

        Args:
            request: HTTP request

        Returns:
            Client IP address string
        """
        # Check X-Forwarded-For header (may contain multiple IPs)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        # Fall back to connection client
        if request.client:
            return request.client.host

        return "unknown"
