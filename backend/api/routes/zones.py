"""API routes for camera zone management."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_camera_or_404, get_zone_or_404
from backend.api.schemas.zone import (
    ZoneCreate,
    ZoneListResponse,
    ZoneResponse,
    ZoneUpdate,
)
from backend.core.database import get_db
from backend.models.zone import Zone

router = APIRouter(prefix="/api/cameras", tags=["zones"])


@router.get(
    "/{camera_id}/zones",
    response_model=ZoneListResponse,
    responses={
        404: {"description": "Camera not found"},
        500: {"description": "Internal server error"},
    },
)
async def list_zones(
    camera_id: str,
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all zones for a camera with optional filtering.

    Args:
        camera_id: ID of the camera
        enabled: Optional filter for enabled/disabled zones
        db: Database session

    Returns:
        ZoneListResponse containing list of zones and total count
    """
    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    query = select(Zone).where(Zone.camera_id == camera_id).order_by(Zone.priority.desc())

    # Apply enabled filter if provided
    if enabled is not None:
        query = query.where(Zone.enabled == enabled)

    result = await db.execute(query)
    zones = result.scalars().all()

    return {
        "zones": zones,
        "count": len(zones),
    }


@router.post(
    "/{camera_id}/zones",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Camera not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_zone(
    camera_id: str,
    zone_data: ZoneCreate,
    db: AsyncSession = Depends(get_db),
) -> Zone:
    """Create a new zone for a camera.

    Args:
        camera_id: ID of the camera
        zone_data: Zone creation data
        db: Database session

    Returns:
        Created zone object with generated ID
    """
    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    # Create zone with generated UUID
    zone = Zone(
        id=str(uuid.uuid4()),
        camera_id=camera_id,
        name=zone_data.name,
        zone_type=zone_data.zone_type,
        coordinates=zone_data.coordinates,
        shape=zone_data.shape,
        color=zone_data.color,
        enabled=zone_data.enabled,
        priority=zone_data.priority,
    )

    db.add(zone)
    await db.commit()
    await db.refresh(zone)

    return zone


@router.get(
    "/{camera_id}/zones/{zone_id}",
    response_model=ZoneResponse,
    responses={
        404: {"description": "Camera or zone not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_zone(
    camera_id: str,
    zone_id: str,
    db: AsyncSession = Depends(get_db),
) -> Zone:
    """Get a specific zone by ID.

    Args:
        camera_id: ID of the camera
        zone_id: ID of the zone
        db: Database session

    Returns:
        Zone object

    Raises:
        HTTPException: 404 if zone not found
    """
    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    return await get_zone_or_404(zone_id, db, camera_id=camera_id)


@router.put(
    "/{camera_id}/zones/{zone_id}",
    response_model=ZoneResponse,
    responses={
        404: {"description": "Camera or zone not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def update_zone(
    camera_id: str,
    zone_id: str,
    zone_data: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
) -> Zone:
    """Update an existing zone.

    Args:
        camera_id: ID of the camera
        zone_id: ID of the zone to update
        zone_data: Zone update data (all fields optional)
        db: Database session

    Returns:
        Updated zone object

    Raises:
        HTTPException: 404 if zone not found
    """
    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    zone = await get_zone_or_404(zone_id, db, camera_id=camera_id)

    # Update only provided fields
    update_data = zone_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)

    await db.commit()
    await db.refresh(zone)

    return zone


@router.delete(
    "/{camera_id}/zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Camera or zone not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_zone(
    camera_id: str,
    zone_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a zone.

    Args:
        camera_id: ID of the camera
        zone_id: ID of the zone to delete
        db: Database session

    Raises:
        HTTPException: 404 if zone not found
    """
    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    zone = await get_zone_or_404(zone_id, db, camera_id=camera_id)

    await db.delete(zone)
    await db.commit()
