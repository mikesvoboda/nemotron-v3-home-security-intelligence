"""API routes for camera management."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.api.dependencies import get_cache_service_dep, get_camera_or_404
from backend.api.middleware import RateLimiter, RateLimitTier
from backend.api.schemas.baseline import (
    ActivityBaselineEntry,
    ActivityBaselineResponse,
    AnomalyListResponse,
    BaselineSummaryResponse,
    ClassBaselineEntry,
    ClassBaselineResponse,
)
from backend.api.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraUpdate,
)
from backend.api.schemas.scene_change import (
    SceneChangeAcknowledgeResponse,
    SceneChangeListResponse,
    SceneChangeResponse,
)
from backend.api.utils.field_filter import (
    FieldFilterError,
    filter_fields,
    parse_fields_param,
    validate_fields,
)
from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.logging import get_logger, sanitize_log_value
from backend.models.audit import AuditAction
from backend.models.camera import Camera, normalize_camera_id
from backend.models.scene_change import SceneChange
from backend.services.audit import AuditService
from backend.services.baseline import get_baseline_service
from backend.services.cache_service import (
    SHORT_TTL,
    CacheKeys,
    CacheService,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/cameras", tags=["cameras"])

# Rate limiter for snapshot endpoints (same tier as media)
snapshot_rate_limiter = RateLimiter(tier=RateLimitTier.MEDIA)

# Valid fields for sparse fieldsets on list_cameras endpoint (NEM-1434)
VALID_CAMERA_LIST_FIELDS = frozenset(
    {
        "id",
        "name",
        "folder_path",
        "status",
        "created_at",
        "last_seen_at",
    }
)

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
    fields: str | None = Query(
        None,
        description="Comma-separated list of fields to include in response (sparse fieldsets). "
        "Valid fields: id, name, folder_path, status, created_at, last_seen_at",
    ),
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> CameraListResponse:
    """List all cameras with optional status filter.

    Uses Redis cache with cache-aside pattern to improve performance
    and generate cache hit metrics.

    Sparse Fieldsets (NEM-1434):
    Use the `fields` parameter to request only specific fields in the response,
    reducing payload size. Example: ?fields=id,name,status

    Args:
        status_filter: Optional status to filter cameras by (online, offline, error)
        fields: Comma-separated list of fields to include (sparse fieldsets)
        db: Database session
        cache: Cache service injected via FastAPI DI

    Returns:
        CameraListResponse containing list of cameras and total count

    Raises:
        HTTPException: 400 if invalid fields are requested
    """
    # Parse and validate fields parameter for sparse fieldsets (NEM-1434)
    requested_fields = parse_fields_param(fields)
    try:
        validated_fields = validate_fields(requested_fields, set(VALID_CAMERA_LIST_FIELDS))
    except FieldFilterError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    # Generate cache key based on filter
    cache_key = CacheKeys.cameras_list_by_status(status_filter)

    try:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            logger.debug(
                "Returning cached cameras for status=%s",
                sanitize_log_value(status_filter),
            )
            # Cast to expected type - cache stores dict[str, Any]
            result_data = dict(cached_data)
            # Apply field filtering to cached data (NEM-1434)
            if validated_fields is not None:
                result_data["cameras"] = [
                    filter_fields(c, validated_fields) for c in result_data["cameras"]
                ]
            return CameraListResponse(cameras=result_data["cameras"], count=result_data["count"])
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

    # Cache the result (cache full data, filter on retrieval)
    try:
        await cache.set(cache_key, response, ttl=SHORT_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

    # Apply field filtering before returning (NEM-1434)
    if validated_fields is not None:
        # cameras_data is known to be a list of dicts from the code above
        response["cameras"] = [filter_fields(c, validated_fields) for c in cameras_data]

    return CameraListResponse(cameras=response["cameras"], count=response["count"])


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Get a specific camera by ID.

    Args:
        camera_id: Normalized camera ID (e.g., "front_door", "backyard")
        db: Database session

    Returns:
        Camera object

    Raises:
        HTTPException: 404 if camera not found
    """
    return await get_camera_or_404(camera_id, db)


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    camera_data: CameraCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
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
    try:
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
    except Exception:
        logger.error(
            "Failed to commit audit log",
            exc_info=True,
            extra={"action": "camera_created", "camera_id": camera.id},
        )
        await db.rollback()
        # Re-add camera since we rolled back the audit log
        db.add(camera)
        await db.commit()
    await db.refresh(camera)

    # Invalidate cameras cache (NEM-1682: use specific method with reason)
    try:
        await cache.invalidate_cameras(reason="camera_created")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")

    return camera


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: str,
    camera_data: CameraUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> Camera:
    """Update an existing camera.

    Args:
        camera_id: Normalized camera ID (e.g., "front_door", "backyard")
        camera_data: Camera update data (all fields optional)
        request: FastAPI request for audit logging
        db: Database session

    Returns:
        Updated camera object

    Raises:
        HTTPException: 404 if camera not found
    """
    camera = await get_camera_or_404(camera_id, db)

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
    try:
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
    except Exception:
        logger.error(
            "Failed to commit audit log",
            exc_info=True,
            extra={"action": "camera_updated", "camera_id": camera_id},
        )
        await db.rollback()
        # Re-apply the update changes since we rolled back
        update_data = camera_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(camera, field, value)
        await db.commit()
    await db.refresh(camera)

    # Invalidate cameras cache (NEM-1682: use specific method with reason)
    try:
        await cache.invalidate_cameras(reason="camera_updated")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")

    # Type is already narrowed by the None check above
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> None:
    """Delete a camera.

    This operation cascades to all related detections and events.

    Args:
        camera_id: Normalized camera ID (e.g., "front_door", "backyard")
        request: FastAPI request for audit logging
        db: Database session

    Raises:
        HTTPException: 404 if camera not found
    """
    camera = await get_camera_or_404(camera_id, db)

    # Log the audit entry before deletion
    try:
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
    except Exception:
        logger.error(
            "Failed to commit audit log",
            exc_info=True,
            extra={"action": "camera_deleted", "camera_id": camera_id},
        )
        await db.rollback()
        # Retry deletion without audit log - deletion is the primary operation
        await db.delete(camera)
        await db.commit()

    # Invalidate cameras cache (NEM-1682: use specific method with reason)
    try:
        await cache.invalidate_cameras(reason="camera_deleted")
    except Exception:
        logger.warning("Cache invalidation failed", exc_info=True, extra={"camera_id": camera_id})


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
    camera = await get_camera_or_404(camera_id, db)
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
    camera = await get_camera_or_404(camera_id, db)

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
    await get_camera_or_404(camera_id, db)

    # Get baseline service and fetch anomalies
    baseline_service = get_baseline_service()
    anomalies = await baseline_service.get_recent_anomalies(camera_id, days=days, session=db)

    return AnomalyListResponse(
        camera_id=camera_id,
        anomalies=anomalies,
        count=len(anomalies),
        period_days=days,
    )


@router.get("/{camera_id}/baseline/activity", response_model=ActivityBaselineResponse)
async def get_camera_activity_baseline(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> ActivityBaselineResponse:
    """Get raw activity baseline data for a camera.

    Returns up to 168 entries (24 hours x 7 days) representing the full
    weekly activity heatmap. Each entry contains the average count and
    sample count for that hour/day combination.

    Args:
        camera_id: ID of the camera
        db: Database session

    Returns:
        ActivityBaselineResponse with entries for the heatmap

    Raises:
        HTTPException: 404 if camera not found
    """
    await get_camera_or_404(camera_id, db)

    # Get baseline service and fetch raw activity baselines
    baseline_service = get_baseline_service()
    raw_baselines = await baseline_service.get_activity_baselines_raw(camera_id, session=db)

    # Calculate peak values
    total_samples = sum(b.sample_count for b in raw_baselines)
    avg_activity = (
        sum(b.avg_count for b in raw_baselines) / len(raw_baselines) if raw_baselines else 0.0
    )

    # Find peak hour and day
    peak_hour: int | None = None
    peak_day: int | None = None
    if raw_baselines:
        max_baseline = max(raw_baselines, key=lambda b: b.avg_count)
        peak_hour = max_baseline.hour
        peak_day = max_baseline.day_of_week

    # Check learning completion
    # Learning is complete when we have at least min_samples for most time slots
    min_samples_required = baseline_service.min_samples
    slots_with_enough_samples = sum(
        1 for b in raw_baselines if b.sample_count >= min_samples_required
    )
    # Consider learning complete if we have data for at least 80% of slots (168 * 0.8 = 134)
    learning_complete = slots_with_enough_samples >= 134 and len(raw_baselines) >= 134

    # Convert to response entries
    entries = [
        ActivityBaselineEntry(
            hour=b.hour,
            day_of_week=b.day_of_week,
            avg_count=round(b.avg_count, 2),
            sample_count=b.sample_count,
            is_peak=b.avg_count > avg_activity * 1.5,  # More than 50% above average
        )
        for b in raw_baselines
    ]

    return ActivityBaselineResponse(
        camera_id=camera_id,
        entries=entries,
        total_samples=total_samples,
        peak_hour=peak_hour,
        peak_day=peak_day,
        learning_complete=learning_complete,
        min_samples_required=min_samples_required,
    )


@router.get("/{camera_id}/baseline/classes", response_model=ClassBaselineResponse)
async def get_camera_class_baseline(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClassBaselineResponse:
    """Get class frequency baseline data for a camera.

    Returns baseline entries grouped by object class and hour, showing
    the frequency of each object type at different times of day.

    Args:
        camera_id: ID of the camera
        db: Database session

    Returns:
        ClassBaselineResponse with entries for each class/hour combination

    Raises:
        HTTPException: 404 if camera not found
    """
    await get_camera_or_404(camera_id, db)

    # Get baseline service and fetch raw class baselines
    baseline_service = get_baseline_service()
    raw_baselines = await baseline_service.get_class_baselines_raw(camera_id, session=db)

    # Calculate stats
    total_samples = sum(b.sample_count for b in raw_baselines)

    # Get unique classes and find most common
    class_totals: dict[str, int] = {}
    for b in raw_baselines:
        if b.detection_class not in class_totals:
            class_totals[b.detection_class] = 0
        class_totals[b.detection_class] += b.sample_count

    unique_classes = list(class_totals.keys())
    most_common_class = (
        max(class_totals.keys(), key=lambda c: class_totals[c]) if class_totals else None
    )

    # Convert to response entries
    entries = [
        ClassBaselineEntry(
            object_class=b.detection_class,
            hour=b.hour,
            frequency=round(b.frequency, 2),
            sample_count=b.sample_count,
        )
        for b in raw_baselines
    ]

    return ClassBaselineResponse(
        camera_id=camera_id,
        entries=entries,
        unique_classes=unique_classes,
        total_samples=total_samples,
        most_common_class=most_common_class,
    )


@router.get("/{camera_id}/scene-changes", response_model=SceneChangeListResponse)
async def get_camera_scene_changes(
    camera_id: str,
    acknowledged: bool | None = Query(default=None, description="Filter by acknowledgement status"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of results"),
    cursor: datetime | None = Query(
        default=None, description="Cursor for pagination (detected_at timestamp)"
    ),
    db: AsyncSession = Depends(get_db),
) -> SceneChangeListResponse:
    """Get scene changes for a camera with cursor-based pagination.

    Returns a list of detected scene changes that may indicate camera
    tampering, angle changes, or blocked views. Uses cursor-based pagination
    for efficient navigation through large datasets.

    Args:
        camera_id: ID of the camera
        acknowledged: Filter by acknowledgement status (None = all)
        limit: Maximum number of results (default: 50, max: 100)
        cursor: Cursor for pagination (detected_at timestamp from previous response)
        db: Database session

    Returns:
        SceneChangeListResponse with list of scene changes and pagination info

    Raises:
        HTTPException: 404 if camera not found
    """
    # Optimized: Build query for scene changes with eager-loaded camera relationship
    # This enables single query when results exist (NEM-1060)
    query = (
        select(SceneChange)
        .options(joinedload(SceneChange.camera))
        .where(SceneChange.camera_id == camera_id)
    )

    # Apply acknowledged filter if provided
    if acknowledged is not None:
        query = query.where(SceneChange.acknowledged == acknowledged)

    # Apply cursor filter for pagination (fetch items before the cursor timestamp)
    if cursor is not None:
        query = query.where(SceneChange.detected_at < cursor)

    # Order by detected_at descending (most recent first)
    # Fetch one extra to determine if there are more results
    query = query.order_by(SceneChange.detected_at.desc()).limit(limit + 1)

    changes_result = await db.execute(query)
    scene_changes = list(changes_result.unique().scalars().all())

    # If no results, verify camera exists (fallback query only when needed)
    if not scene_changes:
        camera_result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = camera_result.scalar_one_or_none()
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera with id {camera_id} not found",
            )

    # Determine if there are more results
    has_more = len(scene_changes) > limit

    # Calculate next cursor from the last item we'll return
    next_cursor: str | None = None
    if has_more and len(scene_changes) > limit:
        # The cursor should be the detected_at of the last item we return
        next_cursor = scene_changes[limit - 1].detected_at.isoformat()

    # Trim to requested limit
    scene_changes = scene_changes[:limit]

    # Convert to response models
    scene_change_responses = [
        SceneChangeResponse(
            id=sc.id,
            detected_at=sc.detected_at,
            change_type=sc.change_type.value,
            similarity_score=sc.similarity_score,
            acknowledged=sc.acknowledged,
            acknowledged_at=sc.acknowledged_at,
            file_path=sc.file_path,
        )
        for sc in scene_changes
    ]

    return SceneChangeListResponse(
        camera_id=camera_id,
        scene_changes=scene_change_responses,
        total_changes=len(scene_change_responses),
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post(
    "/{camera_id}/scene-changes/{scene_change_id}/acknowledge",
    response_model=SceneChangeAcknowledgeResponse,
)
async def acknowledge_scene_change(
    camera_id: str,
    scene_change_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SceneChangeAcknowledgeResponse:
    """Acknowledge a scene change alert.

    Marks a scene change as acknowledged to indicate it has been reviewed.

    Args:
        camera_id: ID of the camera
        scene_change_id: ID of the scene change to acknowledge
        request: FastAPI request for audit logging
        db: Database session

    Returns:
        SceneChangeAcknowledgeResponse confirming acknowledgement

    Raises:
        HTTPException: 404 if camera or scene change not found
    """
    from datetime import UTC, datetime

    # Optimized: Single query with JOIN to fetch scene change and verify camera exists
    # This reduces database round trips from 2 to 1 (NEM-1060)
    change_result = await db.execute(
        select(SceneChange)
        .options(joinedload(SceneChange.camera))
        .where(SceneChange.id == scene_change_id, SceneChange.camera_id == camera_id)
    )
    scene_change = change_result.unique().scalar_one_or_none()

    if not scene_change:
        # Scene change not found - need to determine if it's because camera doesn't exist
        # or because scene change doesn't exist for this camera
        camera_result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = camera_result.scalar_one_or_none()

        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera with id {camera_id} not found",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene change with id {scene_change_id} not found for camera {camera_id}",
        )

    # NEM-1354: Idempotency - if already acknowledged, return existing data without modification
    if scene_change.acknowledged and scene_change.acknowledged_at:
        return SceneChangeAcknowledgeResponse(
            id=scene_change.id,
            acknowledged=scene_change.acknowledged,
            acknowledged_at=scene_change.acknowledged_at,
        )

    # Update acknowledgement status
    acknowledged_at = datetime.now(UTC)
    scene_change.acknowledged = True
    scene_change.acknowledged_at = acknowledged_at

    # Log the audit entry
    try:
        await AuditService.log_action(
            db=db,
            action=AuditAction.EVENT_REVIEWED,  # Reusing existing audit action
            resource_type="scene_change",
            resource_id=str(scene_change_id),
            actor="anonymous",
            details={
                "camera_id": camera_id,
                "change_type": scene_change.change_type.value,
                "similarity_score": scene_change.similarity_score,
            },
            request=request,
        )
        await db.commit()
    except Exception:
        logger.error(
            "Failed to commit audit log",
            exc_info=True,
            extra={"action": "scene_change_acknowledged", "scene_change_id": scene_change_id},
        )
        await db.rollback()
        # Re-apply the acknowledgement since we rolled back
        scene_change.acknowledged = True
        scene_change.acknowledged_at = acknowledged_at
        await db.commit()
    await db.refresh(scene_change)

    return SceneChangeAcknowledgeResponse(
        id=scene_change.id,
        acknowledged=scene_change.acknowledged,
        acknowledged_at=scene_change.acknowledged_at,
    )
