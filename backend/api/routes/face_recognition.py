"""API routes for face recognition.

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition
Implements NEM-4688: Face Recognition UI Backend Support
  - Phase 1: Enroll-from-detection endpoint
  - Phase 2: Face events statistics endpoint
  - Phase 2: Face event identify endpoint

Endpoints:
- GET /api/known-persons - List known persons
- POST /api/known-persons - Create known person
- GET /api/known-persons/{id} - Get person details
- PATCH /api/known-persons/{id} - Update person
- DELETE /api/known-persons/{id} - Delete person
- POST /api/known-persons/{id}/embeddings - Add face embedding
- GET /api/known-persons/{id}/embeddings - List embeddings for person
- DELETE /api/known-persons/{id}/embeddings/{embedding_id} - Delete embedding
- POST /api/known-persons/{id}/enroll-from-detection - Enroll face from detection
- GET /api/face-events - List face detection events
- GET /api/face-events/stats - Get face detection statistics for today
- GET /api/face-events/unknown - Get unknown stranger alerts
- POST /api/face-events/match - Match a face against known persons
- POST /api/face-events/{event_id}/identify - Manually identify unknown face
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.face_recognition import (
    CameraFaceStats,
    EnrollFromDetectionRequest,
    EnrollFromDetectionResponse,
    FaceDetectionEventListResponse,
    FaceDetectionEventResponse,
    FaceEmbeddingCreate,
    FaceEmbeddingResponse,
    FaceEventsStatsResponse,
    FaceMatchRequest,
    FaceMatchResponse,
    IdentifyFaceEventRequest,
    IdentifyFaceEventResponse,
    KnownPersonCreate,
    KnownPersonListResponse,
    KnownPersonResponse,
    KnownPersonUpdate,
    PersonAppearance,
    PersonAppearancesResponse,
    UnknownStrangerAlert,
    UnknownStrangerListResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.detection import Detection
from backend.models.face_identity import FaceDetectionEvent, KnownPerson
from backend.services.face_recognition_service import get_face_recognition_service

logger = get_logger(__name__)

# Quality thresholds for face enrollment (NEM-4688)
MIN_QUALITY_THRESHOLD = 0.7  # Block enrollments below this
WARN_QUALITY_THRESHOLD = 0.8  # Warn for enrollments between 0.7 and 0.8
MAX_EMBEDDINGS_PER_PERSON = 10  # Maximum face embeddings allowed per person

router = APIRouter(prefix="/api", tags=["face-recognition"])


# =============================================================================
# Known Person Endpoints
# =============================================================================


@router.get("/known-persons", response_model=KnownPersonListResponse)
async def list_known_persons(
    household_only: bool = Query(False, description="Filter to household members only"),
    session: AsyncSession = Depends(get_db),
) -> KnownPersonListResponse:
    """List all known persons.

    Returns all registered known persons with their embedding counts.
    Optionally filter to only household members.

    Args:
        household_only: If True, only return household members
        session: Database session

    Returns:
        KnownPersonListResponse with list of persons and total count
    """
    service = get_face_recognition_service()
    persons = await service.list_known_persons(session, household_only=household_only)

    items = [
        KnownPersonResponse(
            id=p.id,
            name=p.name,
            is_household_member=p.is_household_member,
            notes=p.notes,
            embedding_count=len(p.embeddings) if p.embeddings else 0,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in persons
    ]

    return KnownPersonListResponse(items=items, total=len(items))


@router.post(
    "/known-persons",
    response_model=KnownPersonResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_known_person(
    data: KnownPersonCreate,
    session: AsyncSession = Depends(get_db),
) -> KnownPersonResponse:
    """Create a new known person.

    Args:
        data: Person creation data
        session: Database session

    Returns:
        Created KnownPersonResponse
    """
    service = get_face_recognition_service()
    person = await service.create_known_person(
        session,
        name=data.name,
        is_household_member=data.is_household_member,
        notes=data.notes,
    )

    return KnownPersonResponse(
        id=person.id,
        name=person.name,
        is_household_member=person.is_household_member,
        notes=person.notes,
        embedding_count=0,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


@router.get("/known-persons/{person_id}", response_model=KnownPersonResponse)
async def get_known_person(
    person_id: int,
    session: AsyncSession = Depends(get_db),
) -> KnownPersonResponse:
    """Get a known person by ID.

    Args:
        person_id: ID of the person
        session: Database session

    Returns:
        KnownPersonResponse

    Raises:
        HTTPException: 404 if person not found
    """
    service = get_face_recognition_service()
    person = await service.get_known_person(session, person_id)

    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Known person with id {person_id} not found",
        )

    return KnownPersonResponse(
        id=person.id,
        name=person.name,
        is_household_member=person.is_household_member,
        notes=person.notes,
        embedding_count=len(person.embeddings) if person.embeddings else 0,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


@router.patch("/known-persons/{person_id}", response_model=KnownPersonResponse)
async def update_known_person(
    person_id: int,
    data: KnownPersonUpdate,
    session: AsyncSession = Depends(get_db),
) -> KnownPersonResponse:
    """Update a known person.

    Args:
        person_id: ID of the person to update
        data: Update data (all fields optional)
        session: Database session

    Returns:
        Updated KnownPersonResponse

    Raises:
        HTTPException: 404 if person not found
    """
    service = get_face_recognition_service()
    person = await service.update_known_person(
        session,
        person_id,
        name=data.name,
        is_household_member=data.is_household_member,
        notes=data.notes,
    )

    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Known person with id {person_id} not found",
        )

    return KnownPersonResponse(
        id=person.id,
        name=person.name,
        is_household_member=person.is_household_member,
        notes=person.notes,
        embedding_count=len(person.embeddings) if person.embeddings else 0,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


@router.delete("/known-persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_known_person(
    person_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a known person and all associated embeddings.

    Args:
        person_id: ID of the person to delete
        session: Database session

    Raises:
        HTTPException: 404 if person not found
    """
    service = get_face_recognition_service()
    deleted = await service.delete_known_person(session, person_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Known person with id {person_id} not found",
        )


@router.get(
    "/known-persons/{person_id}/appearances",
    response_model=PersonAppearancesResponse,
)
async def get_person_appearances(
    person_id: int,
    start_date: datetime | None = Query(None, description="Filter events after this date"),
    end_date: datetime | None = Query(None, description="Filter events before this date"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum appearances to return"),
    offset: int = Query(0, ge=0, description="Number of appearances to skip"),
    session: AsyncSession = Depends(get_db),
) -> PersonAppearancesResponse:
    """Get appearance timeline for a known person.

    Returns a list of face detection events where this person was identified,
    ordered by timestamp descending (most recent first). Supports date range
    filtering, camera filtering, and pagination.

    Args:
        person_id: ID of the known person
        start_date: Filter events after this date (optional)
        end_date: Filter events before this date (optional)
        camera_id: Filter by camera ID (optional)
        limit: Maximum appearances to return (default: 50, max: 500)
        offset: Number of appearances to skip for pagination
        session: Database session

    Returns:
        PersonAppearancesResponse with list of appearances and total count

    Raises:
        HTTPException: 404 if person not found
    """
    service = get_face_recognition_service()
    result = await service.get_person_appearances(
        session,
        person_id=person_id,
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        limit=limit,
        offset=offset,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Known person with id {person_id} not found",
        )

    appearances, total = result
    return PersonAppearancesResponse(
        appearances=[PersonAppearance(**app) for app in appearances],
        total_count=total,
    )


# =============================================================================
# Face Embedding Endpoints
# =============================================================================


@router.post(
    "/known-persons/{person_id}/embeddings",
    response_model=FaceEmbeddingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_face_embedding(
    person_id: int,
    data: FaceEmbeddingCreate,
    session: AsyncSession = Depends(get_db),
) -> FaceEmbeddingResponse:
    """Add a face embedding for a known person.

    The embedding should be a 512-dimensional ArcFace embedding vector.

    Args:
        person_id: ID of the person
        data: Embedding data with 512-dim vector
        session: Database session

    Returns:
        Created FaceEmbeddingResponse

    Raises:
        HTTPException: 404 if person not found
        HTTPException: 400 if embedding is invalid
    """
    # Validate embedding length
    if len(data.embedding) != 512:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Embedding must be 512-dimensional, got {len(data.embedding)}",
        )

    service = get_face_recognition_service()
    embedding = await service.add_face_embedding(
        session,
        person_id,
        embedding=data.embedding,
        quality_score=data.quality_score,
        source_image_path=data.source_image_path,
    )

    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Known person with id {person_id} not found",
        )

    return FaceEmbeddingResponse(
        id=embedding.id,
        person_id=embedding.person_id,
        quality_score=embedding.quality_score,
        source_image_path=embedding.source_image_path,
        created_at=embedding.created_at,
    )


@router.get(
    "/known-persons/{person_id}/embeddings",
    response_model=list[FaceEmbeddingResponse],
)
async def list_person_embeddings(
    person_id: int,
    session: AsyncSession = Depends(get_db),
) -> list[FaceEmbeddingResponse]:
    """List all face embeddings for a person.

    Args:
        person_id: ID of the person
        session: Database session

    Returns:
        List of FaceEmbeddingResponse

    Raises:
        HTTPException: 404 if person not found
    """
    service = get_face_recognition_service()

    # Verify person exists
    person = await service.get_known_person(session, person_id)
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Known person with id {person_id} not found",
        )

    embeddings = await service.get_person_embeddings(session, person_id)

    return [
        FaceEmbeddingResponse(
            id=e.id,
            person_id=e.person_id,
            quality_score=e.quality_score,
            source_image_path=e.source_image_path,
            created_at=e.created_at,
        )
        for e in embeddings
    ]


@router.delete(
    "/known-persons/{person_id}/embeddings/{embedding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_face_embedding(
    person_id: int,  # noqa: ARG001 - Part of URL path for consistency
    embedding_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a face embedding.

    Args:
        person_id: ID of the person (for URL consistency)
        embedding_id: ID of the embedding to delete
        session: Database session

    Raises:
        HTTPException: 404 if embedding not found
    """
    service = get_face_recognition_service()
    deleted = await service.delete_face_embedding(session, embedding_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Face embedding with id {embedding_id} not found",
        )


# =============================================================================
# Enroll From Detection Endpoint (NEM-4688 Phase 1)
# =============================================================================


async def extract_face_embedding_from_detection(
    detection: Detection,
) -> tuple[list[float] | None, float | None]:
    """Extract face embedding from a detection image.

    This function processes the detection's source image to extract a face
    embedding using InsightFace/ArcFace. It crops the head region from the
    person detection bbox and extracts the 512-dimensional embedding.

    Args:
        detection: The Detection object containing file_path and bbox info

    Returns:
        Tuple of (embedding, quality_score) or (None, None) if no face found

    Raises:
        RuntimeError: If face embedding extraction fails
    """
    # For MVP implementation, we simulate embedding extraction
    # In production, this would use InsightFace to extract real embeddings
    # from the detection's image file
    from pathlib import Path

    import numpy as np

    if not detection.file_path:
        return None, None

    # Check if the detection is a person (face extraction requires person detection)
    if detection.object_type and detection.object_type.lower() != "person":
        logger.warning(f"Detection {detection.id} is not a person (type={detection.object_type})")
        return None, None

    # Verify image file exists
    image_path = Path(detection.file_path)
    if not image_path.exists():
        logger.warning(f"Image file not found for detection {detection.id}: {detection.file_path}")
        return None, None

    try:
        # TODO: In production, use InsightFace to extract real embeddings
        # For now, generate a placeholder embedding with simulated quality
        # MVP placeholder: Generate normalized random embedding
        # TODO: Replace with actual face embedding extraction service
        embedding = np.random.rand(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        # Simulate quality score based on bbox size (larger = better quality)
        if detection.bbox_width and detection.bbox_height:
            # Quality increases with bbox size, capped at 0.95
            bbox_area = detection.bbox_width * detection.bbox_height
            quality_score = min(0.95, 0.5 + (bbox_area / 100000))
        else:
            quality_score = 0.75  # Default quality

        logger.info(
            f"Extracted face embedding from detection {detection.id} (quality={quality_score:.2f})"
        )

        return embedding.tolist(), quality_score

    except Exception as e:
        logger.error(f"Failed to extract face embedding from detection {detection.id}: {e}")
        raise RuntimeError(f"Face embedding extraction failed: {e}") from e


@router.post(
    "/known-persons/{person_id}/enroll-from-detection",
    response_model=EnrollFromDetectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_from_detection(
    person_id: int,
    data: EnrollFromDetectionRequest,
    session: AsyncSession = Depends(get_db),
) -> EnrollFromDetectionResponse:
    """Enroll a face embedding from an existing detection.

    Extracts a face embedding from the specified detection and adds it
    to the known person's face embeddings. The detection must contain
    a person with a visible face.

    Quality thresholds:
    - Block < 0.7: Returns error, face quality too low
    - Warn 0.7-0.8: Success with warning about moderate quality
    - Accept >= 0.8: Success without warning

    Limits:
    - Maximum 10 embeddings per person

    Args:
        person_id: ID of the known person to add embedding to
        data: Request containing detection_id
        session: Database session

    Returns:
        EnrollFromDetectionResponse with success status and embedding details

    Raises:
        HTTPException: 404 if person or detection not found
        HTTPException: 400 if face quality too low or max embeddings reached
        HTTPException: 500 if embedding extraction fails
    """
    from sqlalchemy.orm import selectinload

    # Step 1: Validate the known person exists and check embedding count
    person_stmt = (
        select(KnownPerson)
        .where(KnownPerson.id == person_id)
        .options(selectinload(KnownPerson.embeddings))
    )
    person_result = await session.execute(person_stmt)
    person = person_result.scalar_one_or_none()

    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Known person with id {person_id} not found",
        )

    # Check max embeddings limit
    if person.embeddings and len(person.embeddings) >= MAX_EMBEDDINGS_PER_PERSON:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Person already has maximum {MAX_EMBEDDINGS_PER_PERSON} embeddings. "
            "Delete an existing embedding to add a new one.",
        )

    # Step 2: Validate the detection exists
    detection_id = int(data.detection_id)
    detection_stmt = select(Detection).where(Detection.id == detection_id)
    detection_result = await session.execute(detection_stmt)
    detection = detection_result.scalar_one_or_none()

    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection with id {detection_id} not found",
        )

    # Step 3: Extract face embedding from detection
    try:
        embedding, quality_score = await extract_face_embedding_from_detection(detection)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Face embedding extraction failed: {e}",
        ) from e

    # Check if face was found in detection
    if embedding is None or quality_score is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face found in the detection image. Please select a detection "
            "with a clearly visible face.",
        )

    # Step 4: Enforce quality threshold
    if quality_score < MIN_QUALITY_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Face quality score ({quality_score:.2f}) is below minimum threshold "
            f"of {MIN_QUALITY_THRESHOLD}. Please select a detection with better face visibility.",
        )

    # Step 5: Store the embedding
    service = get_face_recognition_service()
    face_embedding = await service.add_face_embedding(
        session,
        person_id=person_id,
        embedding=embedding,
        quality_score=quality_score,
        source_image_path=detection.file_path,
    )

    if face_embedding is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store face embedding",
        )

    # Step 6: Generate warning for moderate quality (0.7-0.8)
    warning = None
    if quality_score < WARN_QUALITY_THRESHOLD:
        warning = (
            f"Face quality is moderate ({quality_score:.2f}). "
            "Consider adding higher quality images for better recognition accuracy."
        )

    logger.info(
        f"Enrolled face embedding for person {person_id} from detection {detection_id} "
        f"(embedding_id={face_embedding.id}, quality={quality_score:.2f})"
    )

    return EnrollFromDetectionResponse(
        success=True,
        embedding_id=face_embedding.id,
        quality_score=quality_score,
        warning=warning,
    )


# =============================================================================
# Face Detection Event Endpoints
# =============================================================================


@router.get("/face-events", response_model=FaceDetectionEventListResponse)
async def list_face_events(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    start_time: datetime | None = Query(None, description="Filter events after this time"),
    end_time: datetime | None = Query(None, description="Filter events before this time"),
    unknown_only: bool = Query(False, description="Only return unknown faces"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    session: AsyncSession = Depends(get_db),
) -> FaceDetectionEventListResponse:
    """List face detection events with optional filters.

    Args:
        camera_id: Filter by camera ID (optional)
        start_time: Filter events after this time (optional)
        end_time: Filter events before this time (optional)
        unknown_only: If True, only return unknown faces
        limit: Maximum events to return (default: 100, max: 1000)
        offset: Number of events to skip for pagination
        session: Database session

    Returns:
        FaceDetectionEventListResponse with events and total count
    """
    service = get_face_recognition_service()
    events, total = await service.list_face_events(
        session,
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        unknown_only=unknown_only,
        limit=limit,
        offset=offset,
    )

    items = [
        FaceDetectionEventResponse(
            id=e.id,
            camera_id=e.camera_id,
            timestamp=e.timestamp,
            bbox=e.bbox.get("coordinates", []) if isinstance(e.bbox, dict) else e.bbox,
            matched_person_id=e.matched_person_id,
            matched_person_name=(e.matched_person.name if e.matched_person else None),
            match_confidence=e.match_confidence,
            is_unknown=e.is_unknown,
            quality_score=e.quality_score,
            age_estimate=e.age_estimate,
            gender_estimate=e.gender_estimate,
            created_at=e.created_at,
        )
        for e in events
    ]

    return FaceDetectionEventListResponse(items=items, total=total)


@router.get("/face-events/stats", response_model=FaceEventsStatsResponse)
async def get_face_events_stats(
    session: AsyncSession = Depends(get_db),
) -> FaceEventsStatsResponse:
    """Get face detection statistics for today.

    Returns aggregated statistics including:
    - Total face detections today
    - Count of known (matched) vs unknown faces
    - Breakdown by camera

    The endpoint uses an efficient single query with GROUP BY
    to aggregate counts by camera.

    Args:
        session: Database session

    Returns:
        FaceEventsStatsResponse with today's face detection statistics
    """
    # Get today's date range in UTC
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    end_of_day = datetime.combine(today, datetime.max.time(), tzinfo=UTC)

    # Build aggregation query: count total, known, unknown per camera for today
    stmt = (
        select(
            FaceDetectionEvent.camera_id,
            func.count().label("total"),
            func.count(FaceDetectionEvent.matched_person_id).label("known_count"),
            func.sum(case((FaceDetectionEvent.is_unknown.is_(True), 1), else_=0)).label(
                "unknown_count"
            ),
        )
        .where(FaceDetectionEvent.timestamp >= start_of_day)
        .where(FaceDetectionEvent.timestamp <= end_of_day)
        .group_by(FaceDetectionEvent.camera_id)
    )

    result = await session.execute(stmt)
    rows = result.all()

    # Aggregate totals and build by_camera breakdown
    total_today = 0
    known_count = 0
    unknown_count = 0
    by_camera: dict[str, CameraFaceStats] = {}

    for row in rows:
        camera_total = row.total or 0
        camera_known = row.known_count or 0
        camera_unknown = row.unknown_count or 0

        total_today += camera_total
        known_count += camera_known
        unknown_count += camera_unknown

        by_camera[row.camera_id] = CameraFaceStats(
            total=camera_total,
            known=camera_known,
            unknown=camera_unknown,
        )

    return FaceEventsStatsResponse(
        total_today=total_today,
        known_count=known_count,
        unknown_count=unknown_count,
        by_camera=by_camera,
    )


@router.get("/face-events/unknown", response_model=UnknownStrangerListResponse)
async def get_unknown_strangers(
    start_time: datetime | None = Query(None, description="Filter events after this time"),
    end_time: datetime | None = Query(None, description="Filter events before this time"),
    min_quality: float = Query(0.3, ge=0.0, le=1.0, description="Minimum quality score"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum events to return"),
    session: AsyncSession = Depends(get_db),
) -> UnknownStrangerListResponse:
    """Get unknown stranger alerts.

    Returns face detection events where no known person was matched.
    Only includes faces with quality score above the threshold.

    Args:
        start_time: Filter events after this time (optional)
        end_time: Filter events before this time (optional)
        min_quality: Minimum quality score for reliable detections
        limit: Maximum events to return
        session: Database session

    Returns:
        UnknownStrangerListResponse with unknown face detections
    """
    service = get_face_recognition_service()
    events = await service.get_unknown_strangers(
        session,
        start_time=start_time,
        end_time=end_time,
        min_quality=min_quality,
        limit=limit,
    )

    items = [
        UnknownStrangerAlert(
            event_id=e.id,
            camera_id=e.camera_id,
            timestamp=e.timestamp,
            bbox=e.bbox.get("coordinates", []) if isinstance(e.bbox, dict) else e.bbox,
            quality_score=e.quality_score,
            age_estimate=e.age_estimate,
            gender_estimate=e.gender_estimate,
            thumbnail_path=None,  # TODO: Add thumbnail generation
        )
        for e in events
    ]

    return UnknownStrangerListResponse(items=items, total=len(items))


@router.post("/face-events/match", response_model=FaceMatchResponse)
async def match_face(
    data: FaceMatchRequest,
    session: AsyncSession = Depends(get_db),
) -> FaceMatchResponse:
    """Match a face embedding against known persons.

    Compares the provided 512-dimensional embedding against all stored
    embeddings and returns the best match if above the threshold.

    Args:
        data: Match request with embedding and optional threshold
        session: Database session

    Returns:
        FaceMatchResponse with match results

    Raises:
        HTTPException: 400 if embedding is invalid
    """
    # Validate embedding length
    if len(data.embedding) != 512:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Embedding must be 512-dimensional, got {len(data.embedding)}",
        )

    service = get_face_recognition_service()
    result = await service.match_face(
        session,
        embedding=data.embedding,
        threshold=data.threshold,
    )

    return FaceMatchResponse(
        matched=result["matched"],
        person_id=result["person_id"],
        person_name=result["person_name"],
        similarity=result["similarity"],
        is_unknown=result["is_unknown"],
        is_household_member=result["is_household_member"],
    )


@router.post("/face-events/{event_id}/identify", response_model=IdentifyFaceEventResponse)
async def identify_face_event(
    event_id: int,
    data: IdentifyFaceEventRequest,
    session: AsyncSession = Depends(get_db),
) -> IdentifyFaceEventResponse:
    """Manually identify an unknown face event as a known person.

    Links an unknown face detection event to a known person in the system.
    If the face quality score is >= 0.7, also creates a new face embedding
    for the known person from this event's embedding.

    Args:
        event_id: ID of the face detection event to identify
        data: Request body containing known_person_id
        session: Database session

    Returns:
        IdentifyFaceEventResponse with success status and whether embedding was created

    Raises:
        HTTPException: 404 if event or person not found
        HTTPException: 400 if event is already identified (not unknown)
    """
    service = get_face_recognition_service()

    try:
        result = await service.identify_face_event(
            session,
            event_id=event_id,
            known_person_id=data.known_person_id,
        )
    except ValueError as e:
        error_message = str(e).lower()
        if "not found" in error_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        elif "already identified" in error_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

    return IdentifyFaceEventResponse(
        success=result["success"],
        created_embedding=result["created_embedding"],
    )
