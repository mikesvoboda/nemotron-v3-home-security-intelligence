"""API routes for detections management."""

import os
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.middleware import RateLimiter, RateLimitTier
from backend.api.schemas.detections import DetectionListResponse, DetectionResponse
from backend.core.database import get_db
from backend.core.mime_types import DEFAULT_VIDEO_MIME, normalize_file_type
from backend.models.detection import Detection
from backend.services.thumbnail_generator import ThumbnailGenerator
from backend.services.video_processor import VideoProcessor

router = APIRouter(prefix="/api/detections", tags=["detections"])

# Rate limiter for detection media endpoints (images, videos, thumbnails)
# These endpoints are exempt from auth but need rate limiting for abuse prevention
detection_media_rate_limiter = RateLimiter(tier=RateLimitTier.MEDIA)

# Initialize thumbnail generator and video processor
thumbnail_generator = ThumbnailGenerator()
video_processor = VideoProcessor()


@router.get("", response_model=DetectionListResponse)
async def list_detections(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    object_type: str | None = Query(None, description="Filter by object type"),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    min_confidence: float | None = Query(
        None, ge=0.0, le=1.0, description="Minimum confidence score"
    ),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List detections with optional filtering and pagination.

    Args:
        camera_id: Optional camera ID to filter by
        object_type: Optional object type to filter by (person, car, etc.)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        min_confidence: Optional minimum confidence score (0-1)
        limit: Maximum number of results to return (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        db: Database session

    Returns:
        DetectionListResponse containing filtered detections and pagination info
    """
    # Build base query
    query = select(Detection)

    # Apply filters
    if camera_id:
        query = query.where(Detection.camera_id == camera_id)
    if object_type:
        query = query.where(Detection.object_type == object_type)
    if start_date:
        query = query.where(Detection.detected_at >= start_date)
    if end_date:
        query = query.where(Detection.detected_at <= end_date)
    if min_confidence is not None:
        query = query.where(Detection.confidence >= min_confidence)

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort by detected_at descending (newest first)
    query = query.order_by(Detection.detected_at.desc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    detections = result.scalars().all()

    return {
        "detections": detections,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{detection_id}", response_model=DetectionResponse)
async def get_detection(
    detection_id: int,
    db: AsyncSession = Depends(get_db),
) -> Detection:
    """Get a specific detection by ID.

    Args:
        detection_id: Detection ID
        db: Database session

    Returns:
        Detection object

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

    # Type is already narrowed by the None check above
    return detection


@router.get(
    "/{detection_id}/image",
    response_class=Response,
    responses={
        200: {"description": "Image served successfully"},
        404: {"description": "Detection or image not found"},
        429: {"description": "Too many requests"},
        500: {"description": "Failed to generate thumbnail"},
    },
)
async def get_detection_image(
    detection_id: int,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(detection_media_rate_limiter),
) -> Response:
    """Get detection image with bounding box overlay.

    This endpoint is exempt from API key authentication because:
    1. It serves static image content accessed directly by browsers via <img> tags
    2. Detection IDs are not predictable (integer IDs require prior knowledge)
    3. It has rate limiting to prevent abuse

    Returns the thumbnail image with bounding box drawn around the detected object.
    If thumbnail doesn't exist, generates it on the fly from the source image.

    Args:
        detection_id: Detection ID
        db: Database session

    Returns:
        JPEG image with bounding box overlay

    Raises:
        HTTPException: 404 if detection not found or image file doesn't exist
        HTTPException: 500 if image generation fails
    """
    # Get detection from database
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection with id {detection_id} not found",
        )

    # Check if thumbnail exists
    thumbnail_path: str
    if detection.thumbnail_path and os.path.exists(detection.thumbnail_path):
        thumbnail_path = detection.thumbnail_path
    else:
        # Generate thumbnail on the fly
        if not os.path.exists(detection.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source image not found: {detection.file_path}",
            )

        # Prepare detection data for thumbnail generation
        detection_data = {
            "object_type": detection.object_type,
            "confidence": detection.confidence,
            "bbox_x": detection.bbox_x,
            "bbox_y": detection.bbox_y,
            "bbox_width": detection.bbox_width,
            "bbox_height": detection.bbox_height,
        }

        # Generate thumbnail
        generated_path = thumbnail_generator.generate_thumbnail(
            image_path=detection.file_path,
            detections=[detection_data],
            detection_id=str(detection.id),
        )

        if not generated_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate thumbnail image",
            )

        thumbnail_path = generated_path

        # Update detection with thumbnail path
        detection.thumbnail_path = thumbnail_path
        await db.commit()

    # Read and return image
    try:
        with open(thumbnail_path, "rb") as f:
            image_data = f.read()

        return Response(
            content=image_data,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read thumbnail image: {e!s}",
        ) from e


def _parse_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    """Parse HTTP Range header and return start/end byte positions.

    Args:
        range_header: Range header value (e.g., "bytes=0-1023")
        file_size: Total file size in bytes

    Returns:
        Tuple of (start, end) byte positions

    Raises:
        ValueError: If range header is invalid
    """
    if not range_header.startswith("bytes="):
        raise ValueError("Invalid range header format")

    range_spec = range_header[6:]  # Remove "bytes=" prefix

    if range_spec.startswith("-"):
        # Suffix range: last N bytes (e.g., "-500" means last 500 bytes)
        suffix_length = int(range_spec[1:])
        start = max(0, file_size - suffix_length)
        end = file_size - 1
    elif range_spec.endswith("-"):
        # Open-ended range (e.g., "500-" means from byte 500 to end)
        start = int(range_spec[:-1])
        end = file_size - 1
    else:
        # Explicit range (e.g., "0-1023")
        parts = range_spec.split("-")
        if len(parts) != 2:
            raise ValueError("Invalid range specification")
        start = int(parts[0])
        end = int(parts[1]) if parts[1] else file_size - 1

    # Clamp to valid range
    start = max(0, start)
    end = min(end, file_size - 1)

    if start > end:
        raise ValueError("Invalid range: start > end")

    return start, end


@router.get(
    "/{detection_id}/video",
    response_class=StreamingResponse,
    responses={
        200: {"description": "Full video content"},
        206: {"description": "Partial video content (range request)"},
        400: {"description": "Detection is not a video"},
        404: {"description": "Detection or video file not found"},
        416: {"description": "Range not satisfiable"},
        429: {"description": "Too many requests"},
    },
)
async def stream_detection_video(
    detection_id: int,
    range_header: str | None = Header(None, alias="Range"),
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(detection_media_rate_limiter),
) -> StreamingResponse:
    """Stream detection video with HTTP Range request support.

    This endpoint is exempt from API key authentication because:
    1. It serves video content accessed directly by browsers via <video> tags
    2. Detection IDs are not predictable (integer IDs require prior knowledge)
    3. It has rate limiting to prevent abuse

    Supports partial content requests for video seeking and efficient playback.
    Returns 206 Partial Content for range requests, 200 OK for full content.

    Args:
        detection_id: Detection ID
        range_header: HTTP Range header for partial content requests
        db: Database session

    Returns:
        StreamingResponse with video content

    Raises:
        HTTPException: 404 if detection not found or not a video
        HTTPException: 416 if range is not satisfiable
    """
    # Get detection from database
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection with id {detection_id} not found",
        )

    # Verify this is a video detection
    if detection.media_type != "video":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Detection {detection_id} is not a video (media_type: {detection.media_type})",
        )

    # Check video file exists
    if not os.path.exists(detection.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file not found: {detection.file_path}",
        )

    file_size = Path(detection.file_path).stat().st_size
    # Normalize file_type to MIME type, handling legacy extension values (e.g., ".mp4")
    content_type = (
        normalize_file_type(detection.file_type, detection.file_path) or DEFAULT_VIDEO_MIME
    )

    # Handle range request
    if range_header:
        try:
            start, end = _parse_range_header(range_header, file_size)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail=str(e),
                headers={"Content-Range": f"bytes */{file_size}"},
            ) from e

        content_length = end - start + 1

        def iter_file_range() -> Generator[bytes]:
            """Generator to stream file range."""
            with open(detection.file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                chunk_size = 64 * 1024  # 64KB chunks

                while remaining > 0:
                    read_size = min(chunk_size, remaining)
                    data = f.read(read_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_file_range(),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )
    else:
        # Full content request
        def iter_file() -> Generator[bytes]:
            """Generator to stream entire file."""
            chunk_size = 64 * 1024  # 64KB chunks
            with open(detection.file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk

        return StreamingResponse(
            iter_file(),
            status_code=status.HTTP_200_OK,
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )


@router.get(
    "/{detection_id}/video/thumbnail",
    response_class=Response,
    responses={
        200: {"description": "Thumbnail served successfully"},
        400: {"description": "Detection is not a video"},
        404: {"description": "Detection or video not found"},
        429: {"description": "Too many requests"},
        500: {"description": "Failed to generate thumbnail"},
    },
)
async def get_video_thumbnail(
    detection_id: int,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(detection_media_rate_limiter),
) -> Response:
    """Get thumbnail frame from a video detection.

    This endpoint is exempt from API key authentication because:
    1. It serves static image content accessed directly by browsers via <img> tags
    2. Detection IDs are not predictable (integer IDs require prior knowledge)
    3. It has rate limiting to prevent abuse

    Extracts and returns a thumbnail frame from the video. If thumbnail
    doesn't exist, generates it on the fly using ffmpeg.

    Args:
        detection_id: Detection ID
        db: Database session

    Returns:
        JPEG thumbnail image

    Raises:
        HTTPException: 404 if detection not found or not a video
        HTTPException: 500 if thumbnail generation fails
    """
    # Get detection from database
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection with id {detection_id} not found",
        )

    # Verify this is a video detection
    if detection.media_type != "video":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Detection {detection_id} is not a video (media_type: {detection.media_type})",
        )

    # Check if thumbnail already exists
    thumbnail_path: str
    if detection.thumbnail_path and os.path.exists(detection.thumbnail_path):
        thumbnail_path = detection.thumbnail_path
    else:
        # Check video file exists
        if not os.path.exists(detection.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video file not found: {detection.file_path}",
            )

        # Generate thumbnail using video processor
        generated_path = await video_processor.extract_thumbnail_for_detection(
            video_path=detection.file_path,
            detection_id=detection.id,
        )

        if not generated_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate video thumbnail",
            )

        thumbnail_path = generated_path

        # Update detection with thumbnail path
        detection.thumbnail_path = thumbnail_path
        await db.commit()

    # Read and return thumbnail
    try:
        with open(thumbnail_path, "rb") as f:
            image_data = f.read()

        return Response(
            content=image_data,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read video thumbnail: {e!s}",
        ) from e
