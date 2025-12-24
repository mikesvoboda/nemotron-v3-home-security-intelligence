"""API routes for detections management."""

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.detections import DetectionListResponse, DetectionResponse
from backend.core.database import get_db
from backend.models.detection import Detection
from backend.services.thumbnail_generator import ThumbnailGenerator

router = APIRouter(prefix="/api/detections", tags=["detections"])

# Initialize thumbnail generator
thumbnail_generator = ThumbnailGenerator()


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

    return detection


@router.get("/{detection_id}/image", response_class=Response)
async def get_detection_image(
    detection_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Get detection image with bounding box overlay.

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
