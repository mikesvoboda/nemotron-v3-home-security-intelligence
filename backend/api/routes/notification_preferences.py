"""Notification preferences API endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.notification_preferences import (
    CameraNotificationSettingResponse,
    CameraNotificationSettingsListResponse,
    CameraNotificationSettingUpdate,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    PushSubscriptionRegister,
    PushSubscriptionRegisterResponse,
    PushSubscriptionState,
    QuietHoursPeriodCreate,
    QuietHoursPeriodResponse,
    QuietHoursPeriodsListResponse,
)
from backend.api.schemas.pagination import PaginationMeta
from backend.core import get_db
from backend.models.alert_delivery import DeliveryChannelKind, Recipient, RecipientChannel
from backend.models.notification_preferences import (
    DEFAULT_CAMERA_RISK_THRESHOLD,
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
        # Create new setting at the shipped default floor (OD-29: 60, was 0)
        setting = CameraNotificationSetting(
            camera_id=camera_id,
            enabled=True,
            risk_threshold=DEFAULT_CAMERA_RISK_THRESHOLD,
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


# --- Web Push subscription (This browser, B4.3) ------------------------------


def _masked_subscription(sub: dict | None) -> dict | None:
    """A subscription echo the privacy row can stand behind.

    The endpoint host is kept (routing diagnostics need it) but the path is
    truncated, and each key is replaced by a fingerprint — the API never
    returns secrets or push keys in full (4n-alerting.md, "Privacy").
    """
    if not isinstance(sub, dict):
        return None
    endpoint = str(sub.get("endpoint") or "")
    raw_keys = sub.get("keys")
    keys: dict[str, Any] = raw_keys if isinstance(raw_keys, dict) else {}
    masked_keys: dict[str, str] = {}
    for name in ("p256dh", "auth"):
        value = str(keys.get(name) or "")
        masked_keys[name] = f"{name}:{value[:4]}…" if value else ""
    host = urlparse(endpoint).netloc or endpoint[:24]
    masked_endpoint = f"{host}/…"
    return {"endpoint": masked_endpoint, "keys": masked_keys}


def _push_channel_of(recipient: Recipient, device_id: str | None) -> RecipientChannel | None:
    """This browser's webpush channel row, or None when it has none.

    A ``device_id`` pins the row (several browsers may each hold their own
    subscription); without one the first webpush row answers.
    """
    for channel in recipient.channels:
        if getattr(channel, "kind", None) != DeliveryChannelKind.WEBPUSH:
            continue
        if device_id and str(getattr(channel, "target", "") or "") != device_id:
            continue
        return channel
    return None


@router.put(
    "/push-subscription",
    response_model=PushSubscriptionRegisterResponse,
    summary="Register or rotate this browser's Web Push subscription",
)
async def register_push_subscription(
    payload: PushSubscriptionRegister,
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionRegisterResponse:
    """Register (or rotate) this browser's Web Push subscription.

    Writes a ``webpush`` channel row on the Household recipient — the seeded
    recipient that owns quiet hours and holds the This-browser row (the
    design's This-browser row needs no login). An existing row for the same
    browser is updated in place, never duplicated, and a re-subscription
    re-enables a row the worker disabled on HTTP 410.
    """
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Recipient)
        .options(selectinload(Recipient.channels))
        .where(Recipient.enabled.is_(True))
    )
    recipients = result.scalars().all()
    recipient = next((r for r in recipients if r.name == "Household"), None)
    if recipient is None:
        recipient = recipients[0] if recipients else None
    if recipient is None:
        # The recorded upgrade seeds Household; nothing to attach to is a
        # server-side state problem, not a client error.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No notification recipient exists yet; complete setup first.",
        )

    subscription = {
        "endpoint": payload.endpoint,
        "keys": {"p256dh": payload.keys.p256dh, "auth": payload.keys.auth},
    }
    channel = _push_channel_of(recipient, payload.device_id)
    if channel is None:
        channel = RecipientChannel(
            id=str(uuid.uuid4()),
            recipient_id=recipient.id,
            kind=DeliveryChannelKind.WEBPUSH,
            target=payload.device_id or "browser",
            push_subscription=subscription,
            enabled=True,
        )
        db.add(channel)
        recipient.channels.append(channel)
    else:
        channel.push_subscription = subscription
        channel.target = payload.device_id or channel.target
        channel.enabled = True
        channel.last_error = None
    await db.commit()
    return PushSubscriptionRegisterResponse(
        status="registered",
        push_subscription=_masked_subscription(subscription) or {},
        enabled=True,
    )


@router.get(
    "/push-subscription",
    response_model=PushSubscriptionState,
    summary="This browser's Web Push subscription state (masked)",
)
async def get_push_subscription(
    device_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionState:
    """Subscription state for the settings page, with keys masked.

    Reports ``registered``/``enabled`` so a channel the worker switched off
    on HTTP 410 is shown switched off (4n-alerting.md:236).
    """
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Recipient)
        .options(selectinload(Recipient.channels))
        .where(Recipient.enabled.is_(True))
    )
    recipients = result.scalars().all()
    recipient = next((r for r in recipients if r.name == "Household"), None)
    if recipient is None:
        return PushSubscriptionState(registered=False)

    channel = _push_channel_of(recipient, device_id)
    if channel is None:
        return PushSubscriptionState(registered=False)
    sub = channel.push_subscription if isinstance(channel.push_subscription, dict) else None
    masked = _masked_subscription(sub)
    return PushSubscriptionState(
        registered=True,
        enabled=bool(channel.enabled),
        endpoint=masked["endpoint"] if masked else None,
        push_subscription=masked,
        last_error=getattr(channel, "last_error", None),
    )


@router.delete(
    "/push-subscription",
    response_model=PushSubscriptionState,
    summary="Remove this browser's Web Push subscription",
)
async def delete_push_subscription(
    device_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionState:
    """Delete this browser's channel row (the browser asked to unsubscribe)."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Recipient)
        .options(selectinload(Recipient.channels))
        .where(Recipient.enabled.is_(True))
    )
    recipients = result.scalars().all()
    recipient = next((r for r in recipients if r.name == "Household"), None)
    if recipient is None:
        return PushSubscriptionState(registered=False)

    channel = _push_channel_of(recipient, device_id)
    if channel is None:
        return PushSubscriptionState(registered=False)
    await db.delete(channel)
    recipient.channels.remove(channel)
    await db.commit()
    return PushSubscriptionState(registered=False)
