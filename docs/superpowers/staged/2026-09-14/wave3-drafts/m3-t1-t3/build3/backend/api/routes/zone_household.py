"""API routes for zone-household linkage management.

These endpoints enable configuring household member and vehicle access
for camera zones, supporting zone-based access control and trust management.

Endpoints:
- GET /api/zones/{zone_id}/household - Get household config for a zone
- PUT /api/zones/{zone_id}/household - Create/update household config
- DELETE /api/zones/{zone_id}/household - Remove household config
- GET /api/zones/{zone_id}/household/trust/{entity_type}/{entity_id} - Check trust level

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_zone_or_404
from backend.api.schemas.zone_household import (
    TrustCheckResponse,
    ZoneHouseholdConfigCreate,
    ZoneHouseholdConfigResponse,
    ZoneHouseholdConfigUpdate,
)
from backend.core.database import get_db
from backend.services.zone_household_service import ZoneHouseholdService

router = APIRouter(prefix="/api/zones", tags=["zone-household"])


@router.get("/{zone_id}/household", response_model=ZoneHouseholdConfigResponse | None)
async def get_zone_household_config(
    zone_id: str,
    db: AsyncSession = Depends(get_db),
) -> ZoneHouseholdConfigResponse | None:
    """Get the household configuration for a zone.

    Returns the household configuration if one exists, or null if the zone
    has no household linkage configured.

    Args:
        zone_id: ID of the zone
        db: Database session

    Returns:
        ZoneHouseholdConfigResponse if config exists, None otherwise

    Raises:
        HTTPException: 404 if zone not found
    """
    # Verify zone exists
    await get_zone_or_404(zone_id, db)

    service = ZoneHouseholdService(db)
    config = await service.get_config(zone_id)

    if config is None:
        return None

    return ZoneHouseholdConfigResponse.model_validate(config)


@router.put(
    "/{zone_id}/household",
    response_model=ZoneHouseholdConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_zone_household_config(
    zone_id: str,
    config_data: ZoneHouseholdConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> ZoneHouseholdConfigResponse:
    """Create or update the household configuration for a zone.

    If a configuration already exists for this zone, it will be updated.
    Otherwise, a new configuration will be created.

    Args:
        zone_id: ID of the zone
        config_data: Household configuration data
        db: Database session

    Returns:
        Created or updated ZoneHouseholdConfigResponse

    Raises:
        HTTPException: 404 if zone not found
        HTTPException: 404 if owner_id references non-existent member
    """
    from sqlalchemy import select

    from backend.models.household import HouseholdMember, RegisteredVehicle

    # Verify zone exists
    await get_zone_or_404(zone_id, db)

    # Validate owner exists if specified
    if config_data.owner_id is not None:
        owner_result = await db.execute(
            select(HouseholdMember).where(HouseholdMember.id == config_data.owner_id)
        )
        if owner_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household member with id {config_data.owner_id} not found",
            )

    # Validate allowed member IDs exist
    if config_data.allowed_member_ids:
        for member_id in config_data.allowed_member_ids:
            member_result = await db.execute(
                select(HouseholdMember).where(HouseholdMember.id == member_id)
            )
            if member_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Household member with id {member_id} not found",
                )

    # Validate allowed vehicle IDs exist
    if config_data.allowed_vehicle_ids:
        for vehicle_id in config_data.allowed_vehicle_ids:
            vehicle_result = await db.execute(
                select(RegisteredVehicle).where(RegisteredVehicle.id == vehicle_id)
            )
            if vehicle_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Registered vehicle with id {vehicle_id} not found",
                )

    service = ZoneHouseholdService(db)
    existing_config = await service.get_config(zone_id)

    # Convert access schedules to dict format
    access_schedules = [schedule.model_dump() for schedule in config_data.access_schedules]

    if existing_config is None:
        # Create new config
        config = await service.create_config(
            zone_id=zone_id,
            owner_id=config_data.owner_id,
            allowed_member_ids=config_data.allowed_member_ids,
            allowed_vehicle_ids=config_data.allowed_vehicle_ids,
            access_schedules=access_schedules,
        )
    else:
        # Update existing config
        config = await service.update_config(
            existing_config,
            owner_id=config_data.owner_id,
            allowed_member_ids=config_data.allowed_member_ids,
            allowed_vehicle_ids=config_data.allowed_vehicle_ids,
            access_schedules=access_schedules,
        )

    return ZoneHouseholdConfigResponse.model_validate(config)


async def _validate_household_references(db: AsyncSession, update_dict: dict) -> None:
    """Validate that referenced household members and vehicles exist.

    Args:
        db: Database session
        update_dict: Dictionary of fields being updated

    Raises:
        HTTPException: 404 if any referenced entity doesn't exist
    """
    from sqlalchemy import select

    from backend.models.household import HouseholdMember, RegisteredVehicle

    # Validate owner exists if being updated
    if "owner_id" in update_dict and update_dict["owner_id"] is not None:
        owner_result = await db.execute(
            select(HouseholdMember).where(HouseholdMember.id == update_dict["owner_id"])
        )
        if owner_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household member with id {update_dict['owner_id']} not found",
            )

    # Validate allowed member IDs if being updated
    if update_dict.get("allowed_member_ids"):
        for member_id in update_dict["allowed_member_ids"]:
            member_result = await db.execute(
                select(HouseholdMember).where(HouseholdMember.id == member_id)
            )
            if member_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Household member with id {member_id} not found",
                )

    # Validate allowed vehicle IDs if being updated
    if update_dict.get("allowed_vehicle_ids"):
        for vehicle_id in update_dict["allowed_vehicle_ids"]:
            vehicle_result = await db.execute(
                select(RegisteredVehicle).where(RegisteredVehicle.id == vehicle_id)
            )
            if vehicle_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Registered vehicle with id {vehicle_id} not found",
                )


@router.patch(
    "/{zone_id}/household",
    response_model=ZoneHouseholdConfigResponse,
)
async def patch_zone_household_config(
    zone_id: str,
    config_data: ZoneHouseholdConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> ZoneHouseholdConfigResponse:
    """Partially update the household configuration for a zone.

    Only updates the fields that are provided in the request body.
    Unlike PUT, this endpoint requires an existing configuration.

    Args:
        zone_id: ID of the zone
        config_data: Household configuration update data
        db: Database session

    Returns:
        Updated ZoneHouseholdConfigResponse

    Raises:
        HTTPException: 404 if zone not found
        HTTPException: 404 if config not found
        HTTPException: 404 if owner_id references non-existent member
    """
    # Verify zone exists
    await get_zone_or_404(zone_id, db)

    service = ZoneHouseholdService(db)
    config = await service.get_config(zone_id)

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No household configuration found for zone {zone_id}",
        )

    # Validate references
    update_dict = config_data.model_dump(exclude_unset=True)
    await _validate_household_references(db, update_dict)

    # Build update kwargs
    update_kwargs: dict = {}
    if "owner_id" in update_dict:
        update_kwargs["owner_id"] = update_dict["owner_id"]
    if "allowed_member_ids" in update_dict:
        update_kwargs["allowed_member_ids"] = update_dict["allowed_member_ids"]
    if "allowed_vehicle_ids" in update_dict:
        update_kwargs["allowed_vehicle_ids"] = update_dict["allowed_vehicle_ids"]
    if "access_schedules" in update_dict and update_dict["access_schedules"] is not None:
        update_kwargs["access_schedules"] = [
            schedule.model_dump()
            for schedule in config_data.access_schedules  # type: ignore[union-attr]
        ]

    config = await service.update_config(config, **update_kwargs)

    return ZoneHouseholdConfigResponse.model_validate(config)


@router.delete(
    "/{zone_id}/household",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_zone_household_config(
    zone_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete the household configuration for a zone.

    Removes all household linkage for this zone, including owner,
    allowed members, allowed vehicles, and access schedules.

    Args:
        zone_id: ID of the zone
        db: Database session

    Raises:
        HTTPException: 404 if zone not found
        HTTPException: 404 if config not found
    """
    # Verify zone exists
    await get_zone_or_404(zone_id, db)

    service = ZoneHouseholdService(db)
    config = await service.get_config(zone_id)

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No household configuration found for zone {zone_id}",
        )

    await service.delete_config(config)


@router.get(
    "/{zone_id}/household/trust/{entity_type}/{entity_id}",
    response_model=TrustCheckResponse,
)
async def check_entity_trust(
    zone_id: str,
    entity_type: Literal["member", "vehicle"],
    entity_id: int,
    at_time: datetime | None = Query(
        None,
        description="Time to check access for (ISO 8601 format, defaults to current time)",
    ),
    db: AsyncSession = Depends(get_db),
) -> TrustCheckResponse:
    """Check the trust level of an entity in a zone.

    Evaluates the trust level based on:
    1. Zone ownership (full trust)
    2. Allowed members/vehicles list (partial trust)
    3. Time-based access schedules (monitor trust)
    4. No configuration (none)

    Args:
        zone_id: ID of the zone
        entity_type: Type of entity ("member" or "vehicle")
        entity_id: ID of the entity to check
        at_time: Optional time for schedule checking (defaults to now)
        db: Database session

    Returns:
        TrustCheckResponse with trust level and reason

    Raises:
        HTTPException: 404 if zone not found
    """
    # Verify zone exists
    await get_zone_or_404(zone_id, db)

    service = ZoneHouseholdService(db)
    trust_level, reason = await service.get_trust_level(
        zone_id=zone_id,
        entity_id=entity_id,
        entity_type=entity_type,
        at_time=at_time,
    )

    return TrustCheckResponse(
        zone_id=zone_id,
        entity_id=entity_id,
        entity_type=entity_type,
        trust_level=trust_level,
        reason=reason,
    )


@router.get(
    "/member/{member_id}/zones",
    response_model=list[dict],
)
async def get_member_zones(
    member_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all zones where a household member has trust.

    Returns zones where the member is:
    - The owner (full trust)
    - In the allowed members list (partial trust)
    - In any access schedule (potential monitor trust)

    Args:
        member_id: ID of the household member
        db: Database session

    Returns:
        List of zones with trust information
    """
    service = ZoneHouseholdService(db)
    return await service.get_zones_for_member(member_id)


@router.get(
    "/vehicle/{vehicle_id}/zones",
    response_model=list[dict],
)
async def get_vehicle_zones(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all zones where a vehicle has trust.

    Returns zones where the vehicle is in the allowed vehicles list.

    Args:
        vehicle_id: ID of the registered vehicle
        db: Database session

    Returns:
        List of zones with trust information
    """
    service = ZoneHouseholdService(db)
    return await service.get_zones_for_vehicle(vehicle_id)
