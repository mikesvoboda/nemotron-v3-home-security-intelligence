"""Cursor-based pagination utilities.

This module provides utilities for cursor-based pagination, which offers better
performance for large datasets compared to offset-based pagination.

Cursor pagination works by:
1. Encoding the position of the last item as an opaque cursor string
2. Using that cursor to efficiently fetch the next page using indexed columns
3. Avoiding the performance degradation of OFFSET for large offsets

Security:
- Cursors are validated against injection attacks (NEM-2602)
- Length limits prevent resource exhaustion from oversized cursors
- Datetime bounds prevent unreasonable timestamp injection
- All validation failures are logged for security monitoring

Usage:
    # Creating a cursor from the last item in a response
    cursor_data = CursorData(id=event.id, created_at=event.started_at)
    next_cursor = encode_cursor(cursor_data)

    # Decoding a cursor from a request
    cursor_data = decode_cursor(request_cursor)
    if cursor_data:
        query = query.where(Event.id < cursor_data.id)
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
<<<<<<< HEAD
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.core.logging import get_logger, sanitize_log_value

# Security configuration for cursor validation (NEM-2602)
# Maximum length of base64-encoded cursor string (prevents resource exhaustion)
# A typical cursor with id + created_at is ~80-100 chars when base64 encoded
# 512 chars provides ample headroom while preventing abuse
MAX_CURSOR_LENGTH = 512

# Reasonable datetime bounds for cursor validation
# These prevent injection of extreme timestamps that could cause issues
# MIN: 2020-01-01 - Before this system existed
# MAX: 2100-01-01 - Reasonable future bound
MIN_CURSOR_DATETIME = datetime(2020, 1, 1, tzinfo=UTC)
MAX_CURSOR_DATETIME = datetime(2100, 1, 1, tzinfo=UTC)

# Maximum ID value (PostgreSQL bigint max)
MAX_CURSOR_ID = 2**63 - 1

# Valid cursor directions for pagination
VALID_CURSOR_DIRECTIONS = frozenset({"forward", "backward"})

logger = get_logger(__name__)


class CursorValidationModel(BaseModel):
    """Pydantic validation model for decoded cursor data (NEM-2602).

    This model provides strict validation of cursor data to prevent injection attacks.
    All fields are validated for type, range, and format.

    Attributes:
        id: The ID of the last item (must be positive integer)
        created_at: ISO datetime string of the last item (must be within reasonable bounds)
        direction: Optional pagination direction (forward/backward)
    """

    id: int = Field(..., gt=0, le=MAX_CURSOR_ID, description="Cursor position ID")
    created_at: str = Field(..., description="ISO formatted datetime string")
    direction: Literal["forward", "backward"] | None = Field(
        default=None, description="Pagination direction"
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: int) -> int:
        """Validate ID is a positive integer within bounds."""
        if not isinstance(v, int):
            raise ValueError("id must be an integer")
        if v <= 0:
            raise ValueError("id must be positive")
        if v > MAX_CURSOR_ID:
            raise ValueError(f"id exceeds maximum allowed value ({MAX_CURSOR_ID})")
        return v

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: str) -> str:
        """Validate created_at is a valid ISO datetime within reasonable bounds."""
        if not isinstance(v, str):
            raise ValueError("created_at must be a string")
        if len(v) > 50:  # ISO datetime should never exceed ~30 chars
            raise ValueError("created_at format is invalid (too long)")
        return v


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.responses import Response

# Regular expression for valid base64url cursor format (NEM-2585)
# Cursors are base64url-encoded strings (RFC 4648) containing:
# - Alphanumeric characters (a-z, A-Z, 0-9)
# - URL-safe characters: underscore (_) and hyphen (-)
# - Padding character: equals (=)
CURSOR_FORMAT_REGEX = re.compile(r"^[a-zA-Z0-9_=-]+$")

# Maximum allowed cursor length to prevent DoS via oversized cursors
# Base64-encoded JSON payload {"id": <int>, "created_at": "<ISO8601>"}
# should not exceed 200 characters in normal operation
MAX_CURSOR_LENGTH = 500


@dataclass
class CursorData:
    """Data structure for pagination cursor.

    Attributes:
        id: The ID of the last item (used for cursor position)
        created_at: The timestamp of the last item (for tie-breaking)
        direction: Optional pagination direction (forward/backward)
    """

    id: int
    created_at: datetime
    direction: str | None = None


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


def validate_cursor_format(cursor: str | None) -> bool:
    """Validate the format of a pagination cursor (NEM-2585).

    This function performs security-focused validation of cursor format
    before attempting to decode. It checks:
    1. Cursor is not too long (DoS prevention)
    2. Cursor contains only valid base64url characters

    This validation happens BEFORE base64 decoding to reject malformed
    cursors early and prevent potential injection attacks.

    Args:
        cursor: The cursor string to validate, or None/empty

    Returns:
        True if the cursor format is valid or cursor is None/empty

    Raises:
        ValueError: If the cursor format is invalid (bad characters, too long)

    Example:
        >>> validate_cursor_format(None)  # Returns True
        >>> validate_cursor_format("")  # Returns True
        >>> validate_cursor_format("eyJpZCI6MTIzfQ==")  # Returns True
        >>> validate_cursor_format("<script>")  # Raises ValueError
    """
    # No cursor is valid (first page or no pagination)
    if not cursor:
        return True

    # Check for maximum length to prevent DoS
    if len(cursor) > MAX_CURSOR_LENGTH:
        _log_suspicious_cursor(
            cursor, f"Cursor exceeds maximum length ({len(cursor)} > {MAX_CURSOR_LENGTH})"
        )
        raise ValueError(f"Cursor exceeds maximum length of {MAX_CURSOR_LENGTH} characters")

    # Check for valid base64url format
    if not CURSOR_FORMAT_REGEX.match(cursor):
        _log_suspicious_cursor(cursor, "Cursor contains invalid characters")
        raise ValueError("Cursor contains invalid characters (must be base64url-encoded)")

    return True


def _log_suspicious_cursor(cursor: str, reason: str, error: Exception | None = None) -> None:
    """Log suspicious cursor validation failures for security monitoring (NEM-2602).

    This function logs validation failures that may indicate injection attempts
    or malicious input. The cursor value is sanitized before logging to prevent
    log injection attacks.

    Args:
        cursor: The cursor string that failed validation
        reason: Description of why validation failed
        error: Optional exception that caused the failure
    """
    # Truncate cursor for logging (avoid log bloat from oversized inputs)
    truncated_cursor = cursor[:100] + "..." if len(cursor) > 100 else cursor
    sanitized_cursor = sanitize_log_value(truncated_cursor)

    logger.warning(
        "Suspicious cursor validation failure",
        extra={
            "security_event": "cursor_validation_failure",
            "reason": reason,
            "cursor_preview": sanitized_cursor,
            "cursor_length": len(cursor),
            "error_type": type(error).__name__ if error else None,
        },
    )


def _validate_cursor_id_type(cursor: str, raw_id: object) -> None:
    """Validate that the cursor ID is a proper integer type (NEM-2602).

    Args:
        cursor: The original cursor string (for logging)
        raw_id: The raw ID value from the JSON payload

    Raises:
        ValueError: If the ID is not a valid integer type
    """
    # Reject boolean (bool is subclass of int in Python, check explicitly)
    if isinstance(raw_id, bool):
        _log_suspicious_cursor(cursor, "Invalid id type: boolean")
        raise ValueError("Invalid cursor: id must be an integer, not boolean")
    if not isinstance(raw_id, int):
        _log_suspicious_cursor(cursor, f"Invalid id type: {type(raw_id).__name__}")
        raise ValueError("Invalid cursor: id must be an integer")


def _parse_and_validate_datetime(cursor: str, created_at_str: str) -> datetime:
    """Parse and validate the cursor datetime with bounds checking (NEM-2602).

    Args:
        cursor: The original cursor string (for logging)
        created_at_str: The datetime string from the cursor

    Returns:
        A timezone-aware datetime object

    Raises:
        ValueError: If the datetime is invalid or out of bounds
    """
    # Handle both with and without timezone info
    if created_at_str.endswith("Z"):
        created_at_str = created_at_str[:-1] + "+00:00"

    try:
        created_at = datetime.fromisoformat(created_at_str)
    except ValueError as e:
        _log_suspicious_cursor(cursor, f"Invalid datetime format: {created_at_str}", e)
        raise ValueError("Invalid cursor: invalid datetime format") from e

    # Ensure timezone awareness (use UTC if naive)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    # Bounds checking for datetime (NEM-2602)
    if created_at < MIN_CURSOR_DATETIME:
        _log_suspicious_cursor(
            cursor,
            f"Datetime before minimum bound: {created_at.isoformat()}",
        )
        raise ValueError(f"Invalid cursor: datetime before {MIN_CURSOR_DATETIME.year}")

    if created_at > MAX_CURSOR_DATETIME:
        _log_suspicious_cursor(
            cursor,
            f"Datetime after maximum bound: {created_at.isoformat()}",
        )
        raise ValueError(f"Invalid cursor: datetime after {MAX_CURSOR_DATETIME.year}")

    return created_at


def decode_cursor(cursor: str | None) -> CursorData | None:
    """Decode a cursor string back to CursorData with strict validation (NEM-2602).

    This function decodes base64-encoded cursor strings and validates the
    decoded data against injection attacks. Validation includes:
    - Length limit check (prevents resource exhaustion)
    - Base64 format validation
    - JSON structure validation
    - Required field presence check
    - ID range validation (positive integer, within PostgreSQL bigint bounds)
    - Datetime format and bounds validation
    - Direction value validation (if present)

    All validation failures are logged for security monitoring.

    Args:
        cursor: Base64 URL-safe encoded cursor string, or None/empty

    Returns:
        CursorData if valid cursor provided, None if cursor is None/empty

    Raises:
        ValueError: If cursor is invalid (bad encoding, missing fields,
            out-of-bounds values, invalid direction, etc.)
    """
    if not cursor:
        return None

    # Validate cursor format before attempting decode (NEM-2585)
    validate_cursor_format(cursor)

    # Security check: Length limit to prevent resource exhaustion (NEM-2602)
    if len(cursor) > MAX_CURSOR_LENGTH:
        _log_suspicious_cursor(
            cursor,
            f"Cursor exceeds maximum length ({len(cursor)} > {MAX_CURSOR_LENGTH})",
        )
        raise ValueError(f"Invalid cursor: exceeds maximum length ({MAX_CURSOR_LENGTH} characters)")

    try:
        # Decode base64
        try:
            json_bytes = base64.urlsafe_b64decode(cursor)
        except Exception as e:
            _log_suspicious_cursor(cursor, "Invalid base64 encoding", e)
            raise ValueError("Invalid cursor: malformed encoding") from e

        # Parse JSON
        try:
            payload = json.loads(json_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _log_suspicious_cursor(cursor, "Invalid JSON structure", e)
            raise ValueError("Invalid cursor: malformed structure") from e

        # Ensure payload is a dict (not list, string, etc.)
        if not isinstance(payload, dict):
            _log_suspicious_cursor(cursor, f"Unexpected payload type: {type(payload).__name__}")
            raise ValueError("Invalid cursor: unexpected data format")

        # Pre-validation type checks for strict type enforcement (NEM-2602)
        # JSON doesn't differentiate bool from int, and floats vs ints, so we check here
        raw_id = payload.get("id")
        _validate_cursor_id_type(cursor, raw_id)

        # Validate using Pydantic model for strict type checking (NEM-2602)
        try:
            validated = CursorValidationModel(
                id=raw_id,
                created_at=payload.get("created_at"),
                direction=payload.get("direction"),
            )
        except Exception as e:
            _log_suspicious_cursor(cursor, f"Pydantic validation failed: {e}", e)
            raise ValueError(f"Invalid cursor: {e}") from e

        # Parse and validate datetime with bounds checking (NEM-2602)
        created_at = _parse_and_validate_datetime(cursor, validated.created_at)

        return CursorData(
            id=validated.id,
            created_at=created_at,
            direction=validated.direction,
        )
    except ValueError:
        # Re-raise ValueError as-is (already properly formatted)
        raise
    except Exception as e:
        # Catch any other unexpected errors and log as suspicious
        _log_suspicious_cursor(cursor, f"Unexpected error: {e}", e)
        raise ValueError("Invalid cursor: validation failed") from e


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


def set_deprecation_headers(
    response: Response,
    cursor: str | None,
    offset: int,
    sunset_date: str | None = "2026-06-01",
) -> None:
    """Set HTTP Deprecation headers if offset pagination is used.

    This function sets the HTTP Deprecation header per IETF draft standard
    (draft-ietf-httpapi-deprecation-header-02) when offset-based pagination
    is detected without a cursor.

    Headers set:
    - Deprecation: true (indicates the feature is deprecated)
    - Sunset: <date> (optional, indicates when the feature will be removed)

    Args:
        response: FastAPI Response object to set headers on
        cursor: The cursor parameter from the request
        offset: The offset parameter from the request
        sunset_date: Optional sunset date in HTTP-date format (RFC 7231).
                     Defaults to "2026-06-01". Set to None to omit Sunset header.

    Reference:
        https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-deprecation-header-02
    """
    # Only set headers if deprecation warning would be shown
    if get_deprecation_warning(cursor, offset) is None:
        return

    # Set Deprecation header per IETF draft standard
    # The value "true" indicates the resource/feature is deprecated
    response.headers["Deprecation"] = "true"

    # Optionally set Sunset header with future removal date
    # The Sunset header indicates when the deprecated feature will be removed
    if sunset_date:
        response.headers["Sunset"] = sunset_date
