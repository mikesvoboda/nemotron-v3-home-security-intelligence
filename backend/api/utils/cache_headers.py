"""HTTP cache header utilities for GET endpoints.

This module provides utilities for setting appropriate HTTP cache headers
on API responses to improve performance and enable client-side caching.

Cache-Control Directives Reference:
- max-age: How long (in seconds) the response can be cached
- no-cache: Response can be cached but must revalidate on each use
- no-store: Response must not be cached anywhere
- private: Response is specific to user, can only be cached by browser
- public: Response can be cached by any cache (CDN, proxy, browser)
- must-revalidate: Once stale, cache must revalidate before using

See RFC 7234 for the full HTTP caching specification.
"""

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Response


class CacheStrategy(Enum):
    """Cache strategies for different endpoint types.

    Each strategy maps to specific Cache-Control directives appropriate
    for the data characteristics of that endpoint type.
    """

    # Static configuration that rarely changes - 5 minutes
    STATIC_CONFIG = "max-age=300, private"

    # Relatively stable data like camera list - 1 minute
    STABLE = "max-age=60, private"

    # Aggregate/computed data like stats - 1 minute
    STATS = "max-age=60, private"

    # Frequently changing data - revalidate on each request
    DYNAMIC = "no-cache"

    # Immutable data (events/detections after creation) - 1 hour
    IMMUTABLE = "max-age=3600, private"

    # Media files that don't change - 1 hour, cacheable by CDN
    MEDIA = "max-age=3600, public"

    # Real-time data that should never be cached
    REALTIME = "no-store"


def set_cache_headers(response: Response, strategy: CacheStrategy) -> None:
    """Set Cache-Control headers on a FastAPI response.

    Args:
        response: FastAPI Response object
        strategy: CacheStrategy enum value determining cache behavior

    Example:
        @router.get("/config")
        async def get_config(response: Response) -> ConfigResponse:
            set_cache_headers(response, CacheStrategy.STATIC_CONFIG)
            return ConfigResponse(...)
    """
    response.headers["Cache-Control"] = strategy.value


def set_no_cache(response: Response) -> None:
    """Set no-cache headers for dynamic data that changes frequently.

    Data can be cached but must revalidate on each request.
    Use for event lists, search results, etc.

    Args:
        response: FastAPI Response object
    """
    response.headers["Cache-Control"] = CacheStrategy.DYNAMIC.value


def set_no_store(response: Response) -> None:
    """Set no-store headers for real-time data.

    Data must never be cached anywhere.
    Use for GPU stats, telemetry, health checks.

    Args:
        response: FastAPI Response object
    """
    response.headers["Cache-Control"] = CacheStrategy.REALTIME.value


def set_immutable_cache(response: Response) -> None:
    """Set cache headers for immutable resources.

    Resources that don't change after creation (events, detections).
    Cached for 1 hour with private visibility.

    Args:
        response: FastAPI Response object
    """
    response.headers["Cache-Control"] = CacheStrategy.IMMUTABLE.value


def set_media_cache(response: Response) -> None:
    """Set cache headers for media files.

    Static media files (images, thumbnails, video clips).
    Cached for 1 hour with public visibility (CDN-cacheable).

    Args:
        response: FastAPI Response object
    """
    response.headers["Cache-Control"] = CacheStrategy.MEDIA.value
