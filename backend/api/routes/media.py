"""Media file serving endpoints with security protections."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.middleware import RateLimiter, RateLimitTier
from backend.api.schemas.media import MediaErrorResponse
from backend.core.config import get_settings

# Rate limiter for media endpoints
media_rate_limiter = RateLimiter(tier=RateLimitTier.MEDIA)

router = APIRouter(prefix="/api/media", tags=["media"])

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
    # Check for path traversal attempts
    if ".." in requested_path or requested_path.startswith("/"):
        raise HTTPException(
            status_code=403,
            detail=MediaErrorResponse(
                error="Path traversal detected",
                path=requested_path,
            ).model_dump(),
        )

    # Resolve the full path
    full_path = (base_path / requested_path).resolve()

    # Ensure the resolved path is still within the base directory
    try:
        full_path.relative_to(base_path.resolve())
    except ValueError as err:
        raise HTTPException(
            status_code=403,
            detail=MediaErrorResponse(
                error="Access denied - path outside allowed directory",
                path=requested_path,
            ).model_dump(),
        ) from err

    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=MediaErrorResponse(
                error="File not found",
                path=requested_path,
            ).model_dump(),
        )

    # Check file extension is allowed
    file_ext = full_path.suffix.lower()
    if file_ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=403,
            detail=MediaErrorResponse(
                error=f"File type not allowed: {file_ext}",
                path=requested_path,
            ).model_dump(),
        )

    return full_path


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
    - `cameras/<camera_id>/<filename...>` → camera media
    - `thumbnails/<filename>` → thumbnails
    """
    # Normalize: strip any leading slashes (FastAPI path params shouldn't include it, but be safe).
    rel = path.lstrip("/")

    if rel.startswith("cameras/"):
        # cameras/<camera_id>/<filename...>
        remainder = rel.removeprefix("cameras/")
        if "/" not in remainder:
            raise HTTPException(
                status_code=404,
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

    raise HTTPException(
        status_code=404,
        detail=MediaErrorResponse(
            error="Unsupported media path (expected cameras/... or thumbnails/...)",
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
            status_code=403,
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
