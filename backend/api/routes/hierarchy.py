"""API routes for household organizational hierarchy management.

This module provides CRUD endpoints for managing the household hierarchy:
- Household (top-level organization unit)
- Property (physical locations within a household)
- Area (logical zones within a property)
- Camera-Area linking (many-to-many relationship)

Implements:
- NEM-3131: Phase 6.1 - Create Household CRUD API endpoints.
- NEM-3132: Phase 6.2 - Create Property CRUD API endpoints.
- NEM-3133: Phase 6.3 - Create Area CRUD and Camera linking endpoints.

Household Endpoints:
- GET /api/v1/households - List all households
- POST /api/v1/households - Create household
- GET /api/v1/households/{id} - Get household by ID
- PATCH /api/v1/households/{id} - Update household
- DELETE /api/v1/households/{id} - Delete household
- GET /api/v1/households/{id}/properties - List properties for household
- POST /api/v1/households/{id}/properties - Create property under household

Property Endpoints:
- GET /api/v1/properties/{id} - Get property by ID
- PATCH /api/v1/properties/{id} - Update property
- DELETE /api/v1/properties/{id} - Delete property
- GET /api/v1/properties/{id}/areas - List areas for property
- POST /api/v1/properties/{id}/areas - Create area under property

Area Endpoints:
- GET /api/v1/areas/{id} - Get area by ID
- PATCH /api/v1/areas/{id} - Update area
- DELETE /api/v1/areas/{id} - Delete area
- GET /api/v1/areas/{id}/cameras - List cameras in area
- POST /api/v1/areas/{id}/cameras - Link camera to area
- DELETE /api/v1/areas/{id}/cameras/{camera_id} - Unlink camera from area
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.hierarchy import (
    AreaCameraResponse,
    AreaCamerasResponse,
    AreaCreate,
    AreaListResponse,
    AreaResponse,
    AreaUpdate,
    CameraLinkRequest,
    CameraLinkResponse,
    HouseholdCreate,
    HouseholdListResponse,
    HouseholdResponse,
    HouseholdUpdate,
    PropertyCreate,
    PropertyListResponse,
    PropertyResponse,
    PropertyUpdate,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.area import Area
from backend.models.camera import Camera
from backend.models.household_org import Household
from backend.models.property import Property

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/households", tags=["households"])


# =============================================================================
# Helper Functions
# =============================================================================


async def get_household_or_404(
    household_id: int,
    session: AsyncSession,
) -> Household:
    """Get a household by ID or raise 404 if not found.

    Args:
        household_id: The household ID to look up
        session: Database session

    Returns:
        Household object if found

    Raises:
        HTTPException: 404 if household not found
    """
    query = select(Household).where(Household.id == household_id)
    result = await session.execute(query)
    household = result.scalar_one_or_none()

    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household with id {household_id} not found",
        )

    return household


# =============================================================================
# Household CRUD Endpoints
# =============================================================================


@router.get("", response_model=HouseholdListResponse)
async def list_households(
    session: AsyncSession = Depends(get_db),
) -> HouseholdListResponse:
    """List all households.

    Returns all households in the system ordered by name.

    Args:
        session: Database session

    Returns:
        HouseholdListResponse with list of households and total count
    """
    # Get total count
    count_query = select(func.count(Household.id))
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # Get households
    query = select(Household).order_by(Household.name)
    result = await session.execute(query)
    households = list(result.scalars().all())

    return HouseholdListResponse(
        items=[HouseholdResponse.model_validate(h) for h in households],
        total=total,
    )


@router.post(
    "",
    response_model=HouseholdResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_household(
    household_data: HouseholdCreate,
    session: AsyncSession = Depends(get_db),
) -> Household:
    """Create a new household.

    Args:
        household_data: Household creation data
        session: Database session

    Returns:
        Created Household object

    Raises:
        HTTPException: 409 if household with same name already exists
    """
    # Check if household with same name already exists
    existing_query = select(Household).where(Household.name == household_data.name)
    existing_result = await session.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Household with name '{household_data.name}' already exists (id: {existing.id})",
        )

    # Create new household
    household = Household(name=household_data.name)

    session.add(household)
    await session.commit()
    await session.refresh(household)

    logger.info(
        f"Created household: {household.id} ({household.name})",
        extra={"household_id": household.id, "household_name": household.name},
    )

    return household


@router.get("/{household_id}", response_model=HouseholdResponse)
async def get_household(
    household_id: int,
    session: AsyncSession = Depends(get_db),
) -> Household:
    """Get a specific household by ID.

    Args:
        household_id: ID of the household to retrieve
        session: Database session

    Returns:
        Household object

    Raises:
        HTTPException: 404 if household not found
    """
    return await get_household_or_404(household_id, session)


@router.patch("/{household_id}", response_model=HouseholdResponse)
async def update_household(
    household_id: int,
    updates: HouseholdUpdate,
    session: AsyncSession = Depends(get_db),
) -> Household:
    """Update an existing household.

    Args:
        household_id: ID of the household to update
        updates: Household update data (all fields optional)
        session: Database session

    Returns:
        Updated Household object

    Raises:
        HTTPException: 404 if household not found
        HTTPException: 409 if new name conflicts with existing household
    """
    household = await get_household_or_404(household_id, session)

    # Get update data (only fields that were provided)
    update_data = updates.model_dump(exclude_unset=True)

    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != household.name:
        existing_query = select(Household).where(
            Household.name == update_data["name"],
            Household.id != household_id,
        )
        existing_result = await session.execute(existing_query)
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Household with name '{update_data['name']}' already exists (id: {existing.id})",
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(household, field, value)

    await session.commit()
    await session.refresh(household)

    logger.info(
        f"Updated household: {household.id} ({household.name})",
        extra={"household_id": household.id, "updates": list(update_data.keys())},
    )

    return household


@router.delete("/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_household(
    household_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a household.

    This will cascade delete all related properties, areas, and unlink
    associated members and vehicles.

    Args:
        household_id: ID of the household to delete
        session: Database session

    Raises:
        HTTPException: 404 if household not found
    """
    household = await get_household_or_404(household_id, session)

    await session.delete(household)
    await session.commit()

    logger.info(
        f"Deleted household: {household_id}",
        extra={"household_id": household_id},
    )


# =============================================================================
# Household -> Property Endpoints
# =============================================================================


@router.get("/{household_id}/properties", response_model=PropertyListResponse)
async def list_household_properties(
    household_id: int,
    session: AsyncSession = Depends(get_db),
) -> PropertyListResponse:
    """List all properties for a household.

    Args:
        household_id: ID of the household
        session: Database session

    Returns:
        PropertyListResponse with list of properties and total count

    Raises:
        HTTPException: 404 if household not found
    """
    # Verify household exists
    await get_household_or_404(household_id, session)

    # Get total count for this household
    count_query = select(func.count(Property.id)).where(Property.household_id == household_id)
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # Get properties
    query = select(Property).where(Property.household_id == household_id).order_by(Property.name)
    result = await session.execute(query)
    properties = list(result.scalars().all())

    return PropertyListResponse(
        items=[PropertyResponse.model_validate(p) for p in properties],
        total=total,
    )


@router.post(
    "/{household_id}/properties",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_property(
    household_id: int,
    property_data: PropertyCreate,
    session: AsyncSession = Depends(get_db),
) -> Property:
    """Create a new property under a household.

    Args:
        household_id: ID of the household that owns this property
        property_data: Property creation data
        session: Database session

    Returns:
        Created Property object

    Raises:
        HTTPException: 404 if household not found
        HTTPException: 409 if property with same name already exists for this household
    """
    # Verify household exists
    await get_household_or_404(household_id, session)

    # Check if property with same name already exists for this household
    existing_query = select(Property).where(
        Property.household_id == household_id,
        Property.name == property_data.name,
    )
    existing_result = await session.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Property with name '{property_data.name}' already exists for this household (id: {existing.id})",
        )

    # Create new property
    property_obj = Property(
        household_id=household_id,
        name=property_data.name,
        address=property_data.address,
        timezone=property_data.timezone,
    )

    session.add(property_obj)
    await session.commit()
    await session.refresh(property_obj)

    logger.info(
        f"Created property: {property_obj.id} ({property_obj.name}) for household {household_id}",
        extra={
            "property_id": property_obj.id,
            "property_name": property_obj.name,
            "household_id": household_id,
        },
    )

    return property_obj


# =============================================================================
# Property Router (separate prefix for property-centric endpoints)
# =============================================================================


property_router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


async def get_property_or_404(
    property_id: int,
    session: AsyncSession,
) -> Property:
    """Get a property by ID or raise 404 if not found.

    Args:
        property_id: The property ID to look up
        session: Database session

    Returns:
        Property object if found

    Raises:
        HTTPException: 404 if property not found
    """
    query = select(Property).where(Property.id == property_id)
    result = await session.execute(query)
    property_obj = result.scalar_one_or_none()

    if property_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with id {property_id} not found",
        )

    return property_obj


@property_router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    session: AsyncSession = Depends(get_db),
) -> Property:
    """Get a specific property by ID.

    Args:
        property_id: ID of the property to retrieve
        session: Database session

    Returns:
        Property object

    Raises:
        HTTPException: 404 if property not found
    """
    return await get_property_or_404(property_id, session)


@property_router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    updates: PropertyUpdate,
    session: AsyncSession = Depends(get_db),
) -> Property:
    """Update an existing property.

    Args:
        property_id: ID of the property to update
        updates: Property update data (all fields optional)
        session: Database session

    Returns:
        Updated Property object

    Raises:
        HTTPException: 404 if property not found
        HTTPException: 409 if new name conflicts with existing property in same household
    """
    property_obj = await get_property_or_404(property_id, session)

    # Get update data (only fields that were provided)
    update_data = updates.model_dump(exclude_unset=True)

    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != property_obj.name:
        existing_query = select(Property).where(
            Property.household_id == property_obj.household_id,
            Property.name == update_data["name"],
            Property.id != property_id,
        )
        existing_result = await session.execute(existing_query)
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Property with name '{update_data['name']}' already exists for this household (id: {existing.id})",
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(property_obj, field, value)

    await session.commit()
    await session.refresh(property_obj)

    logger.info(
        f"Updated property: {property_obj.id} ({property_obj.name})",
        extra={"property_id": property_obj.id, "updates": list(update_data.keys())},
    )

    return property_obj


@property_router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a property.

    This will cascade delete all related areas and unlink associated cameras.

    Args:
        property_id: ID of the property to delete
        session: Database session

    Raises:
        HTTPException: 404 if property not found
    """
    property_obj = await get_property_or_404(property_id, session)

    household_id = property_obj.household_id
    await session.delete(property_obj)
    await session.commit()

    logger.info(
        f"Deleted property: {property_id} from household {household_id}",
        extra={"property_id": property_id, "household_id": household_id},
    )


# =============================================================================
# Property -> Area Endpoints
# =============================================================================


@property_router.get("/{property_id}/areas", response_model=AreaListResponse)
async def list_property_areas(
    property_id: int,
    session: AsyncSession = Depends(get_db),
) -> AreaListResponse:
    """List all areas for a property.

    Args:
        property_id: ID of the property
        session: Database session

    Returns:
        AreaListResponse with list of areas and total count

    Raises:
        HTTPException: 404 if property not found
    """
    # Verify property exists
    await get_property_or_404(property_id, session)

    # Get total count for this property
    count_query = select(func.count(Area.id)).where(Area.property_id == property_id)
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # Get areas
    query = select(Area).where(Area.property_id == property_id).order_by(Area.name)
    result = await session.execute(query)
    areas = list(result.scalars().all())

    return AreaListResponse(
        items=[AreaResponse.model_validate(a) for a in areas],
        total=total,
    )


@property_router.post(
    "/{property_id}/areas",
    response_model=AreaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_area(
    property_id: int,
    area_data: AreaCreate,
    session: AsyncSession = Depends(get_db),
) -> Area:
    """Create a new area under a property.

    Args:
        property_id: ID of the property that owns this area
        area_data: Area creation data
        session: Database session

    Returns:
        Created Area object

    Raises:
        HTTPException: 404 if property not found
        HTTPException: 409 if area with same name already exists for this property
    """
    # Verify property exists
    await get_property_or_404(property_id, session)

    # Check if area with same name already exists for this property
    existing_query = select(Area).where(
        Area.property_id == property_id,
        Area.name == area_data.name,
    )
    existing_result = await session.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Area with name '{area_data.name}' already exists for this property (id: {existing.id})",
        )

    # Create new area
    area = Area(
        property_id=property_id,
        name=area_data.name,
        description=area_data.description,
        color=area_data.color,
    )

    session.add(area)
    await session.commit()
    await session.refresh(area)

    logger.info(
        f"Created area: {area.id} ({area.name}) for property {property_id}",
        extra={
            "area_id": area.id,
            "area_name": area.name,
            "property_id": property_id,
        },
    )

    return area


# =============================================================================
# Area Router (separate prefix for area-centric endpoints)
# NEM-3133: Phase 6.3 - Create Area CRUD and Camera linking endpoints
# =============================================================================


area_router = APIRouter(prefix="/api/v1/areas", tags=["areas"])


async def get_area_or_404(
    area_id: int,
    session: AsyncSession,
) -> Area:
    """Get an area by ID or raise 404 if not found.

    Args:
        area_id: The area ID to look up
        session: Database session

    Returns:
        Area object if found

    Raises:
        HTTPException: 404 if area not found
    """
    query = select(Area).where(Area.id == area_id)
    result = await session.execute(query)
    area = result.scalar_one_or_none()

    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with id {area_id} not found",
        )

    return area


async def get_camera_or_404(
    camera_id: str,
    session: AsyncSession,
) -> Camera:
    """Get a camera by ID or raise 404 if not found.

    Args:
        camera_id: The camera ID to look up
        session: Database session

    Returns:
        Camera object if found

    Raises:
        HTTPException: 404 if camera not found
    """
    query = select(Camera).where(Camera.id == camera_id, Camera.deleted_at.is_(None))
    result = await session.execute(query)
    camera = result.scalar_one_or_none()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    return camera


@area_router.get("/{area_id}", response_model=AreaResponse)
async def get_area(
    area_id: int,
    session: AsyncSession = Depends(get_db),
) -> Area:
    """Get a specific area by ID.

    Args:
        area_id: ID of the area to retrieve
        session: Database session

    Returns:
        Area object

    Raises:
        HTTPException: 404 if area not found
    """
    return await get_area_or_404(area_id, session)


@area_router.patch("/{area_id}", response_model=AreaResponse)
async def update_area(
    area_id: int,
    updates: AreaUpdate,
    session: AsyncSession = Depends(get_db),
) -> Area:
    """Update an existing area.

    Args:
        area_id: ID of the area to update
        updates: Area update data (all fields optional)
        session: Database session

    Returns:
        Updated Area object

    Raises:
        HTTPException: 404 if area not found
        HTTPException: 409 if new name conflicts with existing area in same property
    """
    area = await get_area_or_404(area_id, session)

    # Get update data (only fields that were provided)
    update_data = updates.model_dump(exclude_unset=True)

    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != area.name:
        existing_query = select(Area).where(
            Area.property_id == area.property_id,
            Area.name == update_data["name"],
            Area.id != area_id,
        )
        existing_result = await session.execute(existing_query)
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Area with name '{update_data['name']}' already exists for this property (id: {existing.id})",
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(area, field, value)

    await session.commit()
    await session.refresh(area)

    logger.info(
        f"Updated area: {area.id} ({area.name})",
        extra={"area_id": area.id, "updates": list(update_data.keys())},
    )

    return area


@area_router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(
    area_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete an area.

    This will unlink all cameras associated with this area (cameras themselves
    are not deleted, only the association).

    Args:
        area_id: ID of the area to delete
        session: Database session

    Raises:
        HTTPException: 404 if area not found
    """
    area = await get_area_or_404(area_id, session)

    property_id = area.property_id
    await session.delete(area)
    await session.commit()

    logger.info(
        f"Deleted area: {area_id} from property {property_id}",
        extra={"area_id": area_id, "property_id": property_id},
    )


# =============================================================================
# Area -> Camera Linking Endpoints
# =============================================================================


@area_router.get("/{area_id}/cameras", response_model=AreaCamerasResponse)
async def list_area_cameras(
    area_id: int,
    session: AsyncSession = Depends(get_db),
) -> AreaCamerasResponse:
    """List all cameras linked to an area.

    Args:
        area_id: ID of the area
        session: Database session

    Returns:
        AreaCamerasResponse with list of cameras and count

    Raises:
        HTTPException: 404 if area not found
    """
    from sqlalchemy.orm import selectinload

    # Load area with cameras eagerly
    query = select(Area).where(Area.id == area_id).options(selectinload(Area.cameras))
    result = await session.execute(query)
    area = result.scalar_one_or_none()

    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with id {area_id} not found",
        )

    # Filter out deleted cameras
    cameras = [c for c in area.cameras if c.deleted_at is None]

    return AreaCamerasResponse(
        area_id=area.id,
        area_name=area.name,
        cameras=[AreaCameraResponse(id=c.id, name=c.name, status=c.status) for c in cameras],
        count=len(cameras),
    )


@area_router.post(
    "/{area_id}/cameras",
    response_model=CameraLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_camera_to_area(
    area_id: int,
    link_request: CameraLinkRequest,
    session: AsyncSession = Depends(get_db),
) -> CameraLinkResponse:
    """Link a camera to an area.

    Creates a many-to-many relationship between the area and camera.
    A camera can be linked to multiple areas, and an area can have multiple cameras.

    Args:
        area_id: ID of the area
        link_request: Contains the camera_id to link
        session: Database session

    Returns:
        CameraLinkResponse confirming the link

    Raises:
        HTTPException: 404 if area or camera not found
        HTTPException: 409 if camera is already linked to this area
    """
    from sqlalchemy.orm import selectinload

    # Load area with cameras eagerly
    query = select(Area).where(Area.id == area_id).options(selectinload(Area.cameras))
    result = await session.execute(query)
    area = result.scalar_one_or_none()

    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with id {area_id} not found",
        )

    # Verify camera exists
    camera = await get_camera_or_404(link_request.camera_id, session)

    # Check if camera is already linked to this area
    if camera in area.cameras:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera '{link_request.camera_id}' is already linked to area {area_id}",
        )

    # Add camera to area
    area.cameras.append(camera)
    await session.commit()

    logger.info(
        f"Linked camera {link_request.camera_id} to area {area_id}",
        extra={"area_id": area_id, "camera_id": link_request.camera_id},
    )

    return CameraLinkResponse(
        area_id=area_id,
        camera_id=link_request.camera_id,
        linked=True,
    )


@area_router.delete(
    "/{area_id}/cameras/{camera_id}",
    response_model=CameraLinkResponse,
)
async def unlink_camera_from_area(
    area_id: int,
    camera_id: str,
    session: AsyncSession = Depends(get_db),
) -> CameraLinkResponse:
    """Unlink a camera from an area.

    Removes the many-to-many relationship between the area and camera.
    Neither the area nor the camera is deleted.

    Args:
        area_id: ID of the area
        camera_id: ID of the camera to unlink
        session: Database session

    Returns:
        CameraLinkResponse confirming the unlink

    Raises:
        HTTPException: 404 if area or camera not found
        HTTPException: 404 if camera is not linked to this area
    """
    from sqlalchemy.orm import selectinload

    # Load area with cameras eagerly
    query = select(Area).where(Area.id == area_id).options(selectinload(Area.cameras))
    result = await session.execute(query)
    area = result.scalar_one_or_none()

    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with id {area_id} not found",
        )

    # Verify camera exists (we still check to give a better error message)
    camera = await get_camera_or_404(camera_id, session)

    # Check if camera is linked to this area
    if camera not in area.cameras:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' is not linked to area {area_id}",
        )

    # Remove camera from area
    area.cameras.remove(camera)
    await session.commit()

    logger.info(
        f"Unlinked camera {camera_id} from area {area_id}",
        extra={"area_id": area_id, "camera_id": camera_id},
    )

    return CameraLinkResponse(
        area_id=area_id,
        camera_id=camera_id,
        linked=False,
    )
