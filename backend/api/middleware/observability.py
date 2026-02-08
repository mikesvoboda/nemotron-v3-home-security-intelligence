"""Unified observability middleware combining timing, logging, and Prometheus metrics.

NEM-5558: Merges RequestTimingMiddleware, RequestLoggingMiddleware, and PrometheusMiddleware
into a single middleware pass to eliminate redundant time.perf_counter() calls and reduce
middleware stack overhead.

Features:
- X-Response-Time header on all responses
- Slow request logging above configurable threshold
- Structured request/response logging with trace context (optional)
- Prometheus http_request_duration_seconds histogram
- Health endpoint short-circuit to bypass observability overhead
"""

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp

from backend.api.middleware.prometheus import (
    EXCLUDED_PATHS as PROMETHEUS_EXCLUDED_PATHS,
)
from backend.api.middleware.prometheus import (
    UNMATCHED_ROUTE_PATTERN,
    http_request_duration_seconds,
)
from backend.api.middleware.request_id import get_correlation_id
from backend.api.middleware.request_logging import (
    DEFAULT_EXCLUDED_PATHS as LOGGING_EXCLUDED_PATHS,
)
from backend.api.middleware.request_logging import (
    format_request_log,
)
from backend.core.logging import (
    get_current_trace_context,
    get_logger,
    get_request_id,
    mask_ip,
)

logger = get_logger(__name__)

# Paths that skip ALL observability (timing header, logging, and metrics)
HEALTH_SHORT_CIRCUIT_PATHS = frozenset(
    {
        "/health",
        "/api/system/health/ready",
        "/metrics",
    }
)


def _get_route_pattern(request: Request) -> str:
    """Extract the route pattern from a request for Prometheus labels.

    High Cardinality Protection (NEM-4488):
        Unmatched routes are normalized to UNMATCHED_ROUTE_PATTERN.
    """
    app = request.app
    if hasattr(app, "routes"):
        for route in app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                if hasattr(route, "path"):
                    return str(route.path)
                break
    return UNMATCHED_ROUTE_PATTERN


def _get_handler_name(request: Request) -> str:
    """Extract the handler/endpoint name from a request."""
    if "endpoint" in request.scope and request.scope["endpoint"] is not None:
        return str(request.scope["endpoint"].__name__)
    if "route" in request.scope and request.scope["route"] is not None:
        route = request.scope["route"]
        if hasattr(route, "endpoint") and route.endpoint is not None:
            return str(route.endpoint.__name__)
        if hasattr(route, "name") and route.name is not None:
            return str(route.name)
    return "unknown"


def _get_log_level_for_status(status_code: int, default_level: int = logging.INFO) -> int:
    """Get appropriate log level based on HTTP status code."""
    if status_code >= 500:
        return logging.ERROR
    elif status_code >= 400:
        return logging.WARNING
    return default_level


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Unified middleware for request timing, structured logging, and Prometheus metrics.

    Replaces three separate middleware (RequestTimingMiddleware, RequestLoggingMiddleware,
    PrometheusMiddleware) with a single pass that performs all observability tasks using
    one shared timer.

    Args:
        app: FastAPI/Starlette application
        slow_request_threshold_ms: Threshold for slow request logging (default: 500ms)
        enable_request_logging: Whether to emit structured request logs (default: False)
        logging_excluded_paths: Paths to exclude from request logging
        metrics_excluded_paths: Paths to exclude from Prometheus metrics
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        slow_request_threshold_ms: int | None = None,
        enable_request_logging: bool = False,
        logging_excluded_paths: frozenset[str] | None = None,
        metrics_excluded_paths: frozenset[str] | None = None,
    ) -> None:
        super().__init__(app)

        # Slow request threshold
        default_threshold_ms = 500
        if slow_request_threshold_ms is not None:
            self.slow_request_threshold_ms = slow_request_threshold_ms
        else:
            try:
                from backend.core.config import get_settings

                settings = get_settings()
                self.slow_request_threshold_ms = getattr(
                    settings, "slow_request_threshold_ms", default_threshold_ms
                )
            except Exception:
                self.slow_request_threshold_ms = default_threshold_ms

        self.enable_request_logging = enable_request_logging
        self.logging_excluded_paths = (
            logging_excluded_paths if logging_excluded_paths is not None else LOGGING_EXCLUDED_PATHS
        )
        self.metrics_excluded_paths = (
            metrics_excluded_paths
            if metrics_excluded_paths is not None
            else PROMETHEUS_EXCLUDED_PATHS
        )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Health endpoint short-circuit: skip all observability
        if path in HEALTH_SHORT_CIRCUIT_PATHS:
            return await call_next(request)

        method = request.method
        start_time = time.perf_counter()
        status_code = 500  # default for exception case

        # Pre-fetch logging context if logging is enabled
        if self.enable_request_logging and path not in self.logging_excluded_paths:
            trace_ctx = get_current_trace_context()
            request_id = get_request_id()
            correlation_id = get_correlation_id()
            client_ip = self._get_client_ip(request)
            client_ip_masked = mask_ip(client_ip)
            user_agent = request.headers.get("user-agent", None)
            should_log = True
        else:
            should_log = False

        should_record_metrics = path not in self.metrics_excluded_paths

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Timing
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            # Slow request logging
            if duration_ms >= self.slow_request_threshold_ms:
                self._log_slow_request(request, response, duration_ms)

            # Structured request logging
            if should_log:
                content_length = response.headers.get("content-length")
                content_length_int = int(content_length) if content_length else None
                log_data = format_request_log(
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    client_ip=client_ip_masked,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    trace_id=trace_ctx.get("trace_id"),
                    span_id=trace_ctx.get("span_id"),
                    user_agent=user_agent,
                    content_length=content_length_int,
                )
                log_level = _get_log_level_for_status(status_code)
                logger.log(
                    log_level,
                    f"{method} {path} completed with {status_code} in {duration_ms:.2f}ms",
                    extra=log_data,
                )

            # Prometheus metrics
            if should_record_metrics:
                http_route = _get_route_pattern(request)
                handler = _get_handler_name(request)
                http_request_duration_seconds.labels(
                    method=method,
                    handler=handler,
                    status=str(status_code),
                    http_route=http_route,
                ).observe(duration_seconds)

            return response

        except Exception as e:
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Always log failures
            logger.error(
                "Request processing failed",
                extra={
                    "duration_ms": round(duration_ms, 2),
                    "path": path,
                    "method": method,
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
            )

            # Structured error logging
            if should_log:
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
                logger.error(
                    f"{method} {path} failed with exception after {duration_ms:.2f}ms",
                    extra=log_data,
                    exc_info=True,
                )

            # Prometheus metrics for error case
            if should_record_metrics:
                http_route = _get_route_pattern(request)
                handler = _get_handler_name(request)
                http_request_duration_seconds.labels(
                    method=method,
                    handler=handler,
                    status=str(status_code),
                    http_route=http_route,
                ).observe(duration_seconds)

            raise

    def _log_slow_request(self, request: Request, response: Response, duration_ms: float) -> None:
        """Log details of a slow request."""
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host
        logger.warning(
            f"Slow request: {request.method} {request.url.path} - "
            f"{response.status_code} - {duration_ms:.2f}ms "
            f"(threshold: {self.slow_request_threshold_ms}ms)",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "threshold_ms": self.slow_request_threshold_ms,
                "client_ip": client_ip,
            },
        )

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request, checking proxy headers."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"
