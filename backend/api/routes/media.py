"""Media file serving endpoints with security protections."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.middleware import RateLimiter, RateLimitTier
from backend.api.schemas.media import MediaErrorResponse
from backend.core.config import get_settings
from backend.core.database import get_db
from backend.models.detection import Detection

# Rate limiter for media endpoints
media_rate_limiter = RateLimiter(tier=RateLimitTier.MEDIA)

router = APIRouter(prefix="/api/media", tags=["media"])

# Maximum path length to prevent potential buffer overflow attacks
# and filesystem limitations. Most filesystems have limits around 4096 bytes.
MAX_PATH_LENGTH = 4096

# Allowed file types and their content-type mappings
ALLOWED_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
}


def _validate_and_resolve_path(base_path: Path, requested_path: str) -> Path:
    """
    Validate and resolve a file path securely.

    Args:
        base_path: The base directory that files must be within
        requested_path: The user-requested path (relative to base)

    Returns:
        Resolved absolute Path object

    Raises:
        HTTPException: If path is invalid, contains traversal attempts, or file doesn't exist
    """
    # Check path length to prevent buffer overflow attacks and filesystem issues
    if len(requested_path) > MAX_PATH_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_414_URI_TOO_LONG,
            detail=MediaErrorResponse(
                error=f"Path too long. Maximum length is {MAX_PATH_LENGTH} characters.",
                path=requested_path[:100] + "..." if len(requested_path) > 100 else requested_path,
            ).model_dump(),
        )

    # Check for path traversal attempts
    if ".." in requested_path or requested_path.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error="Path traversal detected",
                path=requested_path,
            ).model_dump(),
        )

    # Resolve the full path with error handling for filesystem limits
    try:
        full_path = (base_path / requested_path).resolve()
    except (OSError, ValueError) as err:
        # OSError: filesystem limits exceeded (e.g., path too long for OS)
        # ValueError: invalid path characters or format
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MediaErrorResponse(
                error=f"Invalid path: {type(err).__name__}",
                path=requested_path[:100] + "..." if len(requested_path) > 100 else requested_path,
            ).model_dump(),
        ) from err

    # Ensure the resolved path is still within the base directory
    try:
        full_path.relative_to(base_path.resolve())
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error="Access denied - path outside allowed directory",
                path=requested_path,
            ).model_dump(),
        ) from err

    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MediaErrorResponse(
                error="File not found",
                path=requested_path,
            ).model_dump(),
        )

    # Check file extension is allowed
    file_ext = full_path.suffix.lower()
    if file_ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error=f"File type not allowed: {file_ext}",
                path=requested_path,
            ).model_dump(),
        )

    return full_path


def _is_path_within(path: Path, base: Path) -> bool:
    """Check if a path is within a base directory."""
    try:
        path.relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _try_alternate_path(file_path: str, base_path: Path) -> Path | None:
    """Try to find file under base_path if it references seeded data path."""
    seeded_prefix = "/app/data/cameras/"
    if not file_path.startswith(seeded_prefix):
        return None
    relative = file_path[len(seeded_prefix) :]
    alt_path = (base_path / relative).resolve()
    if alt_path.exists() and alt_path.is_file() and _is_path_within(alt_path, base_path):
        return alt_path
    return None


# NOTE: This catch-all route MUST be defined FIRST because tests rely on it
# calling serve_thumbnail/serve_camera_file as functions (which can be patched).
# When specific routes are first, FastAPI calls the registered handler directly,
# bypassing any module-level patches.
@router.get(
    "/{path:path}",
    response_class=FileResponse,
    responses={
        200: {"description": "File served successfully"},
        403: {"model": MediaErrorResponse, "description": "Access denied"},
        404: {"model": MediaErrorResponse, "description": "File not found"},
        429: {"description": "Too many requests"},
    },
)
async def serve_media_compat(
    path: str, _rate_limit: None = Depends(media_rate_limiter)
) -> FileResponse:
    """Compatibility route: serve media via design-spec-style /api/media/{path}.

    This preserves the stricter behavior of the new routes:
    - Path traversal protection
    - Allowed file type allowlist
    - Must remain under configured base directories

    Mapping rules:
    - `cameras/<camera_id>/<filename...>` -> camera media
    - `thumbnails/<filename>` -> thumbnails
    - `detections/<id>` -> detection images
    """
    # Normalize: strip any leading slashes (FastAPI path params shouldn't include it, but be safe).
    rel = path.lstrip("/")

    if rel.startswith("cameras/"):
        # cameras/<camera_id>/<filename...>
        remainder = rel.removeprefix("cameras/")
        if "/" not in remainder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=MediaErrorResponse(
                    error="File not found",
                    path=path,
                ).model_dump(),
            )
        camera_id, filename = remainder.split("/", 1)
        return await serve_camera_file(camera_id=camera_id, filename=filename)

    if rel.startswith("thumbnails/"):
        filename = rel.removeprefix("thumbnails/")
        return await serve_thumbnail(filename=filename)

    if rel.startswith("detections/"):
        detection_id_str = rel.removeprefix("detections/")
        try:
            detection_id = int(detection_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=MediaErrorResponse(
                    error="Invalid detection ID",
                    path=path,
                ).model_dump(),
            ) from None
        # Get database session manually for detections
        async for db in get_db():
            try:
                return await serve_detection_image(detection_id=detection_id, db=db)
            finally:
                await db.close()
        # Should never reach here, but handle edge case
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MediaErrorResponse(
                error="Database connection unavailable",
                path=path,
            ).model_dump(),
        )

    if rel.startswith("clips/"):
        filename = rel.removeprefix("clips/")
        return await serve_clip(filename=filename)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=MediaErrorResponse(
            error="Unsupported media path (expected cameras/..., thumbnails/..., detections/..., or clips/...)",
            path=path,
        ).model_dump(),
    )


@router.get(
    "/cameras/{camera_id}/{filename:path}",
    response_class=FileResponse,
    responses={
        200: {"description": "File served successfully"},
        403: {"model": MediaErrorResponse, "description": "Access denied"},
        404: {"model": MediaErrorResponse, "description": "File not found"},
        429: {"description": "Too many requests"},
    },
)
async def serve_camera_file(
    camera_id: str, filename: str, _rate_limit: None = Depends(media_rate_limiter)
) -> FileResponse:
    """
    Serve camera images or videos from Foscam storage.

    Args:
        camera_id: The camera identifier (directory name)
        filename: The file to serve (can include subdirectories)

    Returns:
        FileResponse with appropriate content-type header

    Raises:
        HTTPException: 403 for invalid paths, 404 for missing files
    """
    # Additional security check on camera_id as well
    if ".." in camera_id or camera_id.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error="Invalid camera identifier",
                path=camera_id,
            ).model_dump(),
        )

    settings = get_settings()
    base_path = Path(settings.foscam_base_path) / camera_id

    # Construct the relative path (camera_id is already part of base_path)
    full_path = _validate_and_resolve_path(base_path, filename)

    # Get content type from extension
    content_type = ALLOWED_TYPES[full_path.suffix.lower()]

    return FileResponse(
        path=str(full_path),
        media_type=content_type,
        filename=full_path.name,
    )


@router.get(
    "/thumbnails/{filename}",
    response_class=FileResponse,
    responses={
        200: {"description": "Thumbnail served successfully"},
        403: {"model": MediaErrorResponse, "description": "Access denied"},
        404: {"model": MediaErrorResponse, "description": "File not found"},
        429: {"description": "Too many requests"},
    },
)
async def serve_thumbnail(
    filename: str, _rate_limit: None = Depends(media_rate_limiter)
) -> FileResponse:
    """
    Serve detection thumbnail images.

    Args:
        filename: The thumbnail filename

    Returns:
        FileResponse with appropriate content-type header

    Raises:
        HTTPException: 403 for invalid paths, 404 for missing files
    """
    # Thumbnails are stored in backend/data/thumbnails/
    base_path = Path(__file__).parent.parent.parent / "data" / "thumbnails"

    full_path = _validate_and_resolve_path(base_path, filename)

    # Get content type from extension
    content_type = ALLOWED_TYPES[full_path.suffix.lower()]

    return FileResponse(
        path=str(full_path),
        media_type=content_type,
        filename=full_path.name,
    )


async def serve_detection_image(
    detection_id: int,
    db: AsyncSession,
) -> FileResponse:
    """
    Serve the image associated with a detection.

    Args:
        detection_id: The detection ID to look up
        db: Database session

    Returns:
        FileResponse with the detection's source image

    Raises:
        HTTPException: 404 if detection not found or file doesn't exist
    """
    # Look up the detection
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MediaErrorResponse(
                error="Detection not found",
                path=f"detections/{detection_id}",
            ).model_dump(),
        )

    # Get the file path from the detection
    file_path = detection.file_path
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MediaErrorResponse(
                error="Detection has no associated file",
                path=f"detections/{detection_id}",
            ).model_dump(),
        )

    # Resolve paths
    settings = get_settings()
    base_path = Path(settings.foscam_base_path)
    data_path = Path(__file__).parent.parent.parent.parent / "data" / "cameras"

    # Determine full path (absolute or relative)
    full_path = (
        Path(file_path)
        if Path(file_path).is_absolute()
        else base_path / detection.camera_id / file_path
    ).resolve()

    # Security check: ensure path is within allowed directories
    if not _is_path_within(full_path, base_path) and not _is_path_within(full_path, data_path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error="Access denied - file outside allowed directory",
                path=f"detections/{detection_id}",
            ).model_dump(),
        )

    # Try alternate path if file doesn't exist (seeded data -> real camera path)
    if not full_path.exists() or not full_path.is_file():
        alt_path = _try_alternate_path(file_path, base_path)
        if alt_path:
            full_path = alt_path

    # Final check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MediaErrorResponse(
                error="File not found on disk",
                path=f"detections/{detection_id}",
            ).model_dump(),
        )

    # Check file extension is allowed
    file_ext = full_path.suffix.lower()
    if file_ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error=f"File type not allowed: {file_ext}",
                path=f"detections/{detection_id}",
            ).model_dump(),
        )

    content_type = ALLOWED_TYPES[file_ext]

    return FileResponse(
        path=str(full_path),
        media_type=content_type,
        filename=full_path.name,
    )


@router.get(
    "/clips/{filename}",
    response_class=FileResponse,
    responses={
        200: {"description": "Clip served successfully"},
        403: {"model": MediaErrorResponse, "description": "Access denied"},
        404: {"model": MediaErrorResponse, "description": "File not found"},
        429: {"description": "Too many requests"},
    },
)
async def serve_clip(
    filename: str, _rate_limit: None = Depends(media_rate_limiter)
) -> FileResponse:
    """
    Serve event video clips.

    Clips are generated by the ClipGenerator service and stored in the
    configured clips directory.

    Args:
        filename: The clip filename (e.g., "123_clip.mp4")

    Returns:
        FileResponse with appropriate content-type header

    Raises:
        HTTPException: 403 for invalid paths, 404 for missing files
    """
    from backend.services.clip_generator import get_clip_generator

    # Get clips directory from clip generator
    clip_generator = get_clip_generator()
    base_path = clip_generator.clips_directory

    full_path = _validate_and_resolve_path(base_path, filename)

    # Get content type from extension
    content_type = ALLOWED_TYPES[full_path.suffix.lower()]

    return FileResponse(
        path=str(full_path),
        media_type=content_type,
        filename=full_path.name,
    )
