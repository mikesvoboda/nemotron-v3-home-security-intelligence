"""Deprecation logging middleware for tracking deprecated endpoint usage (NEM-2090).

This module implements middleware for:
- Logging calls to deprecated API endpoints
- Tracking deprecation metrics via Prometheus
- Adding warning headers to deprecation responses
- Client identification for migration tracking

The middleware detects deprecated endpoints by checking for the 'Deprecation' header
in responses, which should be set by deprecated route handlers.

Usage:
    # In deprecated route handlers, set the Deprecation header:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2025-12-31"  # Optional sunset date

    # The middleware will then:
    # 1. Log a warning with client info
    # 2. Increment Prometheus counter
    # 3. Add Warning header to response
"""

from collections.abc import Awaitable, Callable

from prometheus_client import Counter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.core.logging import get_logger
from backend.core.sanitization import sanitize_metric_label

logger = get_logger(__name__)

# Prometheus counter for deprecated endpoint calls
# Labels: endpoint path and client_id for tracking migration progress
DEPRECATED_CALLS_TOTAL = Counter(
    "hsi_api_deprecated_calls_total",
    "Total calls to deprecated API endpoints",
    labelnames=["endpoint", "client_id"],
)


class DeprecationLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware that logs and tracks calls to deprecated API endpoints.

    This middleware:
    1. Checks response headers for the 'Deprecation' header
    2. If present, logs a warning with client identification
    3. Increments Prometheus metrics for deprecation tracking
    4. Adds a Warning header (RFC 7234) to inform clients

    The 'Deprecation' header should be set by deprecated route handlers
    to mark endpoints as deprecated. Optionally, a 'Sunset' header can
    indicate when the endpoint will be removed.

    Attributes:
        app: The FastAPI/Starlette application
        warn_code: HTTP warning code (default: 299 Miscellaneous Warning)
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        warn_code: int = 299,
    ) -> None:
        """Initialize deprecation logger middleware.

        Args:
            app: FastAPI/Starlette application
            warn_code: HTTP Warning header code (default: 299)
                RFC 7234 defines 299 as "Miscellaneous Warning"
        """
        super().__init__(app)
        self.warn_code = warn_code

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Check for deprecation headers and log/track if present.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response, potentially with Warning header added
        """
        response = await call_next(request)

        # Check if the response indicates a deprecated endpoint
        deprecation_header = response.headers.get("Deprecation")

        if deprecation_header:
            self._handle_deprecated_call(request, response)

        return response

    def _handle_deprecated_call(self, request: Request, response: Response) -> None:
        """Handle a call to a deprecated endpoint.

        Logs the call, increments metrics, and adds Warning header.

        Args:
            request: The HTTP request
            response: The HTTP response
        """
        # Extract client identification
        client_id = request.headers.get("X-Client-ID", "unknown")
        endpoint = request.url.path
        method = request.method
        user_agent = request.headers.get("user-agent", "unknown")

        # Get client IP for logging (privacy-aware)
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        # Log the deprecated endpoint call
        logger.warning(
            f"Deprecated endpoint called: {method} {endpoint}",
            extra={
                "endpoint": endpoint,
                "method": method,
                "client_id": client_id,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "deprecation_info": response.headers.get("Deprecation"),
                "sunset_date": response.headers.get("Sunset"),
            },
        )

        # Increment Prometheus counter
        # Sanitize labels to prevent cardinality explosion
        safe_endpoint = sanitize_metric_label(endpoint, max_length=128)
        safe_client_id = sanitize_metric_label(client_id, max_length=64)
        DEPRECATED_CALLS_TOTAL.labels(
            endpoint=safe_endpoint,
            client_id=safe_client_id,
        ).inc()

        # Add Warning header (RFC 7234)
        # Format: warn-code warn-agent warn-text [warn-date]
        sunset_info = ""
        sunset_header = response.headers.get("Sunset")
        if sunset_header:
            sunset_info = f" Will be removed after {sunset_header}."

        warning_text = f"This endpoint is deprecated.{sunset_info}"
        warning_header = f'{self.warn_code} - "{warning_text}"'

        # Only add Warning header if not already present
        if "Warning" not in response.headers:
            response.headers["Warning"] = warning_header


def record_deprecated_call(endpoint: str, client_id: str = "unknown") -> None:
    """Manually record a deprecated endpoint call.

    This helper function can be used by route handlers to record
    deprecation metrics without relying solely on the middleware.

    Args:
        endpoint: The deprecated endpoint path
        client_id: Client identifier (default: "unknown")

    Example:
        @router.get("/v1/old-endpoint")
        async def old_endpoint(response: Response):
            response.headers["Deprecation"] = "true"
            record_deprecated_call("/v1/old-endpoint", request.headers.get("X-Client-ID"))
            return {"message": "Use /v2/new-endpoint instead"}
    """
    safe_endpoint = sanitize_metric_label(endpoint, max_length=128)
    safe_client_id = sanitize_metric_label(client_id, max_length=64)
    DEPRECATED_CALLS_TOTAL.labels(
        endpoint=safe_endpoint,
        client_id=safe_client_id,
    ).inc()
