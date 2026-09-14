"""ETag support for conditional GET requests (NEM-3743).

This module provides ETag generation and validation utilities for implementing
HTTP caching with conditional requests (If-None-Match).

ETags enable:
1. **Reduced bandwidth**: 304 Not Modified responses for unchanged resources
2. **Client-side caching**: Browsers can cache responses and validate freshness
3. **Optimistic concurrency**: Detect concurrent modifications (If-Match)

ETag Strategies:
- **Content-based**: Hash of response body (accurate but requires full serialization)
- **Metadata-based**: Hash of version/updated_at fields (fast, good for DB records)

Usage:
    from backend.api.middleware.etag import (
        generate_etag,
        generate_etag_from_metadata,
        check_etag_match,
        etag_response,
    )

    @router.get("/events/{event_id}")
    async def get_event(
        event_id: int,
        request: Request,
    ):
        event = await get_event_from_db(event_id)

        # Generate ETag from metadata (fast)
        etag = generate_etag_from_metadata(event.id, event.updated_at)

        # Check If-None-Match header
        if check_etag_match(request, etag):
            return Response(status_code=304)

        return etag_response(EventResponse.model_validate(event), etag)
"""

import hashlib
from datetime import datetime
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Weak ETag prefix (allows semantic equivalence, not byte-for-byte match)
WEAK_PREFIX = 'W/"'
STRONG_PREFIX = '"'


def generate_etag(content: str | bytes, weak: bool = False) -> str:
    """Generate an ETag from content using SHA-256.

    Args:
        content: String or bytes to hash
        weak: If True, generate a weak ETag (W/"...")

    Returns:
        ETag string with proper formatting

    Example:
        >>> etag = generate_etag('{"id": 1, "name": "test"}')
        >>> # Returns: "a1b2c3d4..."
    """
    if isinstance(content, str):
        content = content.encode("utf-8")

    # Use first 16 bytes of SHA-256 (128 bits - sufficient for uniqueness)
    hash_value = hashlib.sha256(content).hexdigest()[:32]

    if weak:
        return f'W/"{hash_value}"'
    return f'"{hash_value}"'


def generate_etag_from_metadata(
    resource_id: int | str,
    updated_at: datetime | None = None,
    version: int | None = None,
) -> str:
    """Generate an ETag from resource metadata (fast, no serialization needed).

    This is preferred for database records where updated_at or version
    is tracked. Faster than content-based ETags since it doesn't require
    serializing the full response.

    Args:
        resource_id: Unique identifier for the resource
        updated_at: Last modification timestamp (preferred)
        version: Version number (alternative to updated_at)

    Returns:
        Weak ETag string

    Example:
        >>> etag = generate_etag_from_metadata(123, updated_at=datetime.now())
        >>> # Returns: W/"event-123-1705334400.123456"
    """
    if updated_at:
        timestamp = updated_at.timestamp()
        return f'W/"{resource_id}-{timestamp:.6f}"'
    elif version is not None:
        return f'W/"{resource_id}-v{version}"'
    else:
        # Fallback to just ID (not recommended - won't change on updates)
        return f'W/"{resource_id}"'


def generate_etag_from_model(model: BaseModel, weak: bool = True) -> str:
    """Generate an ETag from a Pydantic model.

    Serializes the model to JSON and hashes it. Slower than metadata-based
    ETags but ensures byte-level accuracy.

    Args:
        model: Pydantic model to hash
        weak: If True, generate a weak ETag (default)

    Returns:
        ETag string
    """
    content = model.model_dump_json(exclude_none=True)
    return generate_etag(content, weak=weak)


def generate_etag_from_list(
    items: list[Any],
    total: int | None = None,
    updated_at: datetime | None = None,
) -> str:
    """Generate an ETag for a list response.

    For list endpoints, ETags should reflect:
    1. The items in the list (by hashing IDs or first/last items)
    2. Total count (if pagination)
    3. Last modification time of any item (if tracked)

    Args:
        items: List of items (Pydantic models or dicts with 'id' key)
        total: Total count for pagination
        updated_at: Most recent updated_at among all items

    Returns:
        Weak ETag string
    """
    # Build a fingerprint of the list
    parts = []

    # Add count
    parts.append(f"n={len(items)}")

    if total is not None:
        parts.append(f"t={total}")

    # Add first and last IDs for quick change detection
    if items:
        first_id = items[0].id if hasattr(items[0], "id") else items[0].get("id")
        last_id = items[-1].id if hasattr(items[-1], "id") else items[-1].get("id")
        parts.append(f"f={first_id}")
        parts.append(f"l={last_id}")

    # Add latest update timestamp
    if updated_at:
        parts.append(f"u={updated_at.timestamp():.6f}")

    fingerprint = "|".join(parts)
    return generate_etag(fingerprint, weak=True)


def check_etag_match(request: Request, current_etag: str) -> bool:
    """Check if the request's If-None-Match header matches the current ETag.

    Handles:
    - Single ETag: If-None-Match: "abc123"
    - Multiple ETags: If-None-Match: "abc123", "def456"
    - Wildcard: If-None-Match: *

    Args:
        request: FastAPI request object
        current_etag: Current ETag value for the resource

    Returns:
        True if any client ETag matches (resource not modified)
    """
    if_none_match = request.headers.get("if-none-match")
    if not if_none_match:
        return False

    # Handle wildcard
    if if_none_match.strip() == "*":
        return True

    # Parse multiple ETags (comma-separated)
    client_etags = [e.strip() for e in if_none_match.split(",")]

    # Normalize current ETag for comparison
    current_normalized = _normalize_etag(current_etag)

    return any(_etags_match(client_etag, current_normalized) for client_etag in client_etags)


def check_if_match(request: Request, current_etag: str) -> bool:
    """Check if the request's If-Match header matches the current ETag.

    Used for optimistic concurrency control on PUT/PATCH/DELETE.
    If If-Match is present but doesn't match, return 412 Precondition Failed.

    Args:
        request: FastAPI request object
        current_etag: Current ETag value for the resource

    Returns:
        True if If-Match is not present OR if it matches current ETag
        False if If-Match is present but doesn't match (precondition failed)
    """
    if_match = request.headers.get("if-match")
    if not if_match:
        # No If-Match header means proceed without check
        return True

    # Handle wildcard (matches any existing resource)
    if if_match.strip() == "*":
        return True

    # Parse and compare
    client_etags = [e.strip() for e in if_match.split(",")]
    current_normalized = _normalize_etag(current_etag)

    for client_etag in client_etags:
        if _etags_match(client_etag, current_normalized, weak_comparison=False):
            return True

    return False


def _normalize_etag(etag: str) -> str:
    """Normalize an ETag by removing weak prefix and quotes."""
    etag = etag.strip()
    if etag.startswith('W/"') or etag.startswith('w/"'):
        etag = etag[3:-1]  # Remove W/" and trailing "
    elif etag.startswith('"') and etag.endswith('"'):
        etag = etag[1:-1]  # Remove surrounding quotes
    return etag


def _etags_match(client_etag: str, server_etag: str, weak_comparison: bool = True) -> bool:
    """Compare two ETags using weak or strong comparison.

    Weak comparison: Ignores W/ prefix, compares values
    Strong comparison: Requires exact match including W/ prefix
    """
    client_normalized = _normalize_etag(client_etag)
    server_normalized = (
        _normalize_etag(server_etag) if isinstance(server_etag, str) else server_etag
    )

    if weak_comparison:
        return client_normalized == server_normalized

    # Strong comparison - both must be strong ETags
    client_is_weak = client_etag.strip().startswith("W/") or client_etag.strip().startswith("w/")
    server_is_weak = isinstance(server_etag, str) and (
        server_etag.strip().startswith("W/") or server_etag.strip().startswith("w/")
    )

    if client_is_weak or server_is_weak:
        return False

    return client_normalized == server_normalized


def etag_response(
    content: BaseModel | dict[str, Any],
    etag: str,
    status_code: int = 200,
) -> Response:
    """Create a JSON response with ETag header.

    Args:
        content: Response content (Pydantic model or dict)
        etag: ETag value to include in response
        status_code: HTTP status code (default 200)

    Returns:
        JSONResponse with ETag header
    """
    if isinstance(content, BaseModel):
        body = content.model_dump(mode="json", exclude_none=True)
    else:
        body = content

    response = JSONResponse(content=body, status_code=status_code)
    response.headers["ETag"] = etag
    # Enable caching but require revalidation
    response.headers["Cache-Control"] = "private, must-revalidate"
    return response


def not_modified_response(etag: str) -> Response:
    """Create a 304 Not Modified response.

    Args:
        etag: ETag value to include (should match the cached version)

    Returns:
        Response with 304 status and ETag header
    """
    response = Response(status_code=304)
    response.headers["ETag"] = etag
    return response


__all__ = [
    "check_etag_match",
    "check_if_match",
    "etag_response",
    "generate_etag",
    "generate_etag_from_list",
    "generate_etag_from_metadata",
    "generate_etag_from_model",
    "not_modified_response",
]
