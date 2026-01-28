"""Prometheus HTTP request metrics middleware (NEM-4149).

This module implements standard Prometheus HTTP metrics for FastAPI:
- http_request_duration_seconds: Histogram for request latency
- http_request_duration_seconds_count: Request count (derived from histogram)
- http_request_duration_seconds_sum: Total duration (derived from histogram)

Labels:
- method: HTTP method (GET, POST, etc.)
- handler: Route handler name (deprecated, kept for compatibility)
- status: HTTP status code
- http_route: Route path pattern (e.g., /api/events/{event_id})

These metrics are required for the hsi-request-profiling Grafana dashboard.

Usage:
    from backend.api.middleware.prometheus import PrometheusMiddleware

    app.add_middleware(PrometheusMiddleware)

The middleware is designed for minimal performance overhead by:
- Using time.perf_counter() for high-precision timing
- Extracting route patterns from FastAPI's routing system
- Avoiding string operations in the hot path where possible
"""

import time
from collections.abc import Awaitable, Callable

from prometheus_client import Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Standard HTTP request duration buckets (in seconds)
# These buckets are designed for typical web API latencies:
# - 5ms-10ms: Fast cached responses
# - 25ms-100ms: Database reads, simple processing
# - 250ms-500ms: Complex queries, aggregations
# - 1s-2.5s: AI inference, batch operations
# - 5s-10s: Long-running operations
HTTP_REQUEST_DURATION_BUCKETS = (
    0.005,  # 5ms
    0.01,  # 10ms
    0.025,  # 25ms
    0.05,  # 50ms
    0.1,  # 100ms
    0.25,  # 250ms
    0.5,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
)

# Prometheus histogram for HTTP request duration
# This is the standard metric name expected by Prometheus/Grafana
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "handler", "status", "http_route"],
    buckets=HTTP_REQUEST_DURATION_BUCKETS,
)

# Paths to exclude from metrics (health checks, metrics endpoint)
# These endpoints are called frequently by monitoring systems and
# would skew the latency distribution
EXCLUDED_PATHS = frozenset(
    {
        "/",
        "/health",
        "/ready",
        "/api/metrics",
    }
)


def _get_route_pattern(request: Request) -> str:
    """Extract the route pattern from a request.

    This function matches the request against FastAPI's router to find
    the original route pattern (with path parameters like {event_id}).

    Args:
        request: The incoming HTTP request

    Returns:
        Route pattern string (e.g., "/api/events/{event_id}") or
        the raw path if no route matches.
    """
    # Try to get the route from FastAPI's routing system
    app = request.app
    if hasattr(app, "routes"):
        for route in app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                if hasattr(route, "path"):
                    return str(route.path)
                break

    # Fallback to the raw path
    return str(request.url.path)


def _get_handler_name(request: Request) -> str:
    """Extract the handler/endpoint name from a request.

    Args:
        request: The incoming HTTP request

    Returns:
        Handler function name or "unknown" if not found.
    """
    # Try to get the endpoint name from scope
    if "endpoint" in request.scope and request.scope["endpoint"] is not None:
        return str(request.scope["endpoint"].__name__)

    # Try to get from route
    if "route" in request.scope and request.scope["route"] is not None:
        route = request.scope["route"]
        if hasattr(route, "endpoint") and route.endpoint is not None:
            return str(route.endpoint.__name__)
        if hasattr(route, "name") and route.name is not None:
            return str(route.name)

    return "unknown"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP request metrics for Prometheus.

    This middleware records:
    - Request duration as a histogram
    - Request count (via histogram observations)
    - Request duration sum (via histogram observations)

    Labels include method, handler, status, and http_route for
    detailed breakdowns in Grafana dashboards.

    Attributes:
        exclude_paths: Set of paths to exclude from metrics recording.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        exclude_paths: frozenset[str] | None = None,
    ) -> None:
        """Initialize Prometheus metrics middleware.

        Args:
            app: FastAPI/Starlette application
            exclude_paths: Optional set of paths to exclude from metrics.
                Defaults to EXCLUDED_PATHS (health checks, metrics endpoint).
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths if exclude_paths is not None else EXCLUDED_PATHS

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and record Prometheus metrics.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response from the handler
        """
        path = request.url.path

        # Skip metrics for excluded paths
        if path in self.exclude_paths:
            return await call_next(request)

        # Record start time with high precision
        start_time = time.perf_counter()

        # Default status for error cases
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response

        except Exception:
            # Re-raise after recording metrics
            raise

        finally:
            # Calculate duration in seconds
            duration_seconds = time.perf_counter() - start_time

            # Get route pattern and handler name
            http_route = _get_route_pattern(request)
            handler = _get_handler_name(request)

            # Record the metric
            http_request_duration_seconds.labels(
                method=request.method,
                handler=handler,
                status=str(status_code),
                http_route=http_route,
            ).observe(duration_seconds)
