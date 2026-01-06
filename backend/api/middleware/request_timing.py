"""Request timing middleware for API latency tracking (NEM-1469).

This module implements middleware for:
- Measuring request/response duration
- Adding X-Response-Time header to responses
- Logging slow requests above configurable threshold
- Structured logging with request context

The middleware uses time.perf_counter() for high-precision timing.
"""

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware that measures request duration and logs slow requests.

    This middleware:
    1. Records request start time using time.perf_counter()
    2. Adds X-Response-Time header with duration in milliseconds
    3. Logs requests that exceed the slow request threshold

    Attributes:
        slow_request_threshold_ms: Minimum duration (ms) to trigger slow request logging.
            Defaults to value from settings or 500ms.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        slow_request_threshold_ms: int | None = None,
    ) -> None:
        """Initialize request timing middleware.

        Args:
            app: FastAPI/Starlette application
            slow_request_threshold_ms: Threshold in milliseconds for logging slow requests.
                If not provided, uses SLOW_REQUEST_THRESHOLD_MS from settings.
                Falls back to 500ms if neither is set.
        """
        super().__init__(app)

        if slow_request_threshold_ms is not None:
            self.slow_request_threshold_ms = slow_request_threshold_ms
        else:
            # Try to get from settings, default to 500ms
            try:
                settings = get_settings()
                self.slow_request_threshold_ms = getattr(settings, "slow_request_threshold_ms", 500)
            except Exception:
                # Fallback if settings unavailable (e.g., during testing)
                self.slow_request_threshold_ms = 500

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Measure request duration and add timing header.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response with X-Response-Time header added
        """
        # Record start time with high precision
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

            # Calculate duration in milliseconds
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            # Log slow requests
            if duration_ms >= self.slow_request_threshold_ms:
                self._log_slow_request(request, response, duration_ms)

            return response

        except Exception:
            # Calculate duration even on error
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log the slow request if it was slow before error
            if duration_ms >= self.slow_request_threshold_ms:
                logger.warning(
                    f"Slow request (error): {request.method} {request.url.path} "
                    f"- {duration_ms:.2f}ms",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration_ms, 2),
                        "error": True,
                    },
                )

            # Re-raise the exception
            raise

    def _log_slow_request(self, request: Request, response: Response, duration_ms: float) -> None:
        """Log details of a slow request.

        Uses structured logging with extra fields for easy parsing
        and filtering in log aggregation systems.

        Args:
            request: The HTTP request
            response: The HTTP response
            duration_ms: Request duration in milliseconds
        """
        # Get client IP if available
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        # Build structured log message
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
