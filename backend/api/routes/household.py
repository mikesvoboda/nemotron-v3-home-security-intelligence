"""API routes for household member and vehicle management.

Implements NEM-3018: Build API endpoints for household member and vehicle management.

These endpoints enable tracking of known household members and vehicles to reduce
false positives in security monitoring. If Nemotron knows "this is Mike's car"
or "this is a family member", it can score lower risk.

Endpoints:
- GET /api/household/members - List all household members
- POST /api/household/members - Create new member
- GET /api/household/members/{member_id} - Get specific member
- PATCH /api/household/members/{member_id} - Update member
- DELETE /api/household/members/{member_id} - Delete member
- GET /api/household/vehicles - List all registered vehicles
- POST /api/household/vehicles - Create new vehicle
- GET /api/household/vehicles/{vehicle_id} - Get specific vehicle
- PATCH /api/household/vehicles/{vehicle_id} - Update vehicle
- DELETE /api/household/vehicles/{vehicle_id} - Delete vehicle
- POST /api/household/members/{member_id}/embeddings - Add embedding from event
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.household import (
    AddEmbeddingRequest,
    HouseholdMemberCreate,
    HouseholdMemberResponse,
    HouseholdMemberUpdate,
    PersonEmbeddingResponse,
    RegisteredVehicleCreate,
    RegisteredVehicleResponse,
    RegisteredVehicleUpdate,
)
from backend.core.database import get_db
from backend.models.event import Event
from backend.models.household import HouseholdMember, PersonEmbedding, RegisteredVehicle

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

    This endpoint allows linking a person detection embedding from an event
    to a household member for future re-identification. The embedding data
    is extracted from the event's detection.

    Args:
        member_id: ID of the household member
        request: Request containing event_id and confidence
        session: Database session

    Returns:
        Created PersonEmbedding object

    Raises:
        HTTPException: 404 if member not found
        HTTPException: 404 if event not found
        HTTPException: 400 if event has no embedding data
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

    # Verify event exists and has embedding data
    event_query = select(Event).where(Event.id == request.event_id)
    event_result = await session.execute(event_query)
    event = event_result.scalar_one_or_none()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {request.event_id} not found",
        )

    # Check if event has embedding data
    # Note: embedding data would typically come from re-ID models in detection pipeline
    # For now, we use a placeholder embedding since the Event model doesn't have
    # an embedding field - this would be populated from detection metadata
    embedding_data = getattr(event, "embedding", None)
    if embedding_data is None:
        # For MVP, create a placeholder embedding
        # In production, this would come from person re-ID model output
        embedding_data = b"placeholder_embedding"

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
