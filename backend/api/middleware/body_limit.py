"""Request body size limit middleware for DoS protection.

This module provides middleware to limit the maximum size of request bodies,
preventing denial-of-service attacks through large payload submissions.

Usage:
    from backend.api.middleware.body_limit import BodySizeLimitMiddleware

    app.add_middleware(BodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)

Security considerations:
- Default limit is 10MB, suitable for most API use cases
- Requests exceeding the limit receive 413 Payload Too Large response
- The check is performed before reading the body for early rejection
- Content-Length header is used for efficient pre-flight rejection

NEM-1614: Add request body size limits to prevent DoS attacks
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from starlette.types import ASGIApp

# Type alias for call_next function
RequestResponseEndpoint = Callable[[Request], Awaitable[Response]]

# Default maximum body size: 10MB
DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size and prevent DoS attacks.

    This middleware checks the Content-Length header before processing
    the request body. If the declared size exceeds the configured limit,
    the request is rejected with a 413 Payload Too Large response.

    Attributes:
        max_body_size: Maximum allowed body size in bytes (default 10MB)

    Example:
        # Limit to 1MB
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=1024 * 1024)

        # Limit to 50MB for file uploads
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=50 * 1024 * 1024)
    """

    def __init__(
        self,
        app: ASGIApp,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
            max_body_size: Maximum body size in bytes (default 10MB)
        """
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and enforce body size limit.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response from the handler, or 413 if body too large
        """
        # Check Content-Length header for early rejection
        content_length = request.headers.get("content-length")

        if content_length is not None:
            try:
                body_size = int(content_length)
                if body_size > self.max_body_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "error_code": "PAYLOAD_TOO_LARGE",
                            "message": "Request body too large",
                        },
                    )
            except ValueError:
                # Invalid Content-Length header - let the request proceed
                # The framework will handle malformed headers
                pass

        # Body size is within limits, proceed with the request
        return await call_next(request)
