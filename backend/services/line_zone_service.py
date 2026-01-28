"""Line zone service for virtual tripwire detection.

This module provides the LineZoneService class for managing line zones
that detect and count objects crossing from one side to the other.
Line zones are defined by start and end coordinates (in pixels).

Example:
    async with get_session() as session:
        service = LineZoneService(session)
        zone = await service.create_zone(
            camera_id="front_door",
            data=LineZoneCreate(
                name="Driveway Entrance",
                start_x=100, start_y=400,
                end_x=500, end_y=400,
                target_classes=["person", "car"]
            )
        )
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.analytics_zone import LineZoneCreate, LineZoneUpdate
from backend.core.logging import get_logger
from backend.models.analytics_zone import LineZone

logger = get_logger(__name__)


class LineZoneService:
    """Service for managing line zones (virtual tripwires).

    Line zones detect directional crossings across a defined line segment.
    Used for counting entries/exits and triggering alerts on boundary crossings.

    Attributes:
        db: The async database session for operations.

    Example:
        async with get_session() as session:
            service = LineZoneService(session)

            # Create a new line zone
            zone = await service.create_zone(
                camera_id="front_door",
                data=LineZoneCreate(
                    name="Entry Line",
                    start_x=100, start_y=200,
                    end_x=400, end_y=200,
                    target_classes=["person"]
                )
            )

            # Increment crossing count
            await service.increment_count(zone.id, direction="in")
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the line zone service.

        Args:
            db: An async SQLAlchemy session for database operations.
        """
        self.db = db

    async def create_zone(self, camera_id: str, data: LineZoneCreate) -> LineZone:
        """Create a new line zone for a camera.

        Args:
            camera_id: The ID of the camera this zone belongs to.
            data: The zone creation data containing coordinates and settings.

        Returns:
            The created LineZone object.

        Example:
            zone = await service.create_zone(
                camera_id="front_door",
                data=LineZoneCreate(
                    name="Entrance",
                    start_x=100, start_y=200,
                    end_x=400, end_y=200
                )
            )
        """
        zone = LineZone(
            camera_id=camera_id,
            name=data.name,
            start_x=data.start_x,
            start_y=data.start_y,
            end_x=data.end_x,
            end_y=data.end_y,
            alert_on_cross=data.alert_on_cross,
            target_classes=list(data.target_classes),
        )

        self.db.add(zone)
        await self.db.flush()
        await self.db.refresh(zone)

        logger.info(
            f"Created line zone '{zone.name}' for camera {camera_id}",
            extra={
                "zone_id": zone.id,
                "camera_id": camera_id,
                "zone_name": zone.name,
            },
        )

        return zone

    async def get_zone(self, zone_id: int) -> LineZone | None:
        """Get a line zone by ID.

        Args:
            zone_id: The unique identifier of the zone.

        Returns:
            The LineZone if found, None otherwise.
        """
        result = await self.db.execute(select(LineZone).where(LineZone.id == zone_id))
        return result.scalar_one_or_none()

    async def get_zones_by_camera(self, camera_id: str) -> list[LineZone]:
        """Get all line zones for a specific camera.

        Args:
            camera_id: The ID of the camera.

        Returns:
            List of LineZone objects for the camera, ordered by creation time.
        """
        result = await self.db.execute(
            select(LineZone).where(LineZone.camera_id == camera_id).order_by(LineZone.created_at)
        )
        return list(result.scalars().all())

    async def update_zone(self, zone_id: int, data: LineZoneUpdate) -> LineZone | None:
        """Update an existing line zone.

        Only fields present in the update data are modified.

        Args:
            zone_id: The ID of the zone to update.
            data: The update data with optional fields.

        Returns:
            The updated LineZone if found, None otherwise.

        Example:
            updated = await service.update_zone(
                zone_id=1,
                data=LineZoneUpdate(name="New Name", alert_on_cross=False)
            )
        """
        zone = await self.get_zone(zone_id)
        if zone is None:
            return None

        # Update only provided fields
        update_data = data.model_dump(exclude_unset=True)
        for field_name, value in update_data.items():
            if hasattr(zone, field_name):
                setattr(zone, field_name, value)

        await self.db.flush()
        await self.db.refresh(zone)

        logger.info(
            f"Updated line zone {zone_id}",
            extra={
                "zone_id": zone_id,
                "updated_fields": list(update_data.keys()),
            },
        )

        return zone

    async def delete_zone(self, zone_id: int) -> bool:
        """Delete a line zone.

        Args:
            zone_id: The ID of the zone to delete.

        Returns:
            True if the zone was deleted, False if not found.
        """
        zone = await self.get_zone(zone_id)
        if zone is None:
            return False

        await self.db.delete(zone)
        await self.db.flush()

        logger.info(
            f"Deleted line zone {zone_id}",
            extra={"zone_id": zone_id},
        )

        return True

    async def increment_count(self, zone_id: int, direction: str) -> None:
        """Increment the in or out crossing count for a zone.

        Args:
            zone_id: The ID of the zone.
            direction: The crossing direction, either "in" or "out".

        Raises:
            ValueError: If direction is not "in" or "out".

        Example:
            await service.increment_count(zone_id=1, direction="in")
        """
        if direction not in ("in", "out"):
            raise ValueError(f"Direction must be 'in' or 'out', got '{direction}'")

        zone = await self.get_zone(zone_id)
        if zone is None:
            logger.warning(f"Cannot increment count: zone {zone_id} not found")
            return

        if direction == "in":
            zone.in_count += 1
        else:
            zone.out_count += 1

        await self.db.flush()

        logger.debug(
            f"Incremented {direction}_count for zone {zone_id}",
            extra={
                "zone_id": zone_id,
                "direction": direction,
                "in_count": zone.in_count,
                "out_count": zone.out_count,
            },
        )

    async def reset_counts(self, zone_id: int) -> None:
        """Reset the in and out counts for a zone to zero.

        Args:
            zone_id: The ID of the zone.

        Example:
            await service.reset_counts(zone_id=1)
        """
        zone = await self.get_zone(zone_id)
        if zone is None:
            logger.warning(f"Cannot reset counts: zone {zone_id} not found")
            return

        zone.in_count = 0
        zone.out_count = 0

        await self.db.flush()

        logger.info(
            f"Reset counts for line zone {zone_id}",
            extra={"zone_id": zone_id},
        )

    async def get_all_zones(self) -> list[LineZone]:
        """Get all line zones across all cameras.

        Returns:
            List of all LineZone objects, ordered by camera ID and creation time.
        """
        result = await self.db.execute(
            select(LineZone).order_by(LineZone.camera_id, LineZone.created_at)
        )
        return list(result.scalars().all())


def get_line_zone_service(db: AsyncSession) -> LineZoneService:
    """Get a LineZoneService instance for the given session.

    This creates a new LineZoneService bound to the provided session.
    Each request/transaction should use its own session and service.

    Args:
        db: An async SQLAlchemy session for database operations.

    Returns:
        A LineZoneService instance bound to the session.

    Example:
        async with get_session() as session:
            service = get_line_zone_service(session)
            zones = await service.get_zones_by_camera("front_door")
    """
    return LineZoneService(db)
