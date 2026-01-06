"""Reusable utility functions for entity existence checks.

This module provides utility functions that abstract the repeated pattern of
querying for an entity by ID and raising a 404 if not found.

Usage:
    from backend.api.dependencies import get_camera_or_404

    @router.get("/{camera_id}")
    async def get_camera(
        camera_id: str,
        db: AsyncSession = Depends(get_db),
    ) -> CameraResponse:
        camera = await get_camera_or_404(camera_id, db)
        return camera

These functions can be called directly from route handlers, simplifying the
common pattern of:

    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with id {camera_id} not found")

Into a single line:

    camera = await get_camera_or_404(camera_id, db)
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event


async def get_camera_or_404(
    camera_id: str,
    db: AsyncSession,
) -> Camera:
    """Get a camera by ID or raise 404 if not found.

    This utility function queries the database for a camera with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        camera_id: The camera ID to look up
        db: Database session

    Returns:
        Camera object if found

    Raises:
        HTTPException: 404 if camera not found
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    return camera


async def get_event_or_404(
    event_id: int,
    db: AsyncSession,
) -> Event:
    """Get an event by ID or raise 404 if not found.

    This utility function queries the database for an event with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        event_id: The event ID to look up
        db: Database session

    Returns:
        Event object if found

    Raises:
        HTTPException: 404 if event not found
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )

    return event


async def get_detection_or_404(
    detection_id: int,
    db: AsyncSession,
) -> Detection:
    """Get a detection by ID or raise 404 if not found.

    This utility function queries the database for a detection with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        detection_id: The detection ID to look up
        db: Database session

    Returns:
        Detection object if found

    Raises:
        HTTPException: 404 if detection not found
    """
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection with id {detection_id} not found",
        )

    return detection
