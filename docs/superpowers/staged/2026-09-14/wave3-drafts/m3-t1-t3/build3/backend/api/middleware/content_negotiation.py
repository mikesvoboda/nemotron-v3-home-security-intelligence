"""Content negotiation middleware for HTTP response headers.

This middleware handles content negotiation concerns beyond Accept header validation:
- Adds charset declaration to Content-Type headers for JSON responses
- Adds Vary header for proper caching with content negotiation

RFC References:
- RFC 7231 Section 3.1.1.5: Content-Type charset parameter
- RFC 7231 Section 7.1.4: Vary header for caching
- RFC 7694: Hypertext Transfer Protocol (HTTP) Client-Initiated Content-Encoding
"""

from collections.abc import Awaitable, Callable
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class ContentNegotiationMiddleware(BaseHTTPMiddleware):
    """Middleware that enhances response headers for content negotiation.

    This middleware:
    1. Adds charset=utf-8 to Content-Type headers for JSON responses
    2. Adds Vary: Accept-Encoding header for proper caching

    The Vary header tells caches that the response may differ based on
    Accept-Encoding, which is essential when using compression (GzipMiddleware).

    Attributes:
        json_media_types: Set of media types that should have charset added
    """

    # Media types that should have charset=utf-8 appended
    JSON_MEDIA_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "application/json",
            "application/problem+json",
        }
    )

    def __init__(
        self,
        app: ASGIApp,
        *,
        json_media_types: set[str] | frozenset[str] | None = None,
        add_vary_header: bool = True,
    ):
        """Initialize content negotiation middleware.

        Args:
            app: FastAPI/Starlette application
            json_media_types: Override default JSON media types for charset addition
            add_vary_header: Whether to add Vary: Accept-Encoding header (default: True)
        """
        super().__init__(app)
        self.json_media_types = (
            frozenset(json_media_types) if json_media_types else self.JSON_MEDIA_TYPES
        )
        self.add_vary_header = add_vary_header

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and enhance response headers.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response with enhanced headers
        """
        response = await call_next(request)

        # Get current content-type header
        content_type = response.headers.get("content-type", "")

        # Add charset to JSON content types if not already present
        if content_type and "charset" not in content_type.lower():
            # Check if this is a JSON media type
            media_type = content_type.split(";")[0].strip().lower()
            if media_type in self.json_media_types:
                # Add charset=utf-8 to Content-Type
                response.headers["content-type"] = f"{content_type}; charset=utf-8"

        # Add Vary header for proper caching
        # The Vary header tells caches that the response may differ based on
        # the value of certain request headers (Accept-Encoding for compression)
        if self.add_vary_header:
            existing_vary = response.headers.get("vary", "")
            if existing_vary:
                # Append Accept-Encoding if not already present
                vary_values = [v.strip().lower() for v in existing_vary.split(",")]
                if "accept-encoding" not in vary_values:
                    response.headers["vary"] = f"{existing_vary}, Accept-Encoding"
            else:
                response.headers["vary"] = "Accept-Encoding"

        return response
