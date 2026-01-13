"""Cursor-based pagination utilities.

This module provides utilities for cursor-based pagination, which offers better
performance for large datasets compared to offset-based pagination.

Cursor pagination works by:
1. Encoding the position of the last item as an opaque cursor string
2. Using that cursor to efficiently fetch the next page using indexed columns
3. Avoiding the performance degradation of OFFSET for large offsets

Usage:
    # Creating a cursor from the last item in a response
    cursor_data = CursorData(id=event.id, created_at=event.started_at)
    next_cursor = encode_cursor(cursor_data)

    # Decoding a cursor from a request
    cursor_data = decode_cursor(request_cursor)
    if cursor_data:
        query = query.where(Event.id < cursor_data.id)
"""

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class CursorData:
    """Data structure for pagination cursor.

    Attributes:
        id: The ID of the last item (used for cursor position)
        created_at: The timestamp of the last item (for tie-breaking)
    """

    id: int
    created_at: datetime


def encode_cursor(cursor_data: CursorData) -> str:
    """Encode cursor data to a base64 URL-safe string.

    Args:
        cursor_data: CursorData containing id and created_at

    Returns:
        Base64 URL-safe encoded cursor string
    """
    payload = {
        "id": cursor_data.id,
        "created_at": cursor_data.created_at.isoformat(),
    }
    json_str = json.dumps(payload)
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str | None) -> CursorData | None:
    """Decode a cursor string back to CursorData.

    Args:
        cursor: Base64 URL-safe encoded cursor string, or None/empty

    Returns:
        CursorData if valid cursor provided, None if cursor is None/empty

    Raises:
        ValueError: If cursor is invalid (bad encoding, missing fields, etc.)
    """
    if not cursor:
        return None

    try:
        # Decode base64
        json_bytes = base64.urlsafe_b64decode(cursor)
        payload = json.loads(json_bytes)

        # Validate required fields
        if "id" not in payload:
            raise ValueError("Invalid cursor: missing 'id' field")
        if "created_at" not in payload:
            raise ValueError("Invalid cursor: missing 'created_at' field")

        # Parse datetime
        created_at_str = payload["created_at"]
        # Handle both with and without timezone info
        if created_at_str.endswith("Z"):
            created_at_str = created_at_str[:-1] + "+00:00"
        created_at = datetime.fromisoformat(created_at_str)

        # Ensure timezone awareness (use UTC if naive)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        return CursorData(
            id=int(payload["id"]),
            created_at=created_at,
        )
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Invalid cursor: {e}") from e
    except Exception as e:
        raise ValueError(f"Invalid cursor: {e}") from e


def validate_pagination_params(cursor: str | None, offset: int | None) -> None:
    """Validate that offset and cursor pagination are not used simultaneously.

    This function should be called at the start of paginated endpoints to ensure
    clients don't provide conflicting pagination parameters.

    Args:
        cursor: The cursor parameter from the request
        offset: The offset parameter from the request

    Raises:
        ValueError: If both offset (non-zero) and cursor are provided
    """
    # Check if both cursor and non-zero offset are provided
    # Handle case where offset might be a Query object in direct function calls (tests)
    offset_value = offset if isinstance(offset, int) else 0
    if cursor is not None and offset_value > 0:
        raise ValueError("Cannot use both 'offset' and 'cursor' pagination. Choose one.")


def get_deprecation_warning(cursor: str | None, offset: int) -> str | None:
    """Get deprecation warning message if offset pagination is used without cursor.

    Args:
        cursor: The cursor parameter from the request
        offset: The offset parameter from the request

    Returns:
        Deprecation warning message if offset is used without cursor, None otherwise
    """
    # No warning if cursor is provided (cursor takes precedence)
    if cursor:
        return None

    # No warning if offset is 0 (default value)
    if offset == 0:
        return None

    # Warn about deprecated offset pagination
    return (
        "Offset pagination is deprecated and will be removed in a future version. "
        "Please use cursor-based pagination instead by using the 'cursor' parameter "
        "with the 'next_cursor' value from the response."
    )
