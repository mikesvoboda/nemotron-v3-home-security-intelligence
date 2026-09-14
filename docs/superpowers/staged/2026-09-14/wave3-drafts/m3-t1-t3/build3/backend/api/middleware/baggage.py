"""OpenTelemetry Baggage middleware for cross-service context propagation.

NEM-3796: This middleware extracts incoming baggage from HTTP headers and sets
application-specific context for propagation across service boundaries in the
detection pipeline.

Baggage Keys:
- camera.id: Source camera for detection pipeline
- event.priority: Priority level for downstream processing (low, normal, high, critical)
- request.source: Origin of request (ui, api, scheduled, internal)

Baggage is propagated via the W3C Baggage header format:
    baggage: camera.id=front_door,event.priority=high,request.source=api

Usage:
    # In your FastAPI app
    app.add_middleware(BaggageMiddleware)

    # In services, read baggage context
    from backend.api.middleware.baggage import (
        get_camera_id_from_baggage,
        get_event_priority_from_baggage,
        get_request_source_from_baggage,
    )

    camera_id = get_camera_id_from_baggage()
    priority = get_event_priority_from_baggage()

    # Set pipeline context at the start of processing
    from backend.api.middleware.baggage import set_pipeline_baggage
    set_pipeline_baggage(camera_id="front_door", event_priority="high")
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.telemetry import (
    extract_context_from_headers,
    get_baggage,
    set_baggage,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Valid values for event.priority baggage
VALID_PRIORITIES = frozenset({"low", "normal", "high", "critical"})

# Valid values for request.source baggage
VALID_REQUEST_SOURCES = frozenset({"ui", "api", "scheduled", "internal"})

# Regex pattern to extract camera_id from URL paths
# Matches patterns like /cameras/{camera_id}/, /api/cameras/{camera_id}/, etc.
CAMERA_ID_PATH_PATTERN = re.compile(r"/cameras/([^/]+)(?:/|$)")


class BaggageMiddleware(BaseHTTPMiddleware):
    """Middleware for OpenTelemetry Baggage propagation.

    This middleware:
    1. Extracts incoming baggage from W3C Baggage headers
    2. Sets application-specific baggage (camera.id, event.priority, request.source)
    3. Propagates baggage to downstream services via response headers

    The baggage is automatically included in outgoing HTTP requests when using
    get_correlation_headers() from the correlation middleware.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the baggage middleware.

        Args:
            app: The ASGI application to wrap
        """
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with baggage context.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response
        """
        # Extract incoming trace context and baggage from headers
        headers = dict(request.headers)
        extract_context_from_headers(headers)

        # Set request.source based on X-Request-Source header or default to 'api'
        request_source = self._determine_request_source(request)
        set_baggage("request.source", request_source)

        # Extract camera_id from URL path if present and not already in baggage
        camera_id = self._extract_camera_id_from_path(request)
        if camera_id:
            # Only set if not already present from upstream
            existing_camera_id = get_baggage("camera.id")
            if not existing_camera_id:
                set_baggage("camera.id", camera_id)
                logger.debug(
                    "Set camera.id baggage from URL path",
                    extra={"camera.id": camera_id, "path": request.url.path},
                )

        # Log baggage context for debugging (at debug level to avoid noise)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Baggage context established",
                extra={
                    "request.source": request_source,
                    "camera.id": get_baggage("camera.id"),
                    "event.priority": get_baggage("event.priority"),
                    "path": request.url.path,
                },
            )

        # Process the request
        response: Response = await call_next(request)

        return response

    def _determine_request_source(self, request: Request) -> str:
        """Determine the request source from headers.

        Args:
            request: The incoming HTTP request

        Returns:
            The request source: 'ui', 'api', 'scheduled', or 'internal'
        """
        # Check for explicit X-Request-Source header
        source_header = request.headers.get("x-request-source", "").lower()

        if source_header in VALID_REQUEST_SOURCES:
            return source_header

        # Default to 'api' for HTTP requests without explicit source
        return "api"

    def _extract_camera_id_from_path(self, request: Request) -> str | None:
        """Extract camera_id from the URL path if present.

        Matches patterns like:
        - /cameras/{camera_id}
        - /api/cameras/{camera_id}/detect
        - /api/cameras/{camera_id}/zones

        Args:
            request: The incoming HTTP request

        Returns:
            The camera_id if found in the path, None otherwise
        """
        path = request.url.path
        match = CAMERA_ID_PATH_PATTERN.search(path)
        if match:
            return match.group(1)
        return None


def set_pipeline_baggage(
    *,
    camera_id: str | None = None,
    event_priority: str | None = None,
    request_source: str | None = None,
    batch_id: str | None = None,
) -> None:
    """Set pipeline-specific baggage for cross-service propagation.

    This is a convenience function for setting multiple baggage entries
    commonly used in the detection pipeline.

    Args:
        camera_id: The camera identifier (e.g., "front_door", "backyard")
        event_priority: Priority level for processing (low, normal, high, critical)
        request_source: Origin of request (ui, api, scheduled, internal)
        batch_id: Optional batch identifier for batch processing

    Example:
        >>> from backend.api.middleware.baggage import set_pipeline_baggage
        >>> set_pipeline_baggage(
        ...     camera_id="front_door",
        ...     event_priority="high",
        ...     request_source="api"
        ... )
    """
    if camera_id:
        set_baggage("camera.id", camera_id)

    if event_priority:
        if event_priority in VALID_PRIORITIES:
            set_baggage("event.priority", event_priority)
        else:
            logger.warning(
                f"Invalid event_priority value: {event_priority}. "
                f"Valid values are: {', '.join(sorted(VALID_PRIORITIES))}"
            )

    if request_source:
        if request_source in VALID_REQUEST_SOURCES:
            set_baggage("request.source", request_source)
        else:
            logger.warning(
                f"Invalid request_source value: {request_source}. "
                f"Valid values are: {', '.join(sorted(VALID_REQUEST_SOURCES))}"
            )

    if batch_id:
        set_baggage("batch.id", batch_id)


def get_camera_id_from_baggage() -> str | None:
    """Get the camera.id from current baggage context.

    Returns:
        The camera ID if set, None otherwise.

    Example:
        >>> from backend.api.middleware.baggage import get_camera_id_from_baggage
        >>> camera_id = get_camera_id_from_baggage()
        >>> if camera_id:
        ...     print(f"Processing for camera: {camera_id}")
    """
    return get_baggage("camera.id")


def get_event_priority_from_baggage() -> str | None:
    """Get the event.priority from current baggage context.

    Returns:
        The event priority (low, normal, high, critical) if set, None otherwise.

    Example:
        >>> from backend.api.middleware.baggage import get_event_priority_from_baggage
        >>> priority = get_event_priority_from_baggage()
        >>> if priority == "high":
        ...     # Fast-track processing
        ...     pass
    """
    return get_baggage("event.priority")


def get_request_source_from_baggage() -> str | None:
    """Get the request.source from current baggage context.

    Returns:
        The request source (ui, api, scheduled, internal) if set, None otherwise.

    Example:
        >>> from backend.api.middleware.baggage import get_request_source_from_baggage
        >>> source = get_request_source_from_baggage()
        >>> if source == "scheduled":
        ...     # Scheduled task, can use lower priority
        ...     pass
    """
    return get_baggage("request.source")


def get_batch_id_from_baggage() -> str | None:
    """Get the batch.id from current baggage context.

    Returns:
        The batch ID if set, None otherwise.

    Example:
        >>> from backend.api.middleware.baggage import get_batch_id_from_baggage
        >>> batch_id = get_batch_id_from_baggage()
        >>> if batch_id:
        ...     print(f"Processing batch: {batch_id}")
    """
    return get_baggage("batch.id")
