"""Time utilities for consistent UTC datetime handling.

This module provides centralized time utility functions to ensure consistent
UTC time handling across the codebase. All modules that need the current UTC
time should import from here rather than defining their own functions.

Usage:
    from backend.core.time_utils import utc_now, utc_now_naive

    # For timezone-aware datetime (use with DateTime(timezone=True) columns)
    now = utc_now()

    # For naive datetime (use with DateTime(timezone=False) columns)
    now_naive = utc_now_naive()
"""

from datetime import UTC, datetime

__all__ = ["utc_now", "utc_now_naive"]


def utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime.

    This replaces the deprecated datetime.utcnow() and returns a timezone-aware
    datetime compatible with DateTime(timezone=True) columns.

    Returns:
        A timezone-aware datetime object representing the current UTC time.

    Example:
        >>> from backend.core.time_utils import utc_now
        >>> now = utc_now()
        >>> now.tzinfo
        datetime.timezone.utc
    """
    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    """Get current UTC time as naive datetime for PostgreSQL compatibility.

    PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns cannot accept timezone-aware
    datetimes from Python. This function ensures we always use naive UTC times
    for such columns.

    Returns:
        A naive datetime object representing the current UTC time (without tzinfo).

    Example:
        >>> from backend.core.time_utils import utc_now_naive
        >>> now = utc_now_naive()
        >>> now.tzinfo is None
        True
    """
    return datetime.now(UTC).replace(tzinfo=None)
