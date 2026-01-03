"""API routes for camera management."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.middleware import RateLimiter, RateLimitTier
from backend.api.schemas.baseline import AnomalyListResponse, BaselineSummaryResponse
from backend.api.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraUpdate,
)
from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.logging import get_logger, sanitize_log_value
from backend.models.audit import AuditAction
from backend.models.camera import Camera, normalize_camera_id
from backend.services.audit import AuditService
from backend.services.baseline import get_baseline_service
from backend.services.cache_service import (
    SHORT_TTL,
    CacheKeys,
    get_cache_service,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/cameras", tags=["cameras"])

# Rate limiter for snapshot endpoints (same tier as media)
snapshot_rate_limiter = RateLimiter(tier=RateLimitTier.MEDIA)

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

    Uses Redis cache with cache-aside pattern to improve performance
    and generate cache hit metrics.

    Args:
        status_filter: Optional status to filter cameras by (online, offline, error)
        db: Database session

    Returns:
        CameraListResponse containing list of cameras and total count
    """
    # Generate cache key based on filter
    cache_key = CacheKeys.cameras_list_by_status(status_filter)

    try:
        cache = await get_cache_service()
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            logger.debug(
                "Returning cached cameras for status=%s",
                sanitize_log_value(status_filter),
            )
            # Cast to expected type - cache stores dict[str, Any]
            return dict(cached_data)
    except Exception as e:
        logger.warning(f"Cache read failed, falling back to database: {e}")

    # Cache miss - query database
    query = select(Camera)

    # Apply status filter if provided
    if status_filter:
        query = query.where(Camera.status == status_filter)

    result = await db.execute(query)
    cameras = result.scalars().all()

    # Serialize cameras for cache (SQLAlchemy objects can't be directly cached)
    cameras_data = [
        {
            "id": c.id,
            "name": c.name,
            "folder_path": c.folder_path,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None,
        }
        for c in cameras
    ]

    response = {
        "cameras": cameras_data,
        "count": len(cameras_data),
    }

    # Cache the result
    try:
        cache = await get_cache_service()
        await cache.set(cache_key, response, ttl=SHORT_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

    return response


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

    # Type is already narrowed by the None check above
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

    Raises:
        HTTPException: 409 if camera with same name or folder_path already exists
    """
    # Check if a camera with the same name already exists
    existing_name_result = await db.execute(select(Camera).where(Camera.name == camera_data.name))
    existing_name_camera = existing_name_result.scalar_one_or_none()

    if existing_name_camera:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera with name '{camera_data.name}' already exists "
            f"(id: {existing_name_camera.id})",
        )

    # Check if a camera with the same folder_path already exists
    existing_path_result = await db.execute(
        select(Camera).where(Camera.folder_path == camera_data.folder_path)
    )
    existing_path_camera = existing_path_result.scalar_one_or_none()

    if existing_path_camera:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera with folder_path '{camera_data.folder_path}' already exists "
            f"(id: {existing_path_camera.id})",
        )

    # Create camera using normalized ID from the name
    # This ensures the camera ID matches what FileWatcher will use when processing files
    # from this camera's folder_path. Without this, detector_client can't update last_seen_at.
    camera_id = normalize_camera_id(camera_data.name)
    camera = Camera(
        id=camera_id,
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

    # Invalidate cameras cache
    try:
        cache = await get_cache_service()
        await cache.invalidate_pattern("cameras:*")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")

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

    # Invalidate cameras cache
    try:
        cache = await get_cache_service()
        await cache.invalidate_pattern("cameras:*")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")

    # Type is already narrowed by the None check above
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

    # Invalidate cameras cache
    try:
        cache = await get_cache_service()
        await cache.invalidate_pattern("cameras:*")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")


@router.get(
    "/{camera_id}/snapshot",
    response_class=FileResponse,
    responses={
        200: {"description": "Snapshot served successfully"},
        404: {"description": "Camera or snapshot not found"},
        429: {"description": "Too many requests"},
    },
)
async def get_camera_snapshot(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(snapshot_rate_limiter),
) -> FileResponse:
    """Return the latest image for a camera (best-effort snapshot).

    This endpoint is exempt from API key authentication because:
    1. It serves static image content accessed directly by browsers via <img> tags
    2. It has its own security controls (path traversal protection, file type allowlist)
    3. It has rate limiting to prevent abuse

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
    except ValueError:
        # Stored folder_path is outside the current FOSCAM_BASE_PATH.
        # This commonly happens when:
        # - Database has cameras from a different environment (Docker vs native)
        # - Container FOSCAM_BASE_PATH (/cameras) differs from dev path (/export/foscam)
        #
        # Fallback strategy:
        # 1. First, try to extract the folder name from the stored path and look for it
        #    under base_path. This handles cases where the camera name differs from the
        #    folder name (e.g., camera name "Den Camera" but folder is "den").
        # 2. If that fails, try the camera_id directly (works when name == folder name).
        #
        # This is safe because we only look within FOSCAM_BASE_PATH (no traversal).
        # Extract folder name and validate it doesn't contain path traversal
        stored_folder_name = Path(camera.folder_path).name
        # Validate folder name doesn't contain path separators or traversal sequences
        if ".." in stored_folder_name or "/" in stored_folder_name or "\\" in stored_folder_name:
            logger.warning(
                "Invalid folder name detected, skipping fallback",
                extra={
                    "camera_id": camera_id,
                    "folder_name": sanitize_log_value(stored_folder_name),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No snapshot available for this camera",
            ) from None

        # Construct fallback paths and verify they resolve within base_root
        fallback_by_folder_name = (base_root / stored_folder_name).resolve()
        fallback_by_camera_id = (base_root / camera_id).resolve()

        # Security check: ensure resolved paths are within base_root
        try:
            fallback_by_folder_name.relative_to(base_root)
        except ValueError:
            fallback_by_folder_name = None  # type: ignore[assignment]
        try:
            fallback_by_camera_id.relative_to(base_root)
        except ValueError:
            fallback_by_camera_id = None  # type: ignore[assignment]

        if (
            fallback_by_folder_name
            and fallback_by_folder_name.exists()
            and fallback_by_folder_name.is_dir()
        ):
            # Found camera folder by stored folder name
            logger.debug(
                "Using fallback camera path by folder name",
                extra={
                    "camera_id": camera_id,
                    "stored_path": sanitize_log_value(camera.folder_path),
                    "stored_folder_name": sanitize_log_value(stored_folder_name),
                    "fallback_path": str(fallback_by_folder_name),
                    "base_path": str(base_root),
                },
            )
            camera_dir = fallback_by_folder_name
        elif (
            fallback_by_camera_id
            and fallback_by_camera_id.exists()
            and fallback_by_camera_id.is_dir()
        ):
            # Found camera folder by camera ID
            logger.debug(
                "Using fallback camera path by camera ID",
                extra={
                    "camera_id": camera_id,
                    "stored_path": sanitize_log_value(camera.folder_path),
                    "fallback_path": str(fallback_by_camera_id),
                    "base_path": str(base_root),
                },
            )
            camera_dir = fallback_by_camera_id
        else:
            # No fallback available - return 404
            logger.debug(
                "Camera folder_path outside base_path and no fallback found",
                extra={
                    "camera_id": camera_id,
                    "folder_path": sanitize_log_value(camera.folder_path),
                    "base_path": str(base_root),
                    "fallback_by_folder_name_tried": str(fallback_by_folder_name),
                    "fallback_by_camera_id_tried": str(fallback_by_camera_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No snapshot available for this camera",
            ) from None

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


@router.get("/validation/paths")
async def validate_camera_paths(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Validate all camera folder paths against the configured base path.

    This endpoint checks each camera's folder_path to determine:
    1. Whether the path is under the configured FOSCAM_BASE_PATH
    2. Whether the directory exists on disk
    3. Whether the directory contains any images

    Use this to diagnose cameras that show "No snapshot available" errors.

    Returns:
        Dictionary with validation results for all cameras
    """
    settings = get_settings()
    base_root = Path(settings.foscam_base_path).resolve()

    result = await db.execute(select(Camera))
    cameras = result.scalars().all()

    valid_cameras: list[dict[str, Any]] = []
    invalid_cameras: list[dict[str, Any]] = []

    for camera in cameras:
        camera_info: dict[str, Any] = {
            "id": camera.id,
            "name": camera.name,
            "folder_path": camera.folder_path,
            "status": camera.status,
        }

        issues: list[str] = []

        # Check if path is under base_path
        try:
            camera_dir = Path(camera.folder_path).resolve()
            camera_dir.relative_to(base_root)
        except ValueError:
            issues.append(f"folder_path not under base_path ({settings.foscam_base_path})")
            camera_info["resolved_path"] = str(Path(camera.folder_path).resolve())

        # Check if directory exists
        camera_path = Path(camera.folder_path)
        if not camera_path.exists():
            issues.append("directory does not exist")
        elif not camera_path.is_dir():
            issues.append("path is not a directory")
        else:
            # Check for images - use any() on actual file matches, not generators
            has_images = any(
                list(camera_path.rglob(f"*{ext}")) for ext in [".jpg", ".jpeg", ".png", ".gif"]
            )
            if not has_images:
                issues.append("no image files found")

        if issues:
            camera_info["issues"] = issues
            invalid_cameras.append(camera_info)
        else:
            valid_cameras.append(camera_info)

    return {
        "base_path": str(base_root),
        "total_cameras": len(cameras),
        "valid_count": len(valid_cameras),
        "invalid_count": len(invalid_cameras),
        "valid_cameras": valid_cameras,
        "invalid_cameras": invalid_cameras,
    }


@router.get("/{camera_id}/baseline", response_model=BaselineSummaryResponse)
async def get_camera_baseline(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> BaselineSummaryResponse:
    """Get baseline activity data for a camera.

    Returns comprehensive baseline statistics including:
    - Hourly activity patterns (0-23 hours)
    - Daily patterns (by day of week)
    - Object-specific baselines
    - Current deviation from baseline

    Args:
        camera_id: ID of the camera
        db: Database session

    Returns:
        BaselineSummaryResponse with all baseline data

    Raises:
        HTTPException: 404 if camera not found
    """
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    # Get baseline service and fetch data
    baseline_service = get_baseline_service()

    # Fetch all baseline data
    summary = await baseline_service.get_camera_baseline_summary(camera_id, session=db)
    hourly_patterns = await baseline_service.get_hourly_patterns(camera_id, session=db)
    daily_patterns = await baseline_service.get_daily_patterns(camera_id, session=db)
    object_baselines = await baseline_service.get_object_baselines(camera_id, session=db)
    current_deviation = await baseline_service.get_current_deviation(camera_id, session=db)
    baseline_established = await baseline_service.get_baseline_established_date(
        camera_id, session=db
    )

    # Calculate total data points
    data_points = summary["activity_baseline_count"] + summary["class_baseline_count"]

    return BaselineSummaryResponse(
        camera_id=camera_id,
        camera_name=camera.name,
        baseline_established=baseline_established,
        data_points=data_points,
        hourly_patterns=hourly_patterns,
        daily_patterns=daily_patterns,
        object_baselines=object_baselines,
        current_deviation=current_deviation,
    )


@router.get("/{camera_id}/baseline/anomalies", response_model=AnomalyListResponse)
async def get_camera_baseline_anomalies(
    camera_id: str,
    days: int = Query(default=7, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
) -> AnomalyListResponse:
    """Get recent anomaly events for a camera.

    Returns a list of anomaly events detected within the specified time period.
    Anomalies are detections that significantly deviate from the established
    baseline activity patterns.

    Args:
        camera_id: ID of the camera
        days: Number of days to look back (default: 7, max: 90)
        db: Database session

    Returns:
        AnomalyListResponse with list of anomaly events

    Raises:
        HTTPException: 404 if camera not found
    """
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    # Get baseline service and fetch anomalies
    baseline_service = get_baseline_service()
    anomalies = await baseline_service.get_recent_anomalies(camera_id, days=days, session=db)

    return AnomalyListResponse(
        camera_id=camera_id,
        anomalies=anomalies,
        count=len(anomalies),
        period_days=days,
    )
