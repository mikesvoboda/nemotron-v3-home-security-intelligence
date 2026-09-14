"""Profiling middleware for trace context correlation.

NEM-4127: This middleware tags Pyroscope profiling data with OpenTelemetry
trace context, enabling correlation between distributed traces and continuous
profiles. This allows debugging slow requests by viewing their exact CPU profiles.

Usage:
    The middleware is automatically registered in main.py during application
    startup. No additional configuration is required.

    When both OpenTelemetry and Pyroscope are enabled, every HTTP request
    will have its profiling data tagged with trace_id and span_id attributes.

    To view correlated profiles:
    1. Find a slow trace in Jaeger/Tempo
    2. Copy the trace_id
    3. In Pyroscope, filter by tag: trace_id="<trace_id>"
    4. View the exact CPU profile for that request
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.telemetry import profile_with_trace_context

# Type alias for call_next function
RequestResponseEndpoint = Callable[[Request], Awaitable[Response]]


class ProfilingMiddleware(BaseHTTPMiddleware):
    """Middleware to tag profiling data with trace context.

    This middleware wraps each HTTP request in a profile_with_trace_context()
    context manager, which tags Pyroscope profiling data with the current
    OpenTelemetry trace_id and span_id.

    The middleware gracefully handles cases where:
    - OpenTelemetry is not enabled (no tagging, request proceeds normally)
    - Pyroscope is not installed (no tagging, request proceeds normally)
    - No active trace context (no tagging, request proceeds normally)

    Example:
        >>> from fastapi import FastAPI
        >>> from backend.api.middleware.profiling import ProfilingMiddleware
        >>> app = FastAPI()
        >>> app.add_middleware(ProfilingMiddleware)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request with trace-tagged profiling.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            The HTTP response from the downstream handler
        """
        with profile_with_trace_context():
            response = await call_next(request)
        return response
