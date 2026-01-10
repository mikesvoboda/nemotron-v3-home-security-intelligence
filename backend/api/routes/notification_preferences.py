"""Notification preferences API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.notification_preferences import (
    CameraNotificationSettingResponse,
    CameraNotificationSettingsListResponse,
    CameraNotificationSettingUpdate,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    QuietHoursPeriodCreate,
    QuietHoursPeriodResponse,
    QuietHoursPeriodsListResponse,
)
from backend.api.schemas.pagination import PaginationMeta
from backend.core import get_db
from backend.models.notification_preferences import (
    CameraNotificationSetting,
    NotificationPreferences,
    NotificationSound,
    QuietHoursPeriod,
    RiskLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notification-preferences", tags=["notification-preferences"])


# =============================================================================
# Global Preferences Endpoints
# =============================================================================


@router.get(
    "/",
    response_model=NotificationPreferencesResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Get global notification preferences.

    Returns the global notification settings including:
    - Whether notifications are enabled
    - Notification sound selection
    - Risk level filters (which risk levels trigger notifications)

    Returns:
        NotificationPreferencesResponse with current preferences
    """
    # Get or create preferences (singleton with id=1)
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.id == 1)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        # Create default preferences if they don't exist
        prefs = NotificationPreferences(
            id=1,
            enabled=True,
            sound=NotificationSound.DEFAULT.value,
            risk_filters=[
                RiskLevel.CRITICAL.value,
                RiskLevel.HIGH.value,
                RiskLevel.MEDIUM.value,
            ],
        )
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)

    return NotificationPreferencesResponse.model_validate(prefs)


@router.put(
    "/",
    response_model=NotificationPreferencesResponse,
    responses={
        400: {"description": "Bad request - Invalid sound or risk level value"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def update_notification_preferences(
    update: NotificationPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Update global notification preferences.

    Args:
        update: Preferences update data

    Returns:
        NotificationPreferencesResponse with updated preferences

    Raises:
        HTTPException: 400 if sound value is invalid
    """
    # Get existing preferences
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.id == 1)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        # Create if doesn't exist
        prefs = NotificationPreferences(id=1)
        db.add(prefs)

    # Update fields if provided
    if update.enabled is not None:
        prefs.enabled = update.enabled

    if update.sound is not None:
        # Validate sound value
        valid_sounds = [s.value for s in NotificationSound]
        if update.sound not in valid_sounds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sound value. Must be one of: {', '.join(valid_sounds)}",
            )
        prefs.sound = update.sound

    if update.risk_filters is not None:
        # Validate risk filters
        valid_levels = [lvl.value for lvl in RiskLevel]
        for level in update.risk_filters:
            if level not in valid_levels:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid risk level: {level}. Must be one of: {', '.join(valid_levels)}",
                )
        prefs.risk_filters = update.risk_filters

    await db.commit()
    await db.refresh(prefs)

    return NotificationPreferencesResponse.model_validate(prefs)


# =============================================================================
# Camera Settings Endpoints
# =============================================================================


@router.get(
    "/cameras",
    response_model=CameraNotificationSettingsListResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_all_camera_settings(
    db: AsyncSession = Depends(get_db),
) -> CameraNotificationSettingsListResponse:
    """Get all camera notification settings.

    Returns:
        CameraNotificationSettingsListResponse with all camera settings
    """
    result = await db.execute(select(CameraNotificationSetting))
    settings = result.scalars().all()

    return CameraNotificationSettingsListResponse(
        items=[CameraNotificationSettingResponse.model_validate(s) for s in settings],
        pagination=PaginationMeta(
            total=len(settings),
            limit=len(settings) or 50,
            offset=0,
            has_more=False,
        ),
    )


@router.get(
    "/cameras/{camera_id}",
    response_model=CameraNotificationSettingResponse,
    responses={
        404: {"description": "Camera notification setting not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_camera_setting(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> CameraNotificationSettingResponse:
    """Get notification setting for a specific camera.

    Args:
        camera_id: Camera ID

    Returns:
        CameraNotificationSettingResponse for the camera

    Raises:
        HTTPException: 404 if setting not found
    """
    result = await db.execute(
        select(CameraNotificationSetting).where(CameraNotificationSetting.camera_id == camera_id)
    )
    setting = result.scalar_one_or_none()

    if setting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification setting for camera '{camera_id}' not found",
        )

    return CameraNotificationSettingResponse.model_validate(setting)


@router.put(
    "/cameras/{camera_id}",
    response_model=CameraNotificationSettingResponse,
    responses={
        404: {"description": "Camera not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def update_camera_setting(
    camera_id: str,
    update: CameraNotificationSettingUpdate,
    db: AsyncSession = Depends(get_db),
) -> CameraNotificationSettingResponse:
    """Update or create notification setting for a camera.

    Args:
        camera_id: Camera ID
        update: Setting update data

    Returns:
        CameraNotificationSettingResponse with updated setting

    Raises:
        HTTPException: 404 if camera doesn't exist
    """
    # Check if camera exists
    from backend.models import Camera

    camera_result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = camera_result.scalar_one_or_none()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )

    # Get or create setting
    result = await db.execute(
        select(CameraNotificationSetting).where(CameraNotificationSetting.camera_id == camera_id)
    )
    setting = result.scalar_one_or_none()

    if setting is None:
        # Create new setting
        setting = CameraNotificationSetting(
            camera_id=camera_id,
            enabled=True,
            risk_threshold=0,
        )
        db.add(setting)

    # Update fields if provided
    if update.enabled is not None:
        setting.enabled = update.enabled

    if update.risk_threshold is not None:
        setting.risk_threshold = update.risk_threshold

    await db.commit()
    await db.refresh(setting)

    return CameraNotificationSettingResponse.model_validate(setting)


# =============================================================================
# Quiet Hours Endpoints
# =============================================================================


@router.get(
    "/quiet-hours",
    response_model=QuietHoursPeriodsListResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_quiet_hours(
    db: AsyncSession = Depends(get_db),
) -> QuietHoursPeriodsListResponse:
    """Get all quiet hours periods.

    Returns:
        QuietHoursPeriodsListResponse with all quiet periods
    """
    result = await db.execute(select(QuietHoursPeriod))
    periods = result.scalars().all()

    return QuietHoursPeriodsListResponse(
        items=[QuietHoursPeriodResponse.model_validate(p) for p in periods],
        pagination=PaginationMeta(
            total=len(periods),
            limit=len(periods) or 50,
            offset=0,
            has_more=False,
        ),
    )


@router.post(
    "/quiet-hours",
    response_model=QuietHoursPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad request - Invalid time range"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_quiet_hours_period(
    period: QuietHoursPeriodCreate,
    db: AsyncSession = Depends(get_db),
) -> QuietHoursPeriodResponse:
    """Create a new quiet hours period.

    Args:
        period: Quiet hours period data

    Returns:
        QuietHoursPeriodResponse with created period

    Raises:
        HTTPException: 400 if start_time equals end_time (zero-length period)

    Note:
        Periods can span midnight (e.g., 22:00 to 06:00).
        If start_time > end_time, the period wraps to the next day.
    """
    # Validate that period has non-zero length
    if period.start_time == period.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must not equal end_time (zero-length period)",
        )

    # Create new period
    new_period = QuietHoursPeriod(
        label=period.label,
        start_time=period.start_time,
        end_time=period.end_time,
        days=period.days,
    )
    db.add(new_period)

    try:
        await db.commit()
        await db.refresh(new_period)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create quiet hours period: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create quiet hours period",
        ) from e

    return QuietHoursPeriodResponse.model_validate(new_period)


@router.delete(
    "/quiet-hours/{period_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Quiet hours period not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_quiet_hours_period(
    period_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a quiet hours period.

    Args:
        period_id: Period UUID

    Raises:
        HTTPException: 404 if period not found
    """
    result = await db.execute(select(QuietHoursPeriod).where(QuietHoursPeriod.id == period_id))
    period = result.scalar_one_or_none()

    if period is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiet hours period '{period_id}' not found",
        )

    await db.delete(period)
    await db.commit()
