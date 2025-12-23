"""API routes for camera management."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraUpdate,
)
from backend.core.database import get_db
from backend.models.camera import Camera

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=CameraListResponse)
async def list_cameras(
    status_filter: str | None = Query(None, alias="status", description="Filter by camera status"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all cameras with optional status filter.

    Args:
        status_filter: Optional status to filter cameras by (online, offline, error)
        db: Database session

    Returns:
        CameraListResponse containing list of cameras and total count
    """
    query = select(Camera)

    # Apply status filter if provided
    if status_filter:
        query = query.where(Camera.status == status_filter)

    result = await db.execute(query)
    cameras = result.scalars().all()

    return {
        "cameras": cameras,
        "count": len(cameras),
    }


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Get a specific camera by ID.

    Args:
        camera_id: UUID of the camera
        db: Database session

    Returns:
        Camera object

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


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    camera_data: CameraCreate,
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Create a new camera.

    Args:
        camera_data: Camera creation data
        db: Database session

    Returns:
        Created camera object with generated ID
    """
    # Create camera with generated UUID
    camera = Camera(
        id=str(uuid.uuid4()),
        name=camera_data.name,
        folder_path=camera_data.folder_path,
        status=camera_data.status,
    )

    db.add(camera)
    await db.commit()
    await db.refresh(camera)

    return camera


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: str,
    camera_data: CameraUpdate,
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Update an existing camera.

    Args:
        camera_id: UUID of the camera to update
        camera_data: Camera update data (all fields optional)
        db: Database session

    Returns:
        Updated camera object

    Raises:
        HTTPException: 404 if camera not found
    """
    # Get existing camera
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    # Update only provided fields
    update_data = camera_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)

    await db.commit()
    await db.refresh(camera)

    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a camera.

    This operation cascades to all related detections and events.

    Args:
        camera_id: UUID of the camera to delete
        db: Database session

    Raises:
        HTTPException: 404 if camera not found
    """
    # Get existing camera
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    # Delete camera (cascade will handle related data)
    await db.delete(camera)
    await db.commit()
