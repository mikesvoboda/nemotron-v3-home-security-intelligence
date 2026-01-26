"""API routes for face recognition.

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition

Endpoints:
- GET /api/known-persons - List known persons
- POST /api/known-persons - Create known person
- GET /api/known-persons/{id} - Get person details
- PATCH /api/known-persons/{id} - Update person
- DELETE /api/known-persons/{id} - Delete person
- POST /api/known-persons/{id}/embeddings - Add face embedding
- GET /api/known-persons/{id}/embeddings - List embeddings for person
- DELETE /api/known-persons/{id}/embeddings/{embedding_id} - Delete embedding
- GET /api/face-events - List face detection events
- GET /api/face-events/unknown - Get unknown stranger alerts
- POST /api/face-events/match - Match a face against known persons
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.face_recognition import (
    FaceDetectionEventListResponse,
    FaceDetectionEventResponse,
    FaceEmbeddingCreate,
    FaceEmbeddingResponse,
    FaceMatchRequest,
    FaceMatchResponse,
    KnownPersonCreate,
    KnownPersonListResponse,
    KnownPersonResponse,
    KnownPersonUpdate,
    UnknownStrangerAlert,
    UnknownStrangerListResponse,
)
from backend.core.database import get_db
from backend.services.face_recognition_service import get_face_recognition_service

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
