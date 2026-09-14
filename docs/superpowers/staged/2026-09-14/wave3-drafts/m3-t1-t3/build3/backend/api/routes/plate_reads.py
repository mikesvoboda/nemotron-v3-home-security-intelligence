"""API routes for license plate read management (ALPR).

This module provides endpoints for:
- Listing and querying plate reads
- Retrieving single plate reads by ID
- Getting plate reads for specific cameras
- Searching plate reads by plate text
- Recognizing plates from uploaded images
- Getting recognition statistics

All endpoints follow RESTful conventions and return paginated results
where appropriate.
"""

import base64
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import ORJSONResponse

from backend.api.dependencies import DbSession
from backend.api.schemas.plate_read import (
    PlateReadCreate,
    PlateReadListResponse,
    PlateReadResponse,
    PlateRecognizeRequest,
    PlateRecognizeResponse,
    PlateStatisticsResponse,
)
from backend.core.logging import get_logger
from backend.services.alpr_service import get_alpr_service

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/plate-reads",
    tags=["plate-reads"],
    default_response_class=ORJSONResponse,
)


@router.get("", response_model=PlateReadListResponse)
async def list_plate_reads(
    db: DbSession,
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    start_time: datetime | None = Query(
        None, description="Filter reads after this time (ISO format)"
    ),
    end_time: datetime | None = Query(
        None, description="Filter reads before this time (ISO format)"
    ),
    min_confidence: float | None = Query(
        None, ge=0.0, le=1.0, description="Minimum OCR confidence filter"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page"),
) -> PlateReadListResponse:
    """List plate reads with optional filters.

    Returns a paginated list of plate recognition results with optional
    filtering by camera, time range, and confidence threshold.

    Args:
        db: Database session.
        camera_id: Optional filter by camera ID.
        start_time: Optional start time filter (ISO format).
        end_time: Optional end time filter (ISO format).
        min_confidence: Optional minimum OCR confidence filter (0-1).
        page: Page number (1-indexed, default 1).
        page_size: Number of items per page (1-100, default 50).

    Returns:
        PlateReadListResponse with paginated plate reads.

    Example:
        GET /api/plate-reads?camera_id=driveway&page=1&page_size=25
    """
    service = get_alpr_service(db)
    return await service.get_plate_reads(
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        min_confidence=min_confidence,
        page=page,
        page_size=page_size,
    )


@router.get("/statistics", response_model=PlateStatisticsResponse)
async def get_statistics(db: DbSession) -> PlateStatisticsResponse:
    """Get plate recognition statistics.

    Returns aggregate statistics for ALPR system health monitoring,
    including total reads, average confidence, and recent activity.

    Args:
        db: Database session.

    Returns:
        PlateStatisticsResponse with recognition metrics.

    Example:
        GET /api/plate-reads/statistics
    """
    service = get_alpr_service(db)
    return await service.get_statistics()


@router.get("/search", response_model=PlateReadListResponse)
async def search_by_plate_text(
    db: DbSession,
    text: str = Query(..., min_length=1, description="Plate text to search for"),
    exact: bool = Query(False, description="If true, match exactly; otherwise partial match"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page"),
) -> PlateReadListResponse:
    """Search plate reads by plate text.

    Searches for plate reads matching the given text. By default performs
    a partial match (LIKE %text%). Set exact=true for exact matches only.

    Args:
        db: Database session.
        text: Plate text to search for (required).
        exact: If true, match exactly; if false, partial match (default).
        page: Page number (1-indexed, default 1).
        page_size: Number of items per page (1-100, default 50).

    Returns:
        PlateReadListResponse with matching plate reads.

    Example:
        GET /api/plate-reads/search?text=ABC&exact=false
        GET /api/plate-reads/search?text=ABC1234&exact=true
    """
    service = get_alpr_service(db)
    return await service.search_by_plate_text(
        text=text,
        exact=exact,
        page=page,
        page_size=page_size,
    )


@router.get("/camera/{camera_id}", response_model=PlateReadListResponse)
async def get_reads_by_camera(
    camera_id: str,
    db: DbSession,
    start_time: datetime | None = Query(
        None, description="Filter reads after this time (ISO format)"
    ),
    end_time: datetime | None = Query(
        None, description="Filter reads before this time (ISO format)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page"),
) -> PlateReadListResponse:
    """Get plate reads for a specific camera.

    Returns a paginated list of plate reads from the specified camera
    with optional time range filtering.

    Args:
        camera_id: ID of the camera to get reads for.
        db: Database session.
        start_time: Optional start time filter (ISO format).
        end_time: Optional end time filter (ISO format).
        page: Page number (1-indexed, default 1).
        page_size: Number of items per page (1-100, default 50).

    Returns:
        PlateReadListResponse with camera's plate reads.

    Example:
        GET /api/plate-reads/camera/driveway?page=1&page_size=25
    """
    service = get_alpr_service(db)
    return await service.get_reads_by_camera(
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )


@router.get("/{plate_read_id}", response_model=PlateReadResponse)
async def get_plate_read(
    plate_read_id: int,
    db: DbSession,
) -> PlateReadResponse:
    """Get a single plate read by ID.

    Retrieves full details of a specific plate read record.

    Args:
        plate_read_id: Database ID of the plate read.
        db: Database session.

    Returns:
        PlateReadResponse with the plate read details.

    Raises:
        HTTPException: 404 if plate read not found.

    Example:
        GET /api/plate-reads/123
    """
    service = get_alpr_service(db)
    result = await service.get_plate_read(plate_read_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plate read {plate_read_id} not found",
        )

    return result


@router.post("", response_model=PlateReadResponse, status_code=status.HTTP_201_CREATED)
async def create_plate_read(
    data: PlateReadCreate,
    db: DbSession,
) -> PlateReadResponse:
    """Create a new plate read record.

    Used for manual entry or importing plate reads from external ALPR
    systems. For automatic recognition from images, use POST /recognize.

    Args:
        data: PlateReadCreate schema with plate data.
        db: Database session.

    Returns:
        PlateReadResponse with the created record.

    Example:
        POST /api/plate-reads
        {
            "camera_id": "driveway",
            "timestamp": "2026-01-26T14:30:00Z",
            "plate_text": "ABC1234",
            "raw_text": "ABC-1234",
            "detection_confidence": 0.95,
            "ocr_confidence": 0.92,
            "bbox": [100.0, 200.0, 250.0, 240.0],
            "image_quality_score": 0.85,
            "is_enhanced": false,
            "is_blurry": false
        }
    """
    service = get_alpr_service(db)
    result = await service.create_plate_read(data)
    await db.commit()
    return result


@router.post("/recognize", response_model=PlateRecognizeResponse)
async def recognize_plate(
    request: PlateRecognizeRequest,
    db: DbSession,
    store: bool = Query(True, description="Whether to store the result in database"),
) -> PlateRecognizeResponse:
    """Recognize plate text from an uploaded image.

    Processes the image through PaddleOCR to extract plate text.
    Optionally stores the result in the database.

    The image should be base64-encoded JPEG or PNG data, optionally
    prefixed with a data URL scheme (e.g., "data:image/jpeg;base64,").

    Args:
        request: PlateRecognizeRequest with image data.
        db: Database session.
        store: Whether to store the result (default true).

    Returns:
        PlateRecognizeResponse with recognition results.

    Raises:
        HTTPException: 400 if image decoding fails.
        HTTPException: 500 if OCR processing fails.

    Example:
        POST /api/plate-reads/recognize?store=true
        {
            "camera_id": "driveway",
            "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZ...",
            "detection_bbox": [100.0, 200.0, 250.0, 240.0],
            "detection_confidence": 0.95
        }
    """
    # Decode base64 image
    try:
        image_b64 = request.image_base64
        # Remove data URL prefix if present
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        image_data = base64.b64decode(image_b64)
    except Exception as e:
        logger.warning(f"Failed to decode base64 image: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        ) from None

    try:
        service = get_alpr_service(db)
        result = await service.recognize_and_store(
            camera_id=request.camera_id,
            image_data=image_data,
            bbox=request.detection_bbox or [],
            detection_confidence=request.detection_confidence,
            store=store,
        )
        if store and result.stored:
            await db.commit()
        return result
    except ImportError as e:
        logger.error(f"PaddleOCR not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ALPR service not available (PaddleOCR not installed)",
        ) from e
    except Exception as e:
        logger.error(f"Plate recognition failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plate recognition failed: {e}",
        ) from e
