"""Service for managing polygon zones for intrusion detection.

This module provides the PolygonZoneService class for CRUD operations on
polygon zones, which are used for region-based intrusion detection and
object counting within defined areas.

Polygon zones work with the supervision library's PolygonZone for real-time
detection of objects entering, exiting, or dwelling within defined areas.

Example:
    async with get_session() as session:
        service = PolygonZoneService(session)

        # Create a restricted zone
        zone = await service.create_zone(
            camera_id="front_door",
            data=PolygonZoneCreate(
                name="Pool Area",
                polygon=[[100, 200], [400, 200], [400, 500], [100, 500]],
                zone_type="restricted",
                alert_threshold=1,
            )
        )

        # Get all active zones for processing
        zones = await service.get_zones_by_camera("front_door", active_only=True)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.api.schemas.analytics_zone import PolygonZoneCreate, PolygonZoneUpdate
from backend.core.logging import get_logger
from backend.models.analytics_zone import PolygonZone

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class PolygonZoneService:
    """Service for managing polygon zones for intrusion detection.

    This service provides CRUD operations for polygon zones that define
    monitored areas on camera views. Zones can be configured to:
    - Monitor for any entry (alert_threshold=0)
    - Alert when occupancy exceeds a threshold
    - Target specific object classes (person, car, etc.)
    - Be enabled/disabled without deletion

    Attributes:
        db: The async database session for operations.

    Example:
        async with get_session() as session:
            service = PolygonZoneService(session)

            # Create a zone
            zone = await service.create_zone(
                camera_id="backyard",
                data=PolygonZoneCreate(
                    name="Pool Area",
                    polygon=[[100, 100], [400, 100], [400, 300], [100, 300]],
                    zone_type="restricted",
                )
            )

            # Update occupancy count
            await service.update_count(zone.id, count=2)
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the polygon zone service.

        Args:
            db: An async SQLAlchemy session for database operations.
        """
        self.db = db

    async def create_zone(self, camera_id: str, data: PolygonZoneCreate) -> PolygonZone:
        """Create a new polygon zone.

        Args:
            camera_id: The ID of the camera this zone belongs to.
            data: The polygon zone creation data including name, polygon
                coordinates, zone type, and other configuration.

        Returns:
            The newly created PolygonZone instance.

        Example:
            zone = await service.create_zone(
                camera_id="front_door",
                data=PolygonZoneCreate(
                    name="Entry Area",
                    polygon=[[0, 0], [100, 0], [100, 100], [0, 100]],
                    zone_type="entry",
                )
            )
        """
        # Convert zone_type enum to string if needed
        zone_type_value = (
            data.zone_type.value if hasattr(data.zone_type, "value") else str(data.zone_type)
        )

        zone = PolygonZone(
            camera_id=camera_id,
            name=data.name,
            polygon=data.polygon,
            zone_type=zone_type_value,
            alert_threshold=data.alert_threshold,
            target_classes=data.target_classes,
            is_active=data.is_active,
            color=data.color,
            current_count=0,
        )
        self.db.add(zone)
        await self.db.flush()
        await self.db.refresh(zone)

        logger.info(
            f"Created polygon zone {zone.id} '{zone.name}' for camera {camera_id}",
            extra={
                "zone_id": zone.id,
                "camera_id": camera_id,
                "zone_type": zone_type_value,
                "vertex_count": len(data.polygon),
            },
        )

        return zone

    async def get_zone(self, zone_id: int) -> PolygonZone | None:
        """Get a polygon zone by ID.

        Args:
            zone_id: The unique identifier of the zone.

        Returns:
            The PolygonZone if found, None otherwise.

        Example:
            zone = await service.get_zone(zone_id=1)
            if zone:
                print(f"Zone '{zone.name}' has {zone.current_count} objects")
        """
        stmt = select(PolygonZone).where(PolygonZone.id == zone_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_zones_by_camera(
        self, camera_id: str, active_only: bool = True
    ) -> Sequence[PolygonZone]:
        """Get all polygon zones for a camera.

        Args:
            camera_id: The ID of the camera to get zones for.
            active_only: If True, only return zones where is_active=True.
                Defaults to True.

        Returns:
            A sequence of PolygonZone instances ordered by creation time.

        Example:
            # Get all active zones for processing
            zones = await service.get_zones_by_camera("front_door")

            # Get all zones including disabled ones
            all_zones = await service.get_zones_by_camera(
                "front_door", active_only=False
            )
        """
        stmt = select(PolygonZone).where(PolygonZone.camera_id == camera_id)
        if active_only:
            stmt = stmt.where(PolygonZone.is_active == True)  # noqa: E712
        stmt = stmt.order_by(PolygonZone.created_at)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_zone(self, zone_id: int, data: PolygonZoneUpdate) -> PolygonZone | None:
        """Update an existing polygon zone.

        Only the fields present in the update data are modified.

        Args:
            zone_id: The ID of the zone to update.
            data: The update data containing optional fields to modify.

        Returns:
            The updated PolygonZone if found, None if the zone doesn't exist.

        Example:
            # Update zone name and threshold
            updated = await service.update_zone(
                zone_id=1,
                data=PolygonZoneUpdate(
                    name="Updated Name",
                    alert_threshold=3,
                )
            )
        """
        zone = await self.get_zone(zone_id)
        if zone is None:
            return None

        # Update only provided fields
        update_data = data.model_dump(exclude_unset=True)

        # Handle zone_type enum conversion
        if "zone_type" in update_data and update_data["zone_type"] is not None:
            zone_type = update_data["zone_type"]
            update_data["zone_type"] = (
                zone_type.value if hasattr(zone_type, "value") else str(zone_type)
            )

        for field, value in update_data.items():
            setattr(zone, field, value)

        await self.db.flush()
        await self.db.refresh(zone)

        logger.info(
            f"Updated polygon zone {zone_id}",
            extra={
                "zone_id": zone_id,
                "updated_fields": list(update_data.keys()),
            },
        )

        return zone

    async def delete_zone(self, zone_id: int) -> bool:
        """Delete a polygon zone.

        Args:
            zone_id: The ID of the zone to delete.

        Returns:
            True if the zone was deleted, False if not found.

        Example:
            deleted = await service.delete_zone(zone_id=1)
            if deleted:
                print("Zone deleted successfully")
        """
        zone = await self.get_zone(zone_id)
        if zone is None:
            return False

        camera_id = zone.camera_id
        zone_name = zone.name

        await self.db.delete(zone)
        await self.db.flush()

        logger.info(
            f"Deleted polygon zone {zone_id} '{zone_name}' from camera {camera_id}",
            extra={
                "zone_id": zone_id,
                "camera_id": camera_id,
            },
        )

        return True

    async def update_count(self, zone_id: int, count: int) -> None:
        """Update the current occupancy count for a zone.

        This is typically called by the detection pipeline when processing
        frames to update the real-time occupancy count.

        Args:
            zone_id: The ID of the zone to update.
            count: The current number of objects in the zone.

        Raises:
            ValueError: If count is negative.

        Example:
            # Update count after processing detections
            await service.update_count(zone_id=1, count=3)
        """
        if count < 0:
            raise ValueError(f"Count cannot be negative: {count}")

        zone = await self.get_zone(zone_id)
        if zone is None:
            logger.warning(f"Attempted to update count for non-existent zone {zone_id}")
            return

        zone.current_count = count
        await self.db.flush()

        logger.debug(
            f"Updated polygon zone {zone_id} count to {count}",
            extra={
                "zone_id": zone_id,
                "count": count,
            },
        )

    async def set_active(self, zone_id: int, is_active: bool) -> PolygonZone | None:
        """Enable or disable a polygon zone.

        Args:
            zone_id: The ID of the zone to update.
            is_active: True to enable, False to disable.

        Returns:
            The updated PolygonZone if found, None if not found.

        Example:
            # Disable a zone temporarily
            zone = await service.set_active(zone_id=1, is_active=False)
        """
        zone = await self.get_zone(zone_id)
        if zone is None:
            return None

        zone.is_active = is_active
        await self.db.flush()
        await self.db.refresh(zone)

        logger.info(
            f"Set polygon zone {zone_id} active={is_active}",
            extra={
                "zone_id": zone_id,
                "is_active": is_active,
            },
        )

        return zone

    async def get_zones_by_type(self, camera_id: str, zone_type: str) -> Sequence[PolygonZone]:
        """Get all zones of a specific type for a camera.

        Args:
            camera_id: The ID of the camera.
            zone_type: The zone type to filter by (e.g., "restricted", "monitored").

        Returns:
            A sequence of PolygonZone instances matching the type.

        Example:
            # Get all restricted zones
            restricted = await service.get_zones_by_type(
                camera_id="front_door",
                zone_type="restricted"
            )
        """
        stmt = (
            select(PolygonZone)
            .where(
                PolygonZone.camera_id == camera_id,
                PolygonZone.zone_type == zone_type,
            )
            .order_by(PolygonZone.created_at)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def reset_all_counts(self, camera_id: str) -> int:
        """Reset the current count to 0 for all zones of a camera.

        This is useful when restarting detection or clearing stale counts.

        Args:
            camera_id: The ID of the camera.

        Returns:
            The number of zones that were reset.

        Example:
            # Reset counts on camera restart
            count = await service.reset_all_counts("front_door")
            print(f"Reset {count} zone counts")
        """
        zones = await self.get_zones_by_camera(camera_id, active_only=False)
        for zone in zones:
            zone.current_count = 0

        await self.db.flush()

        logger.info(
            f"Reset counts for {len(zones)} polygon zones on camera {camera_id}",
            extra={
                "camera_id": camera_id,
                "zone_count": len(zones),
            },
        )

        return len(zones)


def get_polygon_zone_service(db: AsyncSession) -> PolygonZoneService:
    """Get a PolygonZoneService instance for the given session.

    This creates a new PolygonZoneService bound to the provided session.
    Each request/transaction should use its own session and service.

    Args:
        db: An async SQLAlchemy session for database operations.

    Returns:
        A PolygonZoneService instance bound to the session.

    Example:
        async with get_session() as session:
            service = get_polygon_zone_service(session)
            zones = await service.get_zones_by_camera("front_door")
    """
    return PolygonZoneService(db)
