"""Shared validation utilities for API routes.

This module contains reusable validators that can be used across multiple
API endpoints to ensure consistent validation behavior.
"""

from datetime import datetime

from fastapi import HTTPException, status


def validate_date_range(start_date: datetime | None, end_date: datetime | None) -> None:
    """Validate that start_date is not after end_date.

    This validation ensures that date range filters make logical sense.
    Users could accidentally swap start and end dates, leading to empty
    results and confusion.

    Args:
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering

    Raises:
        HTTPException: 400 Bad Request if start_date is after end_date

    Examples:
        >>> validate_date_range(datetime(2025, 1, 1), datetime(2025, 12, 31))
        # Valid - no exception

        >>> validate_date_range(datetime(2025, 12, 31), datetime(2025, 1, 1))
        # Raises HTTPException with status 400
    """
    # If either date is None or not a datetime instance, validation passes
    # (partial ranges are allowed, and non-datetime values like FastAPI Query
    # objects should be skipped - these occur in unit tests calling functions directly)
    if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
        return

    # Check if start_date is after end_date
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date. "
            f"Received start_date={start_date.isoformat()}, end_date={end_date.isoformat()}",
        )
