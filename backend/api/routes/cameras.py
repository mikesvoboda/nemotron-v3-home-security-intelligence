"""API routes for camera management."""

import asyncio
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.api.dependencies import (
    get_baseline_service_dep,
    get_cache_service_dep,
    get_camera_or_404,
)
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
    CameraPathValidationResponse,
    CameraResponse,
    CameraUpdate,
    CameraValidationInfo,
    DeletedCamerasListResponse,
)
from backend.api.schemas.pagination import create_pagination_meta
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
from backend.core.constants import CacheInvalidationReason
from backend.core.database import get_db
from backend.core.logging import get_logger, sanitize_log_value
from backend.models.audit import AuditAction
from backend.models.camera import Camera, normalize_camera_id
from backend.models.scene_change import SceneChange
from backend.services.audit import AuditService
from backend.services.baseline import BaselineService
from backend.services.cache_service import (
    SHORT_TTL,
    CacheKeys,
    CacheService,
)

# Type alias for dependency injection
BaselineServiceDep = BaselineService

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

# Video file extensions for fallback snapshot extraction (NEM-2446)
_VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".webm"}

# Snapshot cache TTL in seconds (1 hour) - cached snapshots extracted from videos
# Note: This is now configurable via settings.snapshot_cache_ttl (NEM-2519)
_SNAPSHOT_CACHE_TTL = 3600  # Default, use settings.snapshot_cache_ttl

# Thumbnail size for extracted video frames
_SNAPSHOT_THUMBNAIL_SIZE = (640, 480)


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
            items = result_data["cameras"]
            if validated_fields is not None:
                items = [filter_fields(c, validated_fields) for c in items]
            return CameraListResponse(
                items=items,
                pagination=create_pagination_meta(
                    total=len(result_data["cameras"]),
                    limit=1000,  # No pagination limit for cameras list
                    items_count=len(items),
                ),
            )
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

    cache_response = {
        "cameras": cameras_data,
        "count": len(cameras_data),
    }

    # Cache the result (cache full data, filter on retrieval)
    try:
        await cache.set(cache_key, cache_response, ttl=SHORT_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

    # Apply field filtering before returning (NEM-1434)
    items = cameras_data
    if validated_fields is not None:
        items = [filter_fields(c, validated_fields) for c in cameras_data]

    return CameraListResponse(
        items=items,
        pagination=create_pagination_meta(
            total=len(cameras_data),
            limit=1000,  # No pagination limit for cameras list
            items_count=len(items),
        ),
    )


# =============================================================================
# Soft Delete Trash View Endpoints (NEM-1955)
# NOTE: These endpoints MUST be defined before /{camera_id} to avoid
# "deleted" being matched as a camera_id
# =============================================================================


@router.get(
    "/deleted",
    response_model=DeletedCamerasListResponse,
    summary="List all soft-deleted cameras",
    responses={
        200: {"description": "List of soft-deleted cameras"},
    },
)
async def list_deleted_cameras(
    db: AsyncSession = Depends(get_db),
) -> DeletedCamerasListResponse:
    """List all soft-deleted cameras for trash view.

    Returns cameras that have been soft-deleted (deleted_at is not null),
    ordered by deleted_at descending (most recently deleted first).

    This endpoint enables a "trash" view where users can see deleted cameras
    and optionally restore them.

    Args:
        db: Database session

    Returns:
        DeletedCamerasListResponse containing list of deleted cameras and count
    """
    # Query for cameras where deleted_at is not null
    query = select(Camera).where(Camera.deleted_at.isnot(None)).order_by(Camera.deleted_at.desc())

    result = await db.execute(query)
    deleted_cameras = result.scalars().all()

    # Serialize cameras for response using Pydantic models
    cameras_data = [
        CameraResponse(
            id=c.id,
            name=c.name,
            folder_path=c.folder_path,
            status=c.status,
            created_at=c.created_at,
            last_seen_at=c.last_seen_at,
        )
        for c in deleted_cameras
    ]

    return DeletedCamerasListResponse(
        items=cameras_data,
        pagination=create_pagination_meta(
            total=len(cameras_data),
            limit=1000,  # No pagination limit for deleted cameras list
            items_count=len(cameras_data),
        ),
    )


@router.post(
    "/{camera_id}/restore",
    response_model=CameraResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore a soft-deleted camera",
    responses={
        200: {"description": "Camera restored successfully"},
        400: {"description": "Camera is not deleted"},
        404: {"description": "Camera not found"},
    },
)
async def restore_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> Camera:
    """Restore a soft-deleted camera.

    Clears the deleted_at timestamp on a soft-deleted camera, making it
    visible again in normal queries.

    Args:
        camera_id: ID of the camera to restore
        db: Database session
        cache: Cache service for invalidation

    Returns:
        CameraResponse with the restored camera data

    Raises:
        HTTPException: 404 if camera not found
        HTTPException: 400 if camera is not deleted (nothing to restore)
    """
    # Use include_deleted=True to find soft-deleted cameras
    camera = await get_camera_or_404(camera_id, db, include_deleted=True)

    # Check if the camera is actually deleted
    if camera.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera {camera_id} is not deleted",
        )

    # Restore the camera by clearing deleted_at
    camera.restore()
    await db.commit()
    await db.refresh(camera)

    # Invalidate cameras cache
    try:
        await cache.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_RESTORED)
    except Exception as e:
        logger.warning(f"Cache invalidation failed after camera restore: {e}")

    return camera


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
        await cache.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_CREATED)
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
        await cache.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_UPDATED)
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
        await cache.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_DELETED)
    except Exception:
        logger.warning("Cache invalidation failed", exc_info=True, extra={"camera_id": camera_id})


def _resolve_camera_dir(
    camera_folder_path: str,
    camera_id: str,
    base_root: Path,
) -> Path | None:
    """Resolve the camera directory, handling fallback scenarios.

    NEM-2446: Extracted to reduce branch complexity in get_camera_snapshot.

    Args:
        camera_folder_path: The stored folder path from the camera record
        camera_id: The camera ID (used as fallback)
        base_root: The resolved base FOSCAM_BASE_PATH

    Returns:
        Resolved camera directory Path, or None if not found
    """
    camera_dir = Path(camera_folder_path).resolve()
    try:
        camera_dir.relative_to(base_root)
        # Path is valid and within base_root
        if camera_dir.exists() and camera_dir.is_dir():
            return camera_dir
        return None
    except ValueError:
        # Path is outside base_root - this is not an error, just means we need to
        # try fallback strategies (folder name lookup, camera ID lookup).
        # See: NEM-2540 for rationale
        pass

    # Extract folder name for fallback lookup
    stored_folder_name = Path(camera_folder_path).name
    if ".." in stored_folder_name or "/" in stored_folder_name or "\\" in stored_folder_name:
        logger.warning(
            "Invalid folder name detected, skipping fallback",
            extra={
                "camera_id": camera_id,
                "folder_name": sanitize_log_value(stored_folder_name),
            },
        )
        return None

    # Try fallback by folder name first
    fallback_candidates = [
        (base_root / stored_folder_name).resolve(),
        (base_root / camera_id).resolve(),
    ]

    for fallback_path in fallback_candidates:
        try:
            fallback_path.relative_to(base_root)
            if fallback_path.exists() and fallback_path.is_dir():
                logger.debug(
                    "Using fallback camera path",
                    extra={
                        "camera_id": camera_id,
                        "stored_path": sanitize_log_value(camera_folder_path),
                        "fallback_path": str(fallback_path),
                        "base_path": str(base_root),
                    },
                )
                return fallback_path
        except ValueError:
            continue

    logger.debug(
        "Camera folder_path outside base_path and no fallback found",
        extra={
            "camera_id": camera_id,
            "folder_path": sanitize_log_value(camera_folder_path),
            "base_path": str(base_root),
        },
    )
    return None


def _get_snapshot_cache_path(camera_id: str) -> Path:
    """Get the path for a cached camera snapshot.

    Args:
        camera_id: Camera identifier

    Returns:
        Path to the cached snapshot file
    """
    settings = get_settings()
    cache_dir = Path(settings.foscam_base_path) / ".snapshot_cache"
    return cache_dir / f"{camera_id}_snapshot.jpg"


def _is_cache_valid(cache_path: Path, ttl_seconds: int = _SNAPSHOT_CACHE_TTL) -> bool:
    """Check if a cached snapshot is still valid (not expired).

    Args:
        cache_path: Path to the cached file
        ttl_seconds: Time-to-live in seconds

    Returns:
        True if cache is valid, False otherwise
    """
    if not cache_path.exists():
        return False
    try:
        mtime = cache_path.stat().st_mtime
        return (time.time() - mtime) < ttl_seconds
    except OSError:
        return False


async def _extract_frame_from_video(
    video_path: Path,
    output_path: Path,
    size: tuple[int, int] = _SNAPSHOT_THUMBNAIL_SIZE,
) -> bool:
    """Extract a frame from a video file using ffmpeg.

    NEM-2446: Fallback for cameras with only video files.

    Args:
        video_path: Path to the video file
        output_path: Path to save the extracted frame
        size: Output size (width, height)

    Returns:
        True if extraction succeeded, False otherwise
    """
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command
        # -ss 1: Seek to 1 second (avoid black frames at start)
        # -vframes 1: Extract only 1 frame
        # format=yuvj420p: Convert to full-range YUV for JPEG encoding
        # scale with pad: Maintain aspect ratio with padding
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-ss",
            "1",  # Seek to 1 second
            "-i",
            str(video_path),  # Input file
            "-vframes",
            "1",  # Extract only 1 frame
            "-vf",
            f"format=yuvj420p,scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,"
            f"pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
            "-q:v",
            "2",  # High quality JPEG
            str(output_path),
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.warning(
                "ffmpeg frame extraction failed",
                extra={
                    "video_path": str(video_path),
                    "stderr": result.stderr[:500] if result.stderr else "",
                },
            )
            return False

        if not output_path.exists():
            logger.warning(
                "ffmpeg succeeded but output file not created",
                extra={"output_path": str(output_path)},
            )
            return False

        logger.debug(
            "Extracted snapshot from video",
            extra={
                "video_path": str(video_path),
                "output_path": str(output_path),
            },
        )
        return True

    except subprocess.TimeoutExpired:
        logger.warning(
            "ffmpeg timed out extracting frame",
            extra={"video_path": str(video_path)},
        )
        return False
    except FileNotFoundError:
        logger.warning(
            "ffmpeg not found - video snapshot extraction unavailable",
            extra={"video_path": str(video_path)},
        )
        return False
    except Exception:
        logger.error(
            "Failed to extract frame from video",
            exc_info=True,
            extra={"video_path": str(video_path)},
        )
        return False


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

    NEM-2446: Now supports video-only cameras by extracting and caching frames.
    """
    camera = await get_camera_or_404(camera_id, db)
    settings = get_settings()
    base_root = Path(settings.foscam_base_path).resolve()

    # Resolve camera directory with fallback handling
    camera_dir = _resolve_camera_dir(camera.folder_path, camera_id, base_root)
    if camera_dir is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera folder does not exist",
        )

    # NEM-2446: Implement fallback chain for snapshot retrieval
    # 1. Check for cached snapshot (fast response for video-only cameras)
    cache_path = _get_snapshot_cache_path(camera_id)
    if _is_cache_valid(cache_path):
        logger.debug(
            "Returning cached snapshot",
            extra={"camera_id": camera_id, "cache_path": str(cache_path)},
        )
        return FileResponse(
            path=str(cache_path),
            media_type="image/jpeg",
            filename=f"{camera_id}_snapshot.jpg",
        )

    # 2. Search for image files (.jpg, .png, etc.)
    candidates: list[Path] = []
    for ext in _SNAPSHOT_TYPES:
        candidates.extend(camera_dir.rglob(f"*{ext}"))

    candidates = [p for p in candidates if p.is_file()]
    if candidates:
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        media_type = _SNAPSHOT_TYPES.get(latest.suffix.lower(), "application/octet-stream")
        return FileResponse(path=str(latest), media_type=media_type, filename=latest.name)

    # 3. No images found - try to extract frame from video files
    logger.debug(
        "No image files found, searching for video files",
        extra={"camera_id": camera_id, "camera_dir": str(camera_dir)},
    )

    video_candidates: list[Path] = []
    for ext in _VIDEO_EXTENSIONS:
        video_candidates.extend(camera_dir.rglob(f"*{ext}"))

    video_candidates = [p for p in video_candidates if p.is_file()]
    if not video_candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No snapshot images or video files found for camera",
        )

    # Get the most recent video file
    latest_video = max(video_candidates, key=lambda p: p.stat().st_mtime)
    logger.info(
        "Extracting snapshot from video file",
        extra={
            "camera_id": camera_id,
            "video_path": str(latest_video),
        },
    )

    # Extract frame and cache it
    extraction_success = await _extract_frame_from_video(latest_video, cache_path)
    if extraction_success and cache_path.exists():
        logger.debug(
            "Successfully extracted and cached snapshot from video",
            extra={
                "camera_id": camera_id,
                "cache_path": str(cache_path),
            },
        )
        return FileResponse(
            path=str(cache_path),
            media_type="image/jpeg",
            filename=f"{camera_id}_snapshot.jpg",
        )

    # 4. Video exists but frame extraction failed
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Video files found but frame extraction failed",
    )


@router.get(
    "/validation/paths",
    response_model=CameraPathValidationResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def validate_camera_paths(
    db: AsyncSession = Depends(get_db),
) -> CameraPathValidationResponse:
    """Validate all camera folder paths against the configured base path.

    This endpoint checks each camera's folder_path to determine:
    1. Whether the path is under the configured FOSCAM_BASE_PATH
    2. Whether the directory exists on disk
    3. Whether the directory contains any images or video files

    NEM-2446: Video files (.mkv, .mp4, etc.) are now valid for snapshot
    extraction, so cameras with only video files pass validation.

    Use this to diagnose cameras that show "No snapshot available" errors.

    Returns:
        CameraPathValidationResponse with validation results for all cameras
    """
    settings = get_settings()
    base_root = Path(settings.foscam_base_path).resolve()

    result = await db.execute(select(Camera))
    cameras = result.scalars().all()

    valid_cameras: list[CameraValidationInfo] = []
    invalid_cameras: list[CameraValidationInfo] = []

    for camera in cameras:
        issues: list[str] = []
        resolved_path: str | None = None

        # Check if path is under base_path
        try:
            camera_dir = Path(camera.folder_path).resolve()
            camera_dir.relative_to(base_root)
        except ValueError:
            issues.append(f"folder_path not under base_path ({settings.foscam_base_path})")
            resolved_path = str(Path(camera.folder_path).resolve())

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
                # NEM-2446: Also check for video files (valid for snapshot extraction)
                has_videos = any(list(camera_path.rglob(f"*{ext}")) for ext in _VIDEO_EXTENSIONS)
                if not has_videos:
                    issues.append("no image or video files found")

        camera_info = CameraValidationInfo(
            id=camera.id,
            name=camera.name,
            folder_path=camera.folder_path,
            status=camera.status,
            resolved_path=resolved_path,
            issues=issues if issues else None,
        )

        if issues:
            invalid_cameras.append(camera_info)
        else:
            valid_cameras.append(camera_info)

    return CameraPathValidationResponse(
        base_path=str(base_root),
        total_cameras=len(cameras),
        valid_count=len(valid_cameras),
        invalid_count=len(invalid_cameras),
        valid_cameras=valid_cameras,
        invalid_cameras=invalid_cameras,
    )


@router.get("/{camera_id}/baseline", response_model=BaselineSummaryResponse)
async def get_camera_baseline(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    baseline_service: BaselineServiceDep = Depends(get_baseline_service_dep),
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
        baseline_service: BaselineService injected via Depends()

    Returns:
        BaselineSummaryResponse with all baseline data

    Raises:
        HTTPException: 404 if camera not found
    """
    camera = await get_camera_or_404(camera_id, db)

    # Fetch all baseline data (service injected via DI)
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
    baseline_service: BaselineServiceDep = Depends(get_baseline_service_dep),
) -> AnomalyListResponse:
    """Get recent anomaly events for a camera.

    Returns a list of anomaly events detected within the specified time period.
    Anomalies are detections that significantly deviate from the established
    baseline activity patterns.

    Args:
        camera_id: ID of the camera
        days: Number of days to look back (default: 7, max: 90)
        db: Database session
        baseline_service: BaselineService injected via Depends()

    Returns:
        AnomalyListResponse with list of anomaly events

    Raises:
        HTTPException: 404 if camera not found
    """
    await get_camera_or_404(camera_id, db)

    # Fetch anomalies (service injected via DI)
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
    baseline_service: BaselineServiceDep = Depends(get_baseline_service_dep),
) -> ActivityBaselineResponse:
    """Get raw activity baseline data for a camera.

    Returns up to 168 entries (24 hours x 7 days) representing the full
    weekly activity heatmap. Each entry contains the average count and
    sample count for that hour/day combination.

    Args:
        camera_id: ID of the camera
        db: Database session
        baseline_service: BaselineService injected via Depends()

    Returns:
        ActivityBaselineResponse with entries for the heatmap

    Raises:
        HTTPException: 404 if camera not found
    """
    await get_camera_or_404(camera_id, db)

    # Fetch raw activity baselines (service injected via DI)
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
    baseline_service: BaselineServiceDep = Depends(get_baseline_service_dep),
) -> ClassBaselineResponse:
    """Get class frequency baseline data for a camera.

    Returns baseline entries grouped by object class and hour, showing
    the frequency of each object type at different times of day.

    Args:
        camera_id: ID of the camera
        db: Database session
        baseline_service: BaselineService injected via Depends()

    Returns:
        ClassBaselineResponse with entries for each class/hour combination

    Raises:
        HTTPException: 404 if camera not found
    """
    await get_camera_or_404(camera_id, db)

    # Fetch raw class baselines (service injected via DI)
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
