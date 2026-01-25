"""API routes for SystemSetting Key-Value Store (NEM-3638).

This module provides REST API endpoints for managing system-wide settings
stored as key-value pairs in the SystemSetting model.

Endpoints:
- GET /api/v1/system-settings: List all settings
- GET /api/v1/system-settings/{key}: Get a specific setting
- PATCH /api/v1/system-settings/{key}: Update or create a setting
- DELETE /api/v1/system-settings/{key}: Delete a setting
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import ORJSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.system_settings import (
    SystemSettingListResponse,
    SystemSettingResponse,
    SystemSettingUpdate,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.gpu_config import SystemSetting

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/system-settings",
    tags=["system-settings"],
    default_response_class=ORJSONResponse,
)


@router.get("", response_model=SystemSettingListResponse)
async def list_system_settings(
    db: AsyncSession = Depends(get_db),
) -> SystemSettingListResponse:
    """List all system settings.

    Returns all key-value pairs from the SystemSetting table, ordered by key.

    Returns:
        SystemSettingListResponse with all settings
    """
    query = select(SystemSetting).order_by(SystemSetting.key)
    result = await db.execute(query)
    settings = list(result.scalars().all())

    return SystemSettingListResponse(
        items=[
            SystemSettingResponse(
                key=s.key,
                value=s.value,
                updated_at=s.updated_at,
            )
            for s in settings
        ],
        total=len(settings),
    )


@router.get("/{key}", response_model=SystemSettingResponse)
async def get_system_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> SystemSettingResponse:
    """Get a specific system setting by key.

    Args:
        key: Setting key to retrieve
        db: Database session

    Returns:
        SystemSettingResponse with the setting value

    Raises:
        HTTPException: 404 if setting not found
    """
    setting = await db.get(SystemSetting, key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"System setting '{key}' not found",
        )

    return SystemSettingResponse(
        key=setting.key,
        value=setting.value,
        updated_at=setting.updated_at,
    )


@router.patch("/{key}", response_model=SystemSettingResponse)
async def update_system_setting(
    key: str,
    update: SystemSettingUpdate,
    db: AsyncSession = Depends(get_db),
) -> SystemSettingResponse:
    """Update or create a system setting.

    If the setting exists, updates its value. If it doesn't exist, creates it.
    This is an upsert operation.

    Args:
        key: Setting key to update or create
        update: New value for the setting
        db: Database session

    Returns:
        SystemSettingResponse with the updated setting

    Raises:
        HTTPException: 400 if key format is invalid
    """
    # Validate key format (lowercase alphanumeric with underscores)
    import re

    if not re.match(r"^[a-z][a-z0-9_]*$", key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid key format: '{key}'. Keys must be lowercase alphanumeric "
            "with underscores, starting with a letter.",
        )

    if len(key) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Key too long: '{key}'. Maximum length is 64 characters.",
        )

    setting = await db.get(SystemSetting, key)

    if setting:
        # Update existing setting
        setting.value = update.value
        setting.updated_at = datetime.now(UTC)
        logger.info("Updated system setting", extra={"key": key})
    else:
        # Create new setting
        setting = SystemSetting(
            key=key,
            value=update.value,
            updated_at=datetime.now(UTC),
        )
        db.add(setting)
        logger.info("Created system setting", extra={"key": key})

    await db.commit()
    await db.refresh(setting)

    return SystemSettingResponse(
        key=setting.key,
        value=setting.value,
        updated_at=setting.updated_at,
    )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a system setting.

    Args:
        key: Setting key to delete
        db: Database session

    Raises:
        HTTPException: 404 if setting not found
    """
    setting = await db.get(SystemSetting, key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"System setting '{key}' not found",
        )

    await db.delete(setting)
    await db.commit()
    logger.info("Deleted system setting", extra={"key": key})
