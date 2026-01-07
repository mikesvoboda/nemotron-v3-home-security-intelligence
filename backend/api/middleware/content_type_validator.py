"""Content-Type validation middleware for API request bodies.

This middleware validates that incoming requests with bodies (POST, PUT, PATCH)
have an acceptable Content-Type header. This is a defense-in-depth measure
to prevent content-type confusion attacks.

Security considerations:
- Prevents attackers from sending unexpected content types that might be processed differently
- Rejects requests with missing or invalid Content-Type for methods that expect a body
- Allows requests without bodies to pass through (e.g., GET, DELETE)
- Supports both application/json and multipart/form-data for file uploads
"""

from collections.abc import Awaitable, Callable
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.core.logging import get_logger

logger = get_logger(__name__)


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """Middleware that validates Content-Type header for request bodies.

    This middleware ensures that requests with bodies (POST, PUT, PATCH) have
    an acceptable Content-Type header. Requests with unexpected content types
    are rejected with HTTP 415 Unsupported Media Type.

    Attributes:
        METHODS_WITH_BODY: HTTP methods that typically have request bodies
        ALLOWED_CONTENT_TYPES: Set of acceptable base content types
    """

    METHODS_WITH_BODY: ClassVar[set[str]] = {"POST", "PUT", "PATCH"}

    # Allowed content types (base types without charset/boundary parameters)
    ALLOWED_CONTENT_TYPES: ClassVar[set[str]] = {
        "application/json",
        "multipart/form-data",
    }

    # Paths to exempt from Content-Type validation
    # These are typically health checks or endpoints that don't require a body
    EXEMPT_PATHS: ClassVar[set[str]] = {
        "/",
        "/health",
        "/ready",
        "/api/system/health",
        "/api/system/health/ready",
        "/api/metrics",
    }

    def __init__(
        self,
        app: ASGIApp,
        *,
        allowed_content_types: set[str] | None = None,
        exempt_paths: set[str] | None = None,
    ):
        """Initialize Content-Type validation middleware.

        Args:
            app: FastAPI/Starlette application
            allowed_content_types: Override default allowed content types
            exempt_paths: Override default exempt paths
        """
        super().__init__(app)
        self.allowed_content_types = allowed_content_types or self.ALLOWED_CONTENT_TYPES.copy()
        self.exempt_paths = exempt_paths or self.EXEMPT_PATHS.copy()

    def _parse_content_type(self, content_type_header: str) -> str:
        """Parse Content-Type header to extract base type.

        Handles Content-Type headers with parameters like charset or boundary:
        - "application/json; charset=utf-8" -> "application/json"
        - "multipart/form-data; boundary=----" -> "multipart/form-data"

        Args:
            content_type_header: Raw Content-Type header value

        Returns:
            Base content type in lowercase
        """
        if not content_type_header:
            return ""

        # Split on semicolon to remove parameters
        base_type = content_type_header.split(";")[0].strip().lower()
        return base_type

    def _has_body(self, request: Request) -> bool:
        """Check if request appears to have a body.

        A request has a body if:
        - Content-Length header is present and > 0
        - Transfer-Encoding header is present (chunked transfer)
        - Content-Type header is present

        Args:
            request: Incoming HTTP request

        Returns:
            True if request appears to have a body
        """
        content_length = request.headers.get("content-length", "0")
        transfer_encoding = request.headers.get("transfer-encoding", "")
        content_type = request.headers.get("content-type", "")

        # Check for explicit content length > 0
        try:
            if int(content_length) > 0:
                return True
        except ValueError:
            pass

        # Check for chunked transfer encoding
        if transfer_encoding.lower() == "chunked":
            return True

        # Check for Content-Type header (indicates intent to send body)
        return bool(content_type)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Validate Content-Type header and process request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response (either from validation failure or successful processing)
        """
        # Skip validation for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Only validate methods that typically have bodies
        if request.method not in self.METHODS_WITH_BODY:
            return await call_next(request)

        # Check if request has a body
        if not self._has_body(request):
            return await call_next(request)

        # Get and parse Content-Type header
        content_type_header = request.headers.get("content-type", "")
        base_type = self._parse_content_type(content_type_header)

        # Validate Content-Type
        if not base_type:
            logger.warning(
                "Missing Content-Type header for request with body",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            return JSONResponse(
                status_code=415,
                content={
                    "detail": "Missing Content-Type header. Use application/json or multipart/form-data",
                    "error": "unsupported_media_type",
                },
            )

        if base_type not in self.allowed_content_types:
            logger.warning(
                f"Unsupported Content-Type: {base_type}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "content_type": base_type,
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            return JSONResponse(
                status_code=415,
                content={
                    "detail": f"Unsupported Media Type: {base_type}. Use application/json or multipart/form-data",
                    "error": "unsupported_media_type",
                },
            )

        return await call_next(request)
