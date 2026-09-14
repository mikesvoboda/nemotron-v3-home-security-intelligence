"""Middleware for request ID and correlation ID generation and propagation.

This module provides middleware that:
1. Generates or extracts request IDs (X-Request-ID) for request tracking
2. Generates or extracts correlation IDs (X-Correlation-ID) for distributed tracing
3. Sets both in context for access by services and loggers
4. Echoes both headers in responses for client correlation

NEM-1472: Added correlation ID support for distributed tracing
"""

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logging import set_request_id

# Context variable for correlation ID (separate from request_id for clarity)
# This allows distributed tracing across services
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context.

    Returns:
        The correlation ID if set, None otherwise.
    """
    return _correlation_id.get()


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID in context.

    Args:
        correlation_id: The correlation ID to set, or None to clear.
    """
    _correlation_id.set(correlation_id)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that generates and propagates request IDs and correlation IDs.

    This middleware handles two types of identifiers:

    - **Request ID (X-Request-ID)**: Short identifier for a single request.
      Useful for quick debugging and log correlation within a single service.
      Generated as an 8-character UUID prefix if not provided.

    - **Correlation ID (X-Correlation-ID)**: Full UUID for distributed tracing.
      Propagated across service boundaries to correlate logs/traces across
      the entire request flow (API -> YOLO26 -> Nemotron -> etc.).
      Generated as a full UUID if not provided.

    Both IDs are:
    - Extracted from incoming request headers if present
    - Generated if not provided
    - Set in context for access by services and loggers
    - Echoed in response headers for client correlation
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Generate request ID and correlation ID, set them in context."""
        # Get existing request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]

        # Get existing correlation ID from header or generate new one
        # Correlation ID is a full UUID for distributed tracing
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # Set in context for logging and service access
        set_request_id(request_id)
        set_correlation_id(correlation_id)

        try:
            response = await call_next(request)
            # Add request ID and correlation ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            # Clear context
            set_request_id(None)
            set_correlation_id(None)
