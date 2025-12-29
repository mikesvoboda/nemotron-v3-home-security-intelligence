"""API routes for camera management."""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraUpdate,
)
from backend.core.config import get_settings
from backend.core.database import get_db
from backend.models.audit import AuditAction
from backend.models.camera import Camera
from backend.services.audit import AuditService

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

# Allowed snapshot types
_SNAPSHOT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}


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
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Create a new camera.

    Args:
        camera_data: Camera creation data
        request: FastAPI request for audit logging
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

    # Log the audit entry
    await AuditService.log_action(
        db=db,
        action=AuditAction.CAMERA_CREATED,
        resource_type="camera",
        resource_id=camera.id,
        actor="anonymous",
        details={
            "name": camera.name,
            "folder_path": camera.folder_path,
            "status": camera.status,
        },
        request=request,
    )

    await db.commit()
    await db.refresh(camera)

    return camera


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: str,
    camera_data: CameraUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Update an existing camera.

    Args:
        camera_id: UUID of the camera to update
        camera_data: Camera update data (all fields optional)
        request: FastAPI request for audit logging
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

    # Track changes for audit log
    old_values = {
        "name": camera.name,
        "folder_path": camera.folder_path,
        "status": camera.status,
    }

    # Update only provided fields
    update_data = camera_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)

    # Build changes dict for audit
    changes: dict[str, Any] = {}
    for field, old_value in old_values.items():
        new_value = getattr(camera, field)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}

    # Log the audit entry
    await AuditService.log_action(
        db=db,
        action=AuditAction.CAMERA_UPDATED,
        resource_type="camera",
        resource_id=camera_id,
        actor="anonymous",
        details={"changes": changes},
        request=request,
    )

    await db.commit()
    await db.refresh(camera)

    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a camera.

    This operation cascades to all related detections and events.

    Args:
        camera_id: UUID of the camera to delete
        request: FastAPI request for audit logging
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

    # Log the audit entry before deletion
    await AuditService.log_action(
        db=db,
        action=AuditAction.CAMERA_DELETED,
        resource_type="camera",
        resource_id=camera_id,
        actor="anonymous",
        details={
            "name": camera.name,
            "folder_path": camera.folder_path,
            "status": camera.status,
        },
        request=request,
    )

    # Delete camera (cascade will handle related data)
    await db.delete(camera)
    await db.commit()


@router.get("/{camera_id}/snapshot", response_class=FileResponse)
async def get_camera_snapshot(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Return the latest image for a camera (best-effort snapshot).

    This endpoint uses the camera's configured `folder_path` and returns the most recently
    modified image file under that directory.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    settings = get_settings()
    base_root = Path(settings.foscam_base_path).resolve()

    camera_dir = Path(camera.folder_path).resolve()
    try:
        camera_dir.relative_to(base_root)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera folder_path is outside configured foscam_base_path",
        ) from err

    if not camera_dir.exists() or not camera_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera folder does not exist",
        )

    candidates: list[Path] = []
    for ext in _SNAPSHOT_TYPES:
        candidates.extend(camera_dir.rglob(f"*{ext}"))

    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No snapshot images found for camera",
        )

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    media_type = _SNAPSHOT_TYPES.get(latest.suffix.lower(), "application/octet-stream")

    return FileResponse(path=str(latest), media_type=media_type, filename=latest.name)
