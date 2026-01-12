"""API routes for UserCalibration management (NEM-2316, NEM-2350).

This module provides CRUD endpoints for managing user-specific risk thresholds
that are used to categorize risk scores from the AI pipeline.

Endpoints:
    GET    /api/calibration           - Get current user's calibration
    PUT    /api/calibration           - Update calibration thresholds (full update)
    PATCH  /api/calibration           - Partial update calibration thresholds
    POST   /api/calibration/reset     - Reset to default thresholds
    GET    /api/calibration/defaults  - Get default threshold values

For the single-user system, all endpoints use user_id="default".
Calibration records are auto-created on first GET if they don't exist.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.calibration import (
    CalibrationDefaultsResponse,
    CalibrationResetResponse,
    CalibrationResponse,
    CalibrationUpdate,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.user_calibration import UserCalibration

logger = get_logger(__name__)

# Default user ID for single-user system
DEFAULT_USER_ID = "default"

# Default threshold values
DEFAULT_LOW_THRESHOLD = 30
DEFAULT_MEDIUM_THRESHOLD = 60
DEFAULT_HIGH_THRESHOLD = 85
DEFAULT_DECAY_FACTOR = 0.1

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


def _calibration_to_response(calibration: UserCalibration) -> dict[str, Any]:
    """Convert a UserCalibration model to response dict."""
    return {
        "id": calibration.id,
        "user_id": calibration.user_id,
        "low_threshold": calibration.low_threshold,
        "medium_threshold": calibration.medium_threshold,
        "high_threshold": calibration.high_threshold,
        "decay_factor": calibration.decay_factor,
        "false_positive_count": calibration.false_positive_count,
        "missed_detection_count": calibration.missed_detection_count,
        "created_at": calibration.created_at,
        "updated_at": calibration.updated_at,
    }


async def _get_or_create_calibration(
    db: AsyncSession,
    user_id: str = DEFAULT_USER_ID,
) -> UserCalibration:
    """Get user calibration, creating with defaults if not exists.

    Args:
        db: Database session
        user_id: User identifier (default for single-user system)

    Returns:
        UserCalibration instance (existing or newly created)
    """
    result = await db.execute(select(UserCalibration).where(UserCalibration.user_id == user_id))
    calibration = result.scalar_one_or_none()

    if calibration is None:
        # Auto-create with defaults
        calibration = UserCalibration(
            user_id=user_id,
            low_threshold=DEFAULT_LOW_THRESHOLD,
            medium_threshold=DEFAULT_MEDIUM_THRESHOLD,
            high_threshold=DEFAULT_HIGH_THRESHOLD,
            decay_factor=DEFAULT_DECAY_FACTOR,
        )
        db.add(calibration)
        await db.commit()
        await db.refresh(calibration)
        logger.info(
            f"Auto-created calibration for user {user_id}",
            extra={"user_id": user_id},
        )

    return calibration


def _validate_threshold_ordering(
    low: int,
    medium: int,
    high: int,
) -> None:
    """Validate that thresholds maintain proper ordering.

    Args:
        low: Low threshold value
        medium: Medium threshold value
        high: High threshold value

    Raises:
        HTTPException: 422 if thresholds are not properly ordered
    """
    if low >= medium:
        raise HTTPException(
            status_code=422,
            detail=f"low_threshold ({low}) must be less than medium_threshold ({medium})",
        )
    if medium >= high:
        raise HTTPException(
            status_code=422,
            detail=f"medium_threshold ({medium}) must be less than high_threshold ({high})",
        )


@router.get(
    "",
    response_model=CalibrationResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_calibration(
    db: AsyncSession = Depends(get_db),
) -> CalibrationResponse:
    """Get the current user's calibration settings.

    Returns the calibration thresholds for the default user.
    If no calibration exists, one is automatically created with default values.

    Returns:
        CalibrationResponse with current threshold settings
    """
    calibration = await _get_or_create_calibration(db)
    return CalibrationResponse(**_calibration_to_response(calibration))


@router.put(
    "",
    response_model=CalibrationResponse,
    responses={
        422: {"description": "Validation error (invalid threshold ordering)"},
        500: {"description": "Internal server error"},
    },
)
async def update_calibration(
    update_data: CalibrationUpdate,
    db: AsyncSession = Depends(get_db),
) -> CalibrationResponse:
    """Update calibration thresholds.

    Allows partial updates - only provided fields will be changed.
    Validates that threshold ordering is maintained (low < medium < high).

    Args:
        update_data: Fields to update (partial updates supported)
        db: Database session

    Returns:
        Updated CalibrationResponse

    Raises:
        HTTPException: 422 if threshold ordering would be violated
    """
    calibration = await _get_or_create_calibration(db)

    # Get current values (to fill in for partial updates)
    new_low = (
        update_data.low_threshold
        if update_data.low_threshold is not None
        else calibration.low_threshold
    )
    new_medium = (
        update_data.medium_threshold
        if update_data.medium_threshold is not None
        else calibration.medium_threshold
    )
    new_high = (
        update_data.high_threshold
        if update_data.high_threshold is not None
        else calibration.high_threshold
    )

    # Validate threshold ordering with merged values
    _validate_threshold_ordering(new_low, new_medium, new_high)

    # Apply updates
    if update_data.low_threshold is not None:
        calibration.low_threshold = update_data.low_threshold
    if update_data.medium_threshold is not None:
        calibration.medium_threshold = update_data.medium_threshold
    if update_data.high_threshold is not None:
        calibration.high_threshold = update_data.high_threshold
    if update_data.decay_factor is not None:
        calibration.decay_factor = update_data.decay_factor

    await db.commit()
    await db.refresh(calibration)

    logger.info(
        "Updated calibration thresholds",
        extra={
            "user_id": calibration.user_id,
            "low": calibration.low_threshold,
            "medium": calibration.medium_threshold,
            "high": calibration.high_threshold,
        },
    )

    return CalibrationResponse(**_calibration_to_response(calibration))


@router.patch(
    "",
    response_model=CalibrationResponse,
    responses={
        422: {"description": "Validation error (invalid threshold ordering)"},
        500: {"description": "Internal server error"},
    },
)
async def patch_calibration(
    update_data: CalibrationUpdate,
    db: AsyncSession = Depends(get_db),
) -> CalibrationResponse:
    """Partially update calibration thresholds.

    Allows partial updates - only provided fields will be changed.
    Validates that threshold ordering is maintained (low < medium < high).

    This endpoint is semantically identical to PUT but emphasizes partial updates.

    Args:
        update_data: Fields to update (partial updates supported)
        db: Database session

    Returns:
        Updated CalibrationResponse

    Raises:
        HTTPException: 422 if threshold ordering would be violated
    """
    # Delegate to the same logic as PUT
    return await update_calibration(update_data, db)


@router.post(
    "/reset",
    response_model=CalibrationResetResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def reset_calibration(
    db: AsyncSession = Depends(get_db),
) -> CalibrationResetResponse:
    """Reset calibration to default thresholds.

    Resets all thresholds to their default values:
    - low_threshold: 30
    - medium_threshold: 60
    - high_threshold: 85
    - decay_factor: 0.1

    Note: Feedback counts (false_positive_count, missed_detection_count)
    are NOT reset by this operation.

    Returns:
        CalibrationResetResponse with success message and reset calibration data
    """
    calibration = await _get_or_create_calibration(db)

    # Reset to defaults
    calibration.low_threshold = DEFAULT_LOW_THRESHOLD
    calibration.medium_threshold = DEFAULT_MEDIUM_THRESHOLD
    calibration.high_threshold = DEFAULT_HIGH_THRESHOLD
    calibration.decay_factor = DEFAULT_DECAY_FACTOR

    await db.commit()
    await db.refresh(calibration)

    logger.info(
        "Reset calibration to defaults",
        extra={"user_id": calibration.user_id},
    )

    return CalibrationResetResponse(
        message="Calibration reset to default values",
        calibration=CalibrationResponse(**_calibration_to_response(calibration)),
    )


@router.get(
    "/defaults",
    response_model=CalibrationDefaultsResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_calibration_defaults() -> CalibrationDefaultsResponse:
    """Get default calibration threshold values.

    Returns the default values used when creating new calibrations
    or when resetting to defaults. This endpoint is useful for
    displaying defaults in the UI or documentation.

    Returns:
        CalibrationDefaultsResponse with default threshold values
    """
    return CalibrationDefaultsResponse(
        low_threshold=DEFAULT_LOW_THRESHOLD,
        medium_threshold=DEFAULT_MEDIUM_THRESHOLD,
        high_threshold=DEFAULT_HIGH_THRESHOLD,
        decay_factor=DEFAULT_DECAY_FACTOR,
    )
