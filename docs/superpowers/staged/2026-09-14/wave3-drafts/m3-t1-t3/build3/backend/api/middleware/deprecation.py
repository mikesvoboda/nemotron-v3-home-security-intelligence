"""RFC 8594 Deprecation and Sunset headers middleware.

This module implements HTTP middleware for API endpoint deprecation per RFC 8594:
- Deprecation header: Indicates an endpoint is deprecated
  - `Deprecation: true` when no specific date
  - `Deprecation: @<unix-timestamp>` when deprecation date is known
- Sunset header: Indicates when the endpoint will be removed (HTTP-date format per RFC 7231)
- Link header: Optional documentation link with rel="deprecation"

RFC 8594: https://www.rfc-editor.org/rfc/rfc8594.html
RFC 7231 HTTP-date: https://www.rfc-editor.org/rfc/rfc7231.html#section-7.1.1.1

Usage:
    from backend.api.middleware.deprecation import (
        DeprecatedEndpoint,
        DeprecationConfig,
        DeprecationMiddleware,
    )

    config = DeprecationConfig()
    config.register(
        DeprecatedEndpoint(
            path="/api/v1/old-endpoint",
            sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            deprecated_at=datetime(2024, 1, 1, tzinfo=UTC),
            replacement="/api/v2/new-endpoint",
            link="https://docs.example.com/migration",
        )
    )

    app.add_middleware(DeprecationMiddleware, config=config)
"""

from __future__ import annotations

import fnmatch
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


def format_http_date(dt: datetime) -> str:
    """Format a datetime as HTTP-date per RFC 7231.

    HTTP-date format: "day-name, DD Mon YYYY HH:MM:SS GMT"
    Example: "Sun, 01 Jun 2025 00:00:00 GMT"

    Args:
        dt: datetime to format (naive datetimes treated as UTC)

    Returns:
        HTTP-date formatted string
    """
    # Ensure datetime is in UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    elif dt.tzinfo != UTC:
        dt = dt.astimezone(UTC)

    # Format as HTTP-date
    # %a = abbreviated weekday name
    # %d = day of month (zero-padded)
    # %b = abbreviated month name
    # %Y = year
    # %H:%M:%S = time
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def format_unix_timestamp(dt: datetime) -> str:
    """Format a datetime as Unix timestamp with @ prefix for Deprecation header.

    RFC 8594 allows `Deprecation: @<unix-timestamp>` to indicate when
    deprecation was announced.

    Args:
        dt: datetime to format (naive datetimes treated as UTC)

    Returns:
        String in format "@<unix-timestamp>"
    """
    # Ensure datetime is in UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    elif dt.tzinfo != UTC:
        dt = dt.astimezone(UTC)

    timestamp = int(dt.timestamp())
    return f"@{timestamp}"


@dataclass
class DeprecatedEndpoint:
    """Configuration for a deprecated API endpoint.

    Attributes:
        path: URL path pattern (exact or wildcard with *)
        sunset_date: When the endpoint will be removed (required)
        deprecated_at: When deprecation was announced (optional)
        replacement: Replacement endpoint path (optional)
        link: Documentation URL for migration guide (optional)
    """

    path: str
    sunset_date: datetime
    deprecated_at: datetime | None = None
    replacement: str | None = None
    link: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the endpoint configuration."""
        # Normalize path - remove trailing slash for consistency
        if self.path.endswith("/") and len(self.path) > 1:
            self.path = self.path.rstrip("/")


@dataclass
class DeprecationConfig:
    """Registry for deprecated endpoints.

    Supports both exact path matching and wildcard patterns:
    - Exact: "/api/v1/cameras" matches only that path
    - Wildcard: "/api/v1/*" matches any path starting with /api/v1/

    Exact matches take priority over wildcard patterns.
    """

    _endpoints: list[DeprecatedEndpoint] = field(default_factory=list)

    def register(self, endpoint: DeprecatedEndpoint) -> None:
        """Register a deprecated endpoint.

        Args:
            endpoint: DeprecatedEndpoint configuration to register
        """
        self._endpoints.append(endpoint)

    def get_deprecated_endpoints(self) -> list[DeprecatedEndpoint]:
        """Get all registered deprecated endpoints.

        Returns:
            List of DeprecatedEndpoint configurations
        """
        return list(self._endpoints)

    def match(self, path: str) -> DeprecatedEndpoint | None:
        """Find a matching deprecated endpoint for the given path.

        Exact matches take priority over wildcard patterns.

        Args:
            path: URL path to match (query string should be stripped)

        Returns:
            DeprecatedEndpoint if path matches, None otherwise
        """
        # Normalize path
        normalized_path = path.rstrip("/") if len(path) > 1 else path

        # First, look for exact matches
        for endpoint in self._endpoints:
            if not endpoint.path.endswith("*") and endpoint.path == normalized_path:
                return endpoint

        # Then, look for wildcard matches
        for endpoint in self._endpoints:
            if endpoint.path.endswith("*"):
                # Convert wildcard pattern to fnmatch pattern
                pattern = endpoint.path
                if fnmatch.fnmatch(normalized_path, pattern):
                    return endpoint

        return None

    def clear(self) -> None:
        """Remove all registered endpoints."""
        self._endpoints.clear()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeprecationConfig:
        """Create a DeprecationConfig from a dictionary.

        Expected format:
        {
            "endpoints": [
                {
                    "path": "/api/v1/old",
                    "sunset_date": "2025-06-01T00:00:00Z",
                    "deprecated_at": "2024-01-01T00:00:00Z",  # optional
                    "replacement": "/api/v2/new",  # optional
                    "link": "https://docs.example.com/migration"  # optional
                }
            ]
        }

        Args:
            data: Dictionary containing endpoint configurations

        Returns:
            Configured DeprecationConfig instance
        """
        config = cls()

        for endpoint_data in data.get("endpoints", []):
            # Parse dates from ISO format strings
            sunset_date = datetime.fromisoformat(
                endpoint_data["sunset_date"].replace("Z", "+00:00")
            )

            deprecated_at = None
            deprecated_at_str = endpoint_data.get("deprecated_at")
            if deprecated_at_str:
                deprecated_at = datetime.fromisoformat(deprecated_at_str.replace("Z", "+00:00"))

            endpoint = DeprecatedEndpoint(
                path=endpoint_data["path"],
                sunset_date=sunset_date,
                deprecated_at=deprecated_at,
                replacement=endpoint_data.get("replacement"),
                link=endpoint_data.get("link"),
            )
            config.register(endpoint)

        return config


class DeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware that adds RFC 8594 Deprecation and Sunset headers.

    For deprecated endpoints, adds:
    - Deprecation: `true` or `@<unix-timestamp>` when deprecation date is known
    - Sunset: HTTP-date when the endpoint will be removed
    - Link: Optional documentation link with rel="deprecation"

    Non-deprecated endpoints are passed through without modification.

    Attributes:
        config: DeprecationConfig registry of deprecated endpoints
    """

    def __init__(
        self,
        app: ASGIApp,
        config: DeprecationConfig | None = None,
    ):
        """Initialize deprecation middleware.

        Args:
            app: FastAPI/Starlette application
            config: DeprecationConfig registry (default: empty config)
        """
        super().__init__(app)
        self.config = config or DeprecationConfig()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Add deprecation headers if the request path matches a deprecated endpoint.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response with deprecation headers added if applicable
        """
        # Get the response first
        response = await call_next(request)

        # Check if the path matches a deprecated endpoint
        path = request.url.path
        endpoint = self.config.match(path)

        if endpoint is not None:
            # Add Deprecation header
            if endpoint.deprecated_at is not None:
                response.headers["Deprecation"] = format_unix_timestamp(endpoint.deprecated_at)
            else:
                response.headers["Deprecation"] = "true"

            # Add Sunset header
            response.headers["Sunset"] = format_http_date(endpoint.sunset_date)

            # Add Link header if documentation link is provided
            if endpoint.link:
                # RFC 8288 Web Linking format
                link_value = f'<{endpoint.link}>; rel="deprecation"'

                # Append to existing Link header if present
                existing_link = response.headers.get("Link")
                if existing_link:
                    response.headers["Link"] = f"{existing_link}, {link_value}"
                else:
                    response.headers["Link"] = link_value

        return response
