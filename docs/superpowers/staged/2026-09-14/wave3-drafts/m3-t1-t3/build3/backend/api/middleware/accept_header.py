"""Accept header content negotiation middleware for HTTP API responses.

This middleware validates that incoming requests have an Accept header compatible
with the API's supported response formats. It implements HTTP content negotiation
as specified in RFC 7231.

Supported media types:
- application/json: Standard JSON responses
- application/problem+json: RFC 7807 Problem Details for errors

Security considerations:
- Prevents clients from requesting unsupported formats that could cause errors
- Returns clear 406 Not Acceptable when requested format is not supported
- Allows monitoring and metrics endpoints to bypass validation
- Supports wildcards (*/*) and type wildcards (application/*)

RFC References:
- RFC 7231 Section 5.3.2: Accept header semantics
- RFC 7807: Problem Details for HTTP APIs
"""

from collections.abc import Awaitable, Callable
from typing import ClassVar

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Default supported media types for API responses
SUPPORTED_MEDIA_TYPES: frozenset[str] = frozenset(
    {
        "application/json",
        "application/problem+json",
    }
)


def parse_accept_header(accept_header: str | None) -> list[tuple[str, float]]:
    """Parse Accept header into list of (media_type, quality) tuples.

    Parses the Accept header according to RFC 7231 Section 5.3.2.
    Media types are sorted by quality value (highest first).

    Args:
        accept_header: Raw Accept header value (may be None or empty)

    Returns:
        List of (media_type, quality) tuples sorted by quality (descending).
        Empty list if header is None or empty.

    Examples:
        >>> parse_accept_header("application/json")
        [("application/json", 1.0)]

        >>> parse_accept_header("text/html;q=0.9, application/json;q=0.8")
        [("text/html", 0.9), ("application/json", 0.8)]

        >>> parse_accept_header("*/*")
        [("*/*", 1.0)]
    """
    if not accept_header:
        return []

    media_types: list[tuple[str, float]] = []

    for raw_part in accept_header.split(","):
        stripped_part = raw_part.strip()
        if not stripped_part:
            continue

        # Parse media type and parameters
        # Format: media-type [; parameter1=value1] [; q=quality]
        segments = stripped_part.split(";")
        media_type = segments[0].strip().lower()

        if not media_type:
            continue

        # Extract quality value (default is 1.0)
        quality = 1.0
        for raw_segment in segments[1:]:
            stripped_segment = raw_segment.strip()
            if stripped_segment.lower().startswith("q="):
                try:
                    q_value = float(stripped_segment[2:].strip())
                    # Clamp quality to valid range [0, 1]
                    quality = max(0.0, min(1.0, q_value))
                except ValueError:
                    # Invalid quality value, use default
                    quality = 1.0
                break

        media_types.append((media_type, quality))

    # Sort by quality (highest first)
    media_types.sort(key=lambda x: x[1], reverse=True)

    return media_types


def select_best_media_type(
    accepted_types: list[tuple[str, float]],
    supported_types: frozenset[str],
) -> str | None:
    """Select the best matching media type from accepted types.

    Implements content negotiation by selecting the highest-quality
    supported media type from the client's Accept header.

    Args:
        accepted_types: List of (media_type, quality) tuples from Accept header
        supported_types: Set of media types supported by the API

    Returns:
        The best matching media type, or None if no match found.
        Returns "application/json" as default if accepted_types is empty.

    Algorithm:
        1. If accepted_types is empty, return "application/json" (default)
        2. For each accepted type (in quality order):
           a. If exact match in supported_types, return it
           b. If wildcard (*/*), return "application/json"
           c. If type wildcard (e.g., application/*), match any supported type
        3. Return None if no match found
    """
    # Empty Accept header means client accepts any format - use default
    if not accepted_types:
        return "application/json"

    for media_type, quality in accepted_types:
        # Skip types with q=0 (explicitly rejected)
        if quality == 0.0:
            continue

        # Exact match
        if media_type in supported_types:
            return media_type

        # Wildcard */* matches any supported type
        if media_type == "*/*":
            return "application/json"  # Return default

        # Type wildcard (e.g., application/*) matches any subtype
        if media_type.endswith("/*"):
            type_prefix = media_type[:-1]  # "application/*" -> "application/"
            # Check for application/json first as the preferred default
            if "application/json" in supported_types and "application/json".startswith(type_prefix):
                return "application/json"
            # Then check other supported types
            for supported in sorted(supported_types):
                if supported.startswith(type_prefix):
                    return supported

    return None


class AcceptHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware that validates Accept header for HTTP content negotiation.

    This middleware ensures that clients request a supported response format.
    Requests with unsupported Accept headers are rejected with HTTP 406
    Not Acceptable.

    Attributes:
        supported_types: Set of acceptable media types (default: json, problem+json)
        exempt_paths: Paths that bypass Accept validation (health checks, etc.)
    """

    # Default paths exempt from Accept header validation
    # These are typically health checks, metrics, or WebSocket upgrade paths
    # Using frozenset for O(1) membership testing (immutable and hashable)
    DEFAULT_EXEMPT_PATHS: ClassVar[frozenset[str]] = frozenset(
        {
            "/",
            "/health",
            "/ready",
            "/api/system/health",
            "/api/system/health/ready",
            "/api/metrics",
        }
    )

    # Exempt path prefixes (e.g., WebSocket paths)
    DEFAULT_EXEMPT_PREFIXES: ClassVar[tuple[str, ...]] = (
        "/ws/",
        "/docs",
        "/redoc",
        "/openapi.json",
    )

    def __init__(
        self,
        app: ASGIApp,
        *,
        supported_types: set[str] | frozenset[str] | None = None,
        exempt_paths: set[str] | frozenset[str] | None = None,
        exempt_prefixes: tuple[str, ...] | None = None,
    ):
        """Initialize Accept header validation middleware.

        Args:
            app: FastAPI/Starlette application
            supported_types: Override default supported media types
            exempt_paths: Override default exempt paths (converted to frozenset for O(1) lookup)
            exempt_prefixes: Override default exempt path prefixes (tuple for optimized startswith)
        """
        super().__init__(app)
        self.supported_types: frozenset[str] = (
            frozenset(supported_types) if supported_types else SUPPORTED_MEDIA_TYPES
        )
        # Convert to frozenset for O(1) membership testing
        self.exempt_paths: frozenset[str] = (
            frozenset(exempt_paths) if exempt_paths is not None else self.DEFAULT_EXEMPT_PATHS
        )
        self.exempt_prefixes: tuple[str, ...] = (
            exempt_prefixes if exempt_prefixes is not None else self.DEFAULT_EXEMPT_PREFIXES
        )

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from Accept header validation.

        Optimized for high-throughput workloads:
        - O(1) lookup for exact path matches using frozenset
        - O(n) prefix matching using str.startswith(tuple) which is
          implemented in C and faster than Python-level any() iteration

        Args:
            path: Request URL path

        Returns:
            True if path is exempt, False otherwise
        """
        # Check exact matches - O(1) with frozenset
        if path in self.exempt_paths:
            return True

        # Check prefix matches using str.startswith(tuple) - C-level optimization
        # This is faster than any(path.startswith(p) for p in prefixes)
        return path.startswith(self.exempt_prefixes)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Validate Accept header and process request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response (either from validation failure or successful processing)
        """
        # Skip validation for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Get Accept header
        accept_header = request.headers.get("accept", "")

        # Parse Accept header
        accepted_types = parse_accept_header(accept_header)

        # Select best matching media type
        selected_type = select_best_media_type(accepted_types, self.supported_types)

        if selected_type is None:
            # Log the rejection
            logger.info(
                "Request rejected due to unsupported Accept header",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "accept_header": accept_header,
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )

            # Return 406 Not Acceptable with RFC 7807 Problem Details format
            supported_list = sorted(self.supported_types)
            return JSONResponse(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                content={
                    "type": "about:blank",
                    "title": "Not Acceptable",
                    "status": 406,
                    "detail": (
                        f"The requested media type '{accept_header}' is not supported. "
                        f"Supported types: {', '.join(supported_list)}"
                    ),
                    "instance": str(request.url.path),
                },
                media_type="application/problem+json",
            )

        # Store selected media type in request state for later use
        request.state.accepted_media_type = selected_type

        return await call_next(request)
