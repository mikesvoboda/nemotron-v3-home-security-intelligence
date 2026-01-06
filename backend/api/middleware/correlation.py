"""Correlation ID helpers for outgoing HTTP requests.

This module provides utilities for propagating correlation IDs to outgoing
HTTP requests when calling external services (RT-DETR, Nemotron, etc.).

NEM-1472: Correlation ID propagation to AI service HTTP clients

Usage:
    from backend.api.middleware.correlation import get_correlation_headers

    # In your HTTP client code:
    headers = {"Content-Type": "application/json"}
    headers.update(get_correlation_headers())

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
"""

from typing import Any

from backend.api.middleware.request_id import get_correlation_id
from backend.core.logging import get_request_id


def get_correlation_headers() -> dict[str, str]:
    """Get headers for propagating correlation ID to outgoing requests.

    This function retrieves the current correlation ID from context and
    returns a dictionary of headers that should be included in outgoing
    HTTP requests to propagate the correlation chain.

    Returns:
        Dictionary with X-Correlation-ID header if set, empty dict otherwise.

    Example:
        >>> from backend.api.middleware.correlation import get_correlation_headers
        >>>
        >>> headers = {"Content-Type": "application/json"}
        >>> headers.update(get_correlation_headers())
        >>>
        >>> async with httpx.AsyncClient() as client:
        ...     response = await client.post(url, headers=headers, json=data)
    """
    headers: dict[str, str] = {}

    # Get correlation ID from context
    correlation_id = get_correlation_id()
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    # Also propagate request ID if available (some services may use this)
    request_id = get_request_id()
    if request_id:
        headers["X-Request-ID"] = request_id

    return headers


def merge_headers_with_correlation(
    existing_headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge existing headers with correlation headers.

    Convenience function that takes existing headers and adds correlation
    headers to them. Creates a new dict to avoid mutating the input.

    Args:
        existing_headers: Optional existing headers dictionary

    Returns:
        New dictionary with original headers plus correlation headers
    """
    headers: dict[str, Any] = dict(existing_headers) if existing_headers else {}
    headers.update(get_correlation_headers())
    return headers
