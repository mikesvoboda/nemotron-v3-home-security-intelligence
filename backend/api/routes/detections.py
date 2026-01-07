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

from backend.api.dependencies import get_detection_or_404
from backend.api.middleware import RateLimiter, RateLimitTier
from backend.api.pagination import CursorData, decode_cursor, encode_cursor, get_deprecation_warning
from backend.api.schemas.detections import (
    DetectionListResponse,
    DetectionResponse,
    DetectionStatsResponse,
    EnrichmentDataSchema,
    PersonEnrichmentData,
    PetEnrichmentData,
    VehicleEnrichmentData,
)
from backend.api.schemas.enrichment import EnrichmentResponse
from backend.api.validators import validate_date_range
from backend.core.database import get_db
from backend.core.mime_types import DEFAULT_VIDEO_MIME, normalize_file_type
from backend.models.detection import Detection
from backend.services.thumbnail_generator import ThumbnailGenerator
from backend.services.video_processor import VideoProcessor

router = APIRouter(prefix="/api/detections", tags=["detections"])

# ============================================================================
# Error Sanitization
# ============================================================================
# Security: Error messages from enrichment processing may contain sensitive
# internal details. These patterns are used to sanitize errors before exposing
# them via the API.

# Known error categories that can be preserved in sanitized output
_ERROR_CATEGORIES = [
    "license plate detection",
    "face detection",
    "violence detection",
    "clothing classification",
    "clothing segmentation",
    "vehicle damage detection",
    "vehicle classification",
    "image quality assessment",
    "pet classification",
    "vision extraction",
    "re-identification",
    "scene change detection",
    "processing",
]


def _sanitize_errors(errors: list[str]) -> list[str]:
    """Sanitize error messages to remove sensitive internal details.

    Security: This function removes file paths, IP addresses, stack traces,
    and other internal details from error messages before exposing them
    via the API.

    Args:
        errors: List of raw error messages from enrichment processing

    Returns:
        List of sanitized error messages safe for API exposure
    """
    if not errors:
        return []

    sanitized = []
    for error in errors:
        # Extract the error category (e.g., "License plate detection")
        category = None
        error_lower = error.lower()
        for cat in _ERROR_CATEGORIES:
            if cat in error_lower:
                category = cat.title()
                break

        # If we found a category, create a generic message
        if category:
            sanitized.append(f"{category} failed")
        else:
            # For unknown error types, use a completely generic message
            sanitized.append("Enrichment processing error")

    return sanitized


# Rate limiter for detection media endpoints (images, videos, thumbnails)
# These endpoints are exempt from auth but need rate limiting for abuse prevention
detection_media_rate_limiter = RateLimiter(tier=RateLimitTier.MEDIA)

# Initialize thumbnail generator and video processor
thumbnail_generator = ThumbnailGenerator()
video_processor = VideoProcessor()


@router.get("", response_model=DetectionListResponse)
async def list_detections(  # noqa: PLR0912
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    object_type: str | None = Query(None, description="Filter by object type"),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    min_confidence: float | None = Query(
        None, ge=0.0, le=1.0, description="Minimum confidence score"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip (deprecated, use cursor)"),
    cursor: str | None = Query(None, description="Pagination cursor from previous response"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List detections with optional filtering and cursor-based pagination.

    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Cursor-based pagination offers better performance for large datasets.

    Args:
        camera_id: Optional camera ID to filter by
        object_type: Optional object type to filter by (person, car, etc.)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        min_confidence: Optional minimum confidence score (0-1)
        limit: Maximum number of results to return (1-100, default 50)
        offset: Number of results to skip (deprecated, use cursor instead)
        cursor: Pagination cursor from previous response's next_cursor field
        db: Database session

    Returns:
        DetectionListResponse containing filtered detections and pagination info

    Raises:
        HTTPException: 400 if start_date is after end_date
        HTTPException: 400 if cursor is invalid
    """
    # Validate date range
    validate_date_range(start_date, end_date)

    # Decode cursor if provided
    cursor_data: CursorData | None = None
    if cursor:
        try:
            cursor_data = decode_cursor(cursor)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cursor: {e}",
            ) from e

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

    # Apply cursor-based pagination filter (takes precedence over offset)
    if cursor_data:
        # For descending order by detected_at, we want records where:
        # - detected_at < cursor's created_at, OR
        # - detected_at == cursor's created_at AND id < cursor's id (tie-breaker)
        query = query.where(
            (Detection.detected_at < cursor_data.created_at)
            | ((Detection.detected_at == cursor_data.created_at) & (Detection.id < cursor_data.id))
        )

    # Get total count (before pagination) - only when not using cursor
    # With cursor pagination, total count becomes expensive and less meaningful
    total_count: int = 0
    if not cursor_data:
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0

    # Sort by detected_at descending (newest first), then by id descending for consistency
    query = query.order_by(Detection.detected_at.desc(), Detection.id.desc())

    # Apply pagination - fetch one extra to determine if there are more results
    # Use explicit if/else for readability (clearer than ternary with complex expressions)
    if cursor_data:  # noqa: SIM108
        # Cursor-based: fetch limit + 1 to check for more
        query = query.limit(limit + 1)
    else:
        # Offset-based (deprecated): apply offset
        query = query.limit(limit + 1).offset(offset)

    # Execute query
    result = await db.execute(query)
    detections = list(result.scalars().all())

    # Determine if there are more results
    has_more = len(detections) > limit
    if has_more:
        detections = detections[:limit]  # Trim to requested limit

    # Generate next cursor from the last detection
    next_cursor: str | None = None
    if has_more and detections:
        last_detection = detections[-1]
        cursor_data_next = CursorData(id=last_detection.id, created_at=last_detection.detected_at)
        next_cursor = encode_cursor(cursor_data_next)

    # Get deprecation warning if using offset without cursor
    deprecation_warning = get_deprecation_warning(cursor, offset)

    return {
        "detections": detections,
        "count": total_count,
        "limit": limit,
        "offset": offset,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "deprecation_warning": deprecation_warning,
    }


@router.get("/stats", response_model=DetectionStatsResponse)
async def get_detection_stats(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get aggregate detection statistics including class distribution.

    Returns:
    - Total detection count
    - Detection counts grouped by object class (person, car, truck, etc.)
    - Average confidence score across all detections

    Used by the AI Performance page to display detection class distribution charts.

    Optimized to use a single query with window functions instead of 3 separate queries
    (NEM-1321). The query combines:
    - Per-class counts via GROUP BY
    - Total count via SUM(COUNT(*)) OVER() window function
    - Per-class avg confidence, then combined using weighted average formula

    Args:
        db: Database session

    Returns:
        DetectionStatsResponse with aggregate detection statistics
    """
    # Use a single query with window functions to get all stats at once
    # This replaces 3 separate queries with 1 optimized query
    #
    # Strategy: First compute per-class stats including count and avg confidence,
    # then use window functions to compute totals across all groups.
    #
    # For weighted average: sum(class_count * class_avg) / sum(class_count)
    combined_query = (
        select(
            Detection.object_type,
            func.count().label("class_count"),
            func.avg(Detection.confidence).label("class_avg_confidence"),
            func.sum(func.count()).over().label("total_count"),
            # Weighted average using window functions:
            # sum(count * avg) over all groups / sum(count) over all groups
            (
                func.sum(func.count() * func.avg(Detection.confidence)).over()
                / func.sum(func.count()).over()
            ).label("avg_confidence"),
        )
        .where(Detection.object_type.isnot(None))
        .group_by(Detection.object_type)
        .order_by(func.count().desc())
    )
    result = await db.execute(combined_query)
    rows = result.all()

    # If no rows, there are no typed detections
    if not rows:
        return {
            "total_detections": 0,
            "detections_by_class": {},
            "average_confidence": None,
        }

    # Extract total count and average confidence from first row
    # (window function values are same across all grouped rows)
    first_row = rows[0]
    total_detections = int(first_row.total_count)
    avg_confidence = first_row.avg_confidence

    # Build detections_by_class dict
    detections_by_class: dict[str, int] = {}
    for row in rows:
        if row.object_type:
            detections_by_class[row.object_type] = row.class_count

    return {
        "total_detections": total_detections,
        "detections_by_class": detections_by_class,
        "average_confidence": float(avg_confidence) if avg_confidence else None,
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
    return await get_detection_or_404(detection_id, db)


def _extract_clothing_from_enrichment(enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
    """Extract clothing data from enrichment into API response format."""
    clothing_classifications = enrichment_data.get("clothing_classifications", {})
    clothing_segmentation = enrichment_data.get("clothing_segmentation", {})

    if not clothing_classifications and not clothing_segmentation:
        return None

    clothing_response: dict[str, Any] = {}
    if clothing_classifications:
        first_key = next(iter(clothing_classifications), None)
        if first_key:
            cc = clothing_classifications[first_key]
            # Parse raw description to extract upper/lower
            raw_desc = cc.get("raw_description", "")
            # When raw_description has no comma, use it directly; fall back to top_category only if empty
            parts = (
                raw_desc.split(", ")
                if ", " in raw_desc
                else [raw_desc if raw_desc else cc.get("top_category")]
            )
            clothing_response["upper"] = parts[0] if parts else None
            clothing_response["lower"] = parts[1] if len(parts) > 1 else None
            clothing_response["is_suspicious"] = cc.get("is_suspicious")
            clothing_response["is_service_uniform"] = cc.get("is_service_uniform")

    if clothing_segmentation:
        first_key = next(iter(clothing_segmentation), None)
        if first_key:
            cs = clothing_segmentation[first_key]
            clothing_response["has_face_covered"] = cs.get("has_face_covered")
            clothing_response["has_bag"] = cs.get("has_bag")
            clothing_response["clothing_items"] = cs.get("clothing_items")

    return clothing_response


def _extract_vehicle_from_enrichment(enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
    """Extract vehicle data from enrichment into API response format."""
    vehicle_classifications = enrichment_data.get("vehicle_classifications", {})
    if not vehicle_classifications:
        return None

    first_key = next(iter(vehicle_classifications), None)
    if not first_key:
        return None

    vc = vehicle_classifications[first_key]
    vehicle_response = {
        "type": vc.get("vehicle_type"),
        "color": None,  # Color not currently captured in enrichment
        "confidence": vc.get("confidence"),
        "is_commercial": vc.get("is_commercial"),
        "damage_detected": None,
        "damage_types": None,
    }
    # Add damage info if present for same detection
    vehicle_damage = enrichment_data.get("vehicle_damage", {})
    if first_key in vehicle_damage:
        vd = vehicle_damage[first_key]
        vehicle_response["damage_detected"] = vd.get("has_damage", False)
        vehicle_response["damage_types"] = vd.get("damage_types", [])

    return vehicle_response


def validate_enrichment_data(enrichment_data: dict[str, Any] | None) -> EnrichmentDataSchema | None:
    """Validate and convert raw enrichment data to typed EnrichmentDataSchema.

    This function converts raw JSONB enrichment data from the database into a
    typed EnrichmentDataSchema for use in DetectionResponse. It extracts the
    relevant fields and creates typed models for vehicle, person, and pet data.

    Args:
        enrichment_data: Raw JSONB enrichment data from the Detection model

    Returns:
        EnrichmentDataSchema if data exists, None otherwise
    """
    if enrichment_data is None:
        return None

    # Extract vehicle data using typed model
    vehicle: VehicleEnrichmentData | None = None
    vehicle_classifications = enrichment_data.get("vehicle_classifications", {})
    if vehicle_classifications:
        first_key = next(iter(vehicle_classifications), None)
        if first_key:
            vc = vehicle_classifications[first_key]
            vehicle_damage = enrichment_data.get("vehicle_damage", {})
            has_damage = False
            if first_key in vehicle_damage:
                has_damage = vehicle_damage[first_key].get("has_damage", False)

            vehicle = VehicleEnrichmentData(
                vehicle_type=vc.get("vehicle_type"),
                vehicle_color=None,  # Color not currently captured in enrichment
                has_damage=has_damage,
                is_commercial=vc.get("is_commercial", False),
            )

    # Extract person data using typed model
    person: PersonEnrichmentData | None = None
    clothing_classifications = enrichment_data.get("clothing_classifications", {})
    if clothing_classifications:
        first_key = next(iter(clothing_classifications), None)
        if first_key:
            cc = clothing_classifications[first_key]
            raw_desc = cc.get("raw_description", "")
            carrying_str = cc.get("carrying", "")
            carrying_list = [carrying_str] if carrying_str else []

            person = PersonEnrichmentData(
                clothing_description=raw_desc if raw_desc else None,
                action=None,  # Action not in clothing classification
                carrying=carrying_list,
                is_suspicious=cc.get("is_suspicious", False),
            )

    # Extract pet data using typed model
    pet: PetEnrichmentData | None = None
    pet_classifications = enrichment_data.get("pet_classifications", {})
    if pet_classifications:
        first_key = next(iter(pet_classifications), None)
        if first_key:
            pc = pet_classifications[first_key]
            pet = PetEnrichmentData(
                pet_type=pc.get("animal_type"),
                breed=None,  # Breed not currently captured
            )

    # Extract errors (sanitized for API exposure)
    errors = _sanitize_errors(enrichment_data.get("errors", []))

    return EnrichmentDataSchema(
        vehicle=vehicle,
        person=person,
        pet=pet,
        weather=None,  # Weather not currently in enrichment pipeline
        errors=errors,
    )


def _transform_enrichment_data(
    detection_id: int,
    enrichment_data: dict[str, Any] | None,
    detected_at: datetime | None,
) -> dict[str, Any]:
    """Transform raw enrichment data from database to structured API response.

    Args:
        detection_id: Detection ID
        enrichment_data: Raw JSONB data from the detection
        detected_at: Detection timestamp (used as fallback for enriched_at)

    Returns:
        Dictionary matching EnrichmentResponse schema
    """
    empty_response: dict[str, Any] = {
        "detection_id": detection_id,
        "enriched_at": detected_at,
        "license_plate": {"detected": False},
        "face": {"detected": False, "count": 0},
        "vehicle": None,
        "clothing": None,
        "violence": {"detected": False, "score": 0.0},
        "weather": None,
        "pose": None,
        "depth": None,
        "image_quality": None,
        "pet": None,
        "processing_time_ms": None,
        "errors": [],
    }

    if enrichment_data is None:
        return empty_response

    # Extract license plate data
    license_plates = enrichment_data.get("license_plates", [])
    license_plate_response: dict[str, Any] = {"detected": False}
    if license_plates:
        plate = license_plates[0]  # Use first plate
        license_plate_response = {
            "detected": True,
            "confidence": plate.get("confidence"),
            "text": plate.get("text"),
            "ocr_confidence": plate.get("ocr_confidence"),
            "bbox": plate.get("bbox"),
        }

    # Extract face data
    faces = enrichment_data.get("faces", [])
    face_response: dict[str, Any] = {"detected": False, "count": 0}
    if faces:
        face_response = {
            "detected": True,
            "count": len(faces),
            "confidence": max(f.get("confidence", 0) for f in faces),
        }

    # Extract violence data
    violence_data = enrichment_data.get("violence_detection")
    violence_response: dict[str, Any] = {"detected": False, "score": 0.0}
    if violence_data:
        violence_response = {
            "detected": violence_data.get("is_violent", False),
            "score": violence_data.get("confidence", 0.0),
            "confidence": violence_data.get("confidence"),
        }

    # Extract image quality data
    image_quality_response: dict[str, Any] | None = None
    iq = enrichment_data.get("image_quality")
    if iq:
        image_quality_response = {
            "score": iq.get("quality_score"),
            "is_blurry": iq.get("is_blurry"),
            "is_low_quality": iq.get("is_low_quality"),
            "quality_issues": iq.get("quality_issues", []),
            "quality_change_detected": enrichment_data.get("quality_change_detected"),
        }

    # Extract pet data
    pet_response: dict[str, Any] | None = None
    pet_classifications = enrichment_data.get("pet_classifications", {})
    if pet_classifications:
        first_key = next(iter(pet_classifications), None)
        if first_key:
            pc = pet_classifications[first_key]
            pet_response = {
                "detected": True,
                "type": pc.get("animal_type"),
                "confidence": pc.get("confidence"),
                "is_household_pet": pc.get("is_household_pet"),
            }

    return {
        "detection_id": detection_id,
        "enriched_at": detected_at,
        "license_plate": license_plate_response,
        "face": face_response,
        "vehicle": _extract_vehicle_from_enrichment(enrichment_data),
        "clothing": _extract_clothing_from_enrichment(enrichment_data),
        "violence": violence_response,
        "weather": None,  # Placeholder - not currently in enrichment pipeline
        "pose": None,  # Placeholder for future ViTPose
        "depth": None,  # Placeholder for future Depth Anything V2
        "image_quality": image_quality_response,
        "pet": pet_response,
        "processing_time_ms": enrichment_data.get("processing_time_ms"),
        # Security: Sanitize error messages to remove sensitive internal details
        "errors": _sanitize_errors(enrichment_data.get("errors", [])),
    }


@router.get("/{detection_id}/enrichment", response_model=EnrichmentResponse)
async def get_detection_enrichment(
    detection_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get structured enrichment data for a detection.

    Returns results from the 18+ vision models run during the enrichment pipeline:
    - License plate detection and OCR
    - Face detection
    - Vehicle classification and damage detection
    - Clothing analysis (FashionCLIP and SegFormer)
    - Violence detection
    - Image quality assessment
    - Pet classification

    Args:
        detection_id: Detection ID
        db: Database session

    Returns:
        EnrichmentResponse with structured vision model results

    Raises:
        HTTPException: 404 if detection not found
    """
    detection = await get_detection_or_404(detection_id, db)
    return _transform_enrichment_data(
        detection_id=detection.id,
        enrichment_data=detection.enrichment_data,
        detected_at=detection.detected_at,
    )


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
    full: bool = Query(False, description="Return full-size original image instead of thumbnail"),
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(detection_media_rate_limiter),
) -> Response:
    """Get detection image with bounding box overlay, or full-size original.

    This endpoint is exempt from API key authentication because:
    1. It serves static image content accessed directly by browsers via <img> tags
    2. Detection IDs are not predictable (integer IDs require prior knowledge)
    3. It has rate limiting to prevent abuse

    By default, returns the thumbnail image with bounding box drawn around the
    detected object. If thumbnail doesn't exist, generates it on the fly from
    the source image.

    When full=true is passed, returns the original source image without any
    bounding box overlay. This is used for the full-size image lightbox viewer.

    Args:
        detection_id: Detection ID
        full: If true, return the original full-size image instead of thumbnail
        db: Database session

    Returns:
        JPEG image (thumbnail with bounding box, or full-size original)

    Raises:
        HTTPException: 404 if detection not found or image file doesn't exist
        HTTPException: 500 if image generation fails
    """
    detection = await get_detection_or_404(detection_id, db)

    # If full=true, return the original source image
    if full:
        if not os.path.exists(detection.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source image not found: {detection.file_path}",
            )

        try:
            # nosemgrep: path-traversal-open - file_path from database, not user input
            with open(detection.file_path, "rb") as f:
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
                detail=f"Failed to read source image: {e!s}",
            ) from e

    # Default behavior: return thumbnail with bounding box
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
        # nosemgrep: path-traversal-open - thumbnail_path derived from database path
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
    detection = await get_detection_or_404(detection_id, db)

    # Verify this is a video detection
    if detection.media_type != "video":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Detection {detection.id} is not a video (media_type: {detection.media_type})",
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
            # nosemgrep: path-traversal-open - file_path from database, not user input
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
            # nosemgrep: path-traversal-open - file_path from database, not user input
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
    detection = await get_detection_or_404(detection_id, db)

    # Verify this is a video detection
    if detection.media_type != "video":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Detection {detection.id} is not a video (media_type: {detection.media_type})",
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
        # nosemgrep: path-traversal-open - thumbnail_path derived from database path
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
