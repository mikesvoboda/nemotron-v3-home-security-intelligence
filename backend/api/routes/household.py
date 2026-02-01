"""API routes for household member and vehicle management.

Implements NEM-3018: Build API endpoints for household member and vehicle management.
Implements NEM-4688: Add household member link person endpoint.
Implements NEM-4688 Phase 1: Fix household embeddings endpoint to extract real embeddings.

These endpoints enable tracking of known household members and vehicles to reduce
false positives in security monitoring. If Nemotron knows "this is Mike's car"
or "this is a family member", it can score lower risk.

Endpoints:
- GET /api/household/members - List all household members
- POST /api/household/members - Create new member
- GET /api/household/members/{member_id} - Get specific member
- PATCH /api/household/members/{member_id} - Update member
- DELETE /api/household/members/{member_id} - Delete member
- PATCH /api/household/members/{member_id}/link-person - Link member to known person
- GET /api/household/vehicles - List all registered vehicles
- POST /api/household/vehicles - Create new vehicle
- GET /api/household/vehicles/{vehicle_id} - Get specific vehicle
- PATCH /api/household/vehicles/{vehicle_id} - Update vehicle
- DELETE /api/household/vehicles/{vehicle_id} - Delete vehicle
- POST /api/household/members/{member_id}/embeddings - Add embedding from event
"""

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.household import (
    AddEmbeddingRequest,
    HouseholdMemberCreate,
    HouseholdMemberResponse,
    HouseholdMemberUpdate,
    LinkPersonRequest,
    LinkPersonResponse,
    PersonEmbeddingResponse,
    RegisteredVehicleCreate,
    RegisteredVehicleResponse,
    RegisteredVehicleUpdate,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.event import Event
from backend.models.face_identity import KnownPerson
from backend.models.household import HouseholdMember, PersonEmbedding, RegisteredVehicle
from backend.services.reid_service import get_reid_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/household", tags=["household"])


# =============================================================================
# Household Member Endpoints
# =============================================================================


@router.get("/members", response_model=list[HouseholdMemberResponse])
async def list_members(
    session: AsyncSession = Depends(get_db),
) -> list[HouseholdMember]:
    """List all household members.

    Returns all registered household members ordered by name.

    Args:
        session: Database session

    Returns:
        List of HouseholdMember objects
    """
    query = select(HouseholdMember).order_by(HouseholdMember.name)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post(
    "/members",
    response_model=HouseholdMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_member(
    member: HouseholdMemberCreate,
    session: AsyncSession = Depends(get_db),
) -> HouseholdMember:
    """Create a new household member.

    Args:
        member: Member creation data
        session: Database session

    Returns:
        Created HouseholdMember object
    """
    db_member = HouseholdMember(
        name=member.name,
        role=member.role,
        trusted_level=member.trusted_level,
        typical_schedule=member.typical_schedule,
        notes=member.notes,
    )

    session.add(db_member)
    await session.commit()
    await session.refresh(db_member)

    return db_member


@router.get("/members/{member_id}", response_model=HouseholdMemberResponse)
async def get_member(
    member_id: int,
    session: AsyncSession = Depends(get_db),
) -> HouseholdMember:
    """Get a specific household member by ID.

    Args:
        member_id: ID of the member to retrieve
        session: Database session

    Returns:
        HouseholdMember object

    Raises:
        HTTPException: 404 if member not found
    """
    query = select(HouseholdMember).where(HouseholdMember.id == member_id)
    result = await session.execute(query)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household member with id {member_id} not found",
        )

    return member


@router.patch("/members/{member_id}", response_model=HouseholdMemberResponse)
async def update_member(
    member_id: int,
    updates: HouseholdMemberUpdate,
    session: AsyncSession = Depends(get_db),
) -> HouseholdMember:
    """Update an existing household member.

    Args:
        member_id: ID of the member to update
        updates: Member update data (all fields optional)
        session: Database session

    Returns:
        Updated HouseholdMember object

    Raises:
        HTTPException: 404 if member not found
    """
    query = select(HouseholdMember).where(HouseholdMember.id == member_id)
    result = await session.execute(query)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household member with id {member_id} not found",
        )

    # Update only provided fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(member, field, value)

    await session.commit()
    await session.refresh(member)

    return member


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a household member.

    This will also delete all associated person embeddings (cascade).

    Args:
        member_id: ID of the member to delete
        session: Database session

    Raises:
        HTTPException: 404 if member not found
    """
    query = select(HouseholdMember).where(HouseholdMember.id == member_id)
    result = await session.execute(query)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household member with id {member_id} not found",
        )

    await session.delete(member)
    await session.commit()


# =============================================================================
# Registered Vehicle Endpoints
# =============================================================================


@router.get("/vehicles", response_model=list[RegisteredVehicleResponse])
async def list_vehicles(
    session: AsyncSession = Depends(get_db),
) -> list[RegisteredVehicle]:
    """List all registered vehicles.

    Returns all registered vehicles ordered by description.

    Args:
        session: Database session

    Returns:
        List of RegisteredVehicle objects
    """
    query = select(RegisteredVehicle).order_by(RegisteredVehicle.description)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post(
    "/vehicles",
    response_model=RegisteredVehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle(
    vehicle: RegisteredVehicleCreate,
    session: AsyncSession = Depends(get_db),
) -> RegisteredVehicle:
    """Create a new registered vehicle.

    Args:
        vehicle: Vehicle creation data
        session: Database session

    Returns:
        Created RegisteredVehicle object

    Raises:
        HTTPException: 404 if owner_id is specified but owner doesn't exist
    """
    # Validate owner exists if specified
    if vehicle.owner_id is not None:
        owner_query = select(HouseholdMember).where(HouseholdMember.id == vehicle.owner_id)
        owner_result = await session.execute(owner_query)
        owner = owner_result.scalar_one_or_none()

        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Owner (household member) with id {vehicle.owner_id} not found",
            )

    db_vehicle = RegisteredVehicle(
        description=vehicle.description,
        license_plate=vehicle.license_plate,
        vehicle_type=vehicle.vehicle_type,
        color=vehicle.color,
        owner_id=vehicle.owner_id,
        trusted=vehicle.trusted,
    )

    session.add(db_vehicle)
    await session.commit()
    await session.refresh(db_vehicle)

    return db_vehicle


@router.get("/vehicles/{vehicle_id}", response_model=RegisteredVehicleResponse)
async def get_vehicle(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db),
) -> RegisteredVehicle:
    """Get a specific registered vehicle by ID.

    Args:
        vehicle_id: ID of the vehicle to retrieve
        session: Database session

    Returns:
        RegisteredVehicle object

    Raises:
        HTTPException: 404 if vehicle not found
    """
    query = select(RegisteredVehicle).where(RegisteredVehicle.id == vehicle_id)
    result = await session.execute(query)
    vehicle = result.scalar_one_or_none()

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registered vehicle with id {vehicle_id} not found",
        )

    return vehicle


@router.patch("/vehicles/{vehicle_id}", response_model=RegisteredVehicleResponse)
async def update_vehicle(
    vehicle_id: int,
    updates: RegisteredVehicleUpdate,
    session: AsyncSession = Depends(get_db),
) -> RegisteredVehicle:
    """Update an existing registered vehicle.

    Args:
        vehicle_id: ID of the vehicle to update
        updates: Vehicle update data (all fields optional)
        session: Database session

    Returns:
        Updated RegisteredVehicle object

    Raises:
        HTTPException: 404 if vehicle not found
        HTTPException: 404 if owner_id is specified but owner doesn't exist
    """
    query = select(RegisteredVehicle).where(RegisteredVehicle.id == vehicle_id)
    result = await session.execute(query)
    vehicle = result.scalar_one_or_none()

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registered vehicle with id {vehicle_id} not found",
        )

    # Validate owner exists if being updated
    update_data = updates.model_dump(exclude_unset=True)
    if "owner_id" in update_data and update_data["owner_id"] is not None:
        owner_query = select(HouseholdMember).where(HouseholdMember.id == update_data["owner_id"])
        owner_result = await session.execute(owner_query)
        owner = owner_result.scalar_one_or_none()

        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Owner (household member) with id {update_data['owner_id']} not found",
            )

    # Update fields
    for field, value in update_data.items():
        setattr(vehicle, field, value)

    await session.commit()
    await session.refresh(vehicle)

    return vehicle


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a registered vehicle.

    Args:
        vehicle_id: ID of the vehicle to delete
        session: Database session

    Raises:
        HTTPException: 404 if vehicle not found
    """
    query = select(RegisteredVehicle).where(RegisteredVehicle.id == vehicle_id)
    result = await session.execute(query)
    vehicle = result.scalar_one_or_none()

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registered vehicle with id {vehicle_id} not found",
        )

    await session.delete(vehicle)
    await session.commit()


# =============================================================================
# Link Person Endpoint
# =============================================================================


@router.patch("/members/{member_id}/link-person", response_model=LinkPersonResponse)
async def link_person(
    member_id: int,
    request: LinkPersonRequest,
    session: AsyncSession = Depends(get_db),
) -> LinkPersonResponse:
    """Link or unlink a household member to a known person.

    This endpoint allows linking a household member to a known person in the
    face recognition system, or unlinking by passing null for known_person_id.

    Args:
        member_id: ID of the household member
        request: Request containing known_person_id (or null to unlink)
        session: Database session

    Returns:
        LinkPersonResponse with success status

    Raises:
        HTTPException: 404 if household member not found
        HTTPException: 404 if known person not found (when linking)
    """
    # Verify member exists
    member_query = select(HouseholdMember).where(HouseholdMember.id == member_id)
    member_result = await session.execute(member_query)
    member = member_result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household member with id {member_id} not found",
        )

    # If linking to a known person (not null), verify the person exists
    if request.known_person_id is not None:
        person_query = select(KnownPerson).where(KnownPerson.id == request.known_person_id)
        person_result = await session.execute(person_query)
        known_person = person_result.scalar_one_or_none()

        if known_person is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Known person with id {request.known_person_id} not found",
            )

    # Update the link (or unlink if null)
    member.known_person_id = request.known_person_id
    await session.commit()

    return LinkPersonResponse(success=True)


# =============================================================================
# Person Embedding Endpoints
# =============================================================================


@router.post(
    "/members/{member_id}/embeddings",
    response_model=PersonEmbeddingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_embedding_from_event(
    member_id: int,
    request: AddEmbeddingRequest,
    session: AsyncSession = Depends(get_db),
) -> PersonEmbedding:
    """Add a person embedding from an event to a household member.

    This endpoint extracts a person embedding from the event's detection image
    using the ReIdentificationService (CLIP ViT-L) and stores it in the
    PersonEmbedding table for future person re-identification.

    The endpoint finds the first person detection in the event, loads the
    detection image, and generates a 768-dimensional CLIP embedding using
    the detection's bounding box to focus on the person.

    Args:
        member_id: ID of the household member
        request: Request containing event_id and confidence
        session: Database session

    Returns:
        Created PersonEmbedding object

    Raises:
        HTTPException: 404 if member not found
        HTTPException: 404 if event not found
        HTTPException: 400 if event has no person detection
        HTTPException: 400 if detection image cannot be loaded
        HTTPException: 500 if embedding generation fails
    """
    # Verify member exists
    member_query = select(HouseholdMember).where(HouseholdMember.id == member_id)
    member_result = await session.execute(member_query)
    member = member_result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household member with id {member_id} not found",
        )

    # Verify event exists and has detections
    event_query = select(Event).where(Event.id == request.event_id)
    event_result = await session.execute(event_query)
    event = event_result.scalar_one_or_none()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {request.event_id} not found",
        )

    # Find the first person detection in the event
    person_detection = None
    for detection in event.detections:
        if detection.object_type == "person":
            person_detection = detection
            break

    if person_detection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event does not contain a person detection. Cannot extract embedding.",
        )

    # Load the detection image
    try:
        with Image.open(person_detection.file_path) as image:
            # Create bounding box tuple if bbox coordinates are available
            bbox: tuple[int, int, int, int] | None = None
            if (
                person_detection.bbox_x is not None
                and person_detection.bbox_y is not None
                and person_detection.bbox_width is not None
                and person_detection.bbox_height is not None
            ):
                bbox = (
                    person_detection.bbox_x,
                    person_detection.bbox_y,
                    person_detection.bbox_x + person_detection.bbox_width,
                    person_detection.bbox_y + person_detection.bbox_height,
                )

            # Generate embedding using ReIdentificationService
            reid_service = get_reid_service()
            try:
                embedding_list = await reid_service.generate_embedding(image, bbox=bbox)
            except Exception as e:
                logger.error(
                    "Failed to generate embedding for event %d: %s",
                    request.event_id,
                    str(e),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate embedding: {e}",
                ) from e

            # Convert embedding list to serialized numpy array (bytes)
            embedding_array = np.array(embedding_list, dtype=np.float32)
            embedding_data = embedding_array.tobytes()

    except FileNotFoundError as e:
        logger.warning(
            "Detection image not found for event %d: %s",
            request.event_id,
            person_detection.file_path,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Detection image not found: {person_detection.file_path}",
        ) from e
    except OSError as e:
        logger.warning(
            "Failed to open detection image for event %d: %s",
            request.event_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open detection image: {e}",
        ) from e

    db_embedding = PersonEmbedding(
        member_id=member_id,
        embedding=embedding_data,
        source_event_id=request.event_id,
        confidence=request.confidence,
    )

    session.add(db_embedding)
    await session.commit()
    await session.refresh(db_embedding)

    return db_embedding
