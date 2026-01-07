"""Shared validation utilities for API routes.

This module contains reusable validators that can be used across multiple
API endpoints to ensure consistent validation behavior.

Validators:
- validate_date_range: Ensures start_date is not after end_date
- validate_camera_id_format: Validates camera ID format and length
- validate_risk_score_range: Validates risk score is within 0-100 range
"""

import re
from datetime import datetime

from fastapi import HTTPException, status

# =============================================================================
# Camera ID Validation Constants
# =============================================================================

# Camera ID must be alphanumeric with underscores and hyphens only
# This prevents path traversal, SQL injection, and other injection attacks
CAMERA_ID_PATTERN = r"^[a-zA-Z0-9_-]+$"
CAMERA_ID_MIN_LENGTH = 1
CAMERA_ID_MAX_LENGTH = 64

# Compiled regex for performance (compile once, use many times)
_CAMERA_ID_REGEX = re.compile(CAMERA_ID_PATTERN)

# =============================================================================
# Risk Score Validation Constants
# =============================================================================

# Risk score thresholds (aligned with backend severity taxonomy)
RISK_SCORE_MIN = 0
RISK_SCORE_MAX = 100


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


def validate_camera_id_format(camera_id: str) -> str:
    """Validate camera_id format for security and correctness.

    Camera IDs must be alphanumeric with underscores and hyphens only.
    This prevents path traversal, SQL injection, and other injection attacks.

    Args:
        camera_id: The camera identifier to validate

    Returns:
        The validated camera_id (unchanged if valid)

    Raises:
        HTTPException: 400 Bad Request if camera_id is invalid

    Examples:
        >>> validate_camera_id_format("front_door")
        'front_door'

        >>> validate_camera_id_format("camera-123")
        'camera-123'

        >>> validate_camera_id_format("invalid@id")
        # Raises HTTPException with status 400

    Security:
        Rejects:
        - Path traversal attempts (../)
        - Special characters (@, #, $, etc.)
        - Dots (to prevent file extension manipulation)
        - Spaces and whitespace
        - Control characters
    """
    # Check for None or non-string types
    if camera_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="camera_id is required and cannot be None",
        )

    if not isinstance(camera_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"camera_id must be a string, got {type(camera_id).__name__}",
        )

    # Check length constraints
    if len(camera_id) < CAMERA_ID_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"camera_id must be at least {CAMERA_ID_MIN_LENGTH} character(s) long",
        )

    if len(camera_id) > CAMERA_ID_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"camera_id must be at most {CAMERA_ID_MAX_LENGTH} characters long, "
            f"got {len(camera_id)} characters",
        )

    # Check format pattern (alphanumeric, underscore, hyphen only)
    if not _CAMERA_ID_REGEX.match(camera_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="camera_id must contain only alphanumeric characters, underscores, and hyphens. "
            f"Invalid format: '{camera_id}'",
        )

    return camera_id


def validate_risk_score_range(risk_score: int) -> int:
    """Validate that risk_score is within the valid range (0-100).

    Risk scores represent the assessed risk level of a security event:
    - 0-29: Low risk
    - 30-59: Medium risk
    - 60-84: High risk
    - 85-100: Critical risk

    Args:
        risk_score: The risk score to validate (must be an integer)

    Returns:
        The validated risk_score (unchanged if valid)

    Raises:
        HTTPException: 400 Bad Request if risk_score is out of range
        TypeError: If risk_score is not an integer

    Examples:
        >>> validate_risk_score_range(75)
        75

        >>> validate_risk_score_range(0)
        0

        >>> validate_risk_score_range(101)
        # Raises HTTPException with status 400
    """
    # Check for None
    if risk_score is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="risk_score is required and cannot be None",
        )

    # Check type (must be integer, not float or string)
    if not isinstance(risk_score, int) or isinstance(risk_score, bool):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"risk_score must be an integer, got {type(risk_score).__name__}",
        )

    # Check range
    if risk_score < RISK_SCORE_MIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"risk_score must be at least {RISK_SCORE_MIN}, got {risk_score}. "
            f"Valid range is {RISK_SCORE_MIN}-{RISK_SCORE_MAX}.",
        )

    if risk_score > RISK_SCORE_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"risk_score must be at most {RISK_SCORE_MAX}, got {risk_score}. "
            f"Valid range is {RISK_SCORE_MIN}-{RISK_SCORE_MAX}.",
        )

    return risk_score
