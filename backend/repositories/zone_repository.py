"""Repository for Zone entity database operations.

This module provides the ZoneRepository class which extends the generic
Repository base class with zone-specific query methods.

Example:
    async with get_session() as session:
        repo = ZoneRepository(session)
        zones = await repo.get_by_camera_id("front_door")
        enabled_zones = await repo.get_enabled_zones("front_door")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.models import Zone, ZoneType
from backend.repositories.base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


class ZoneRepository(Repository[Zone]):
    """Repository for Zone entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    zone-specific query methods.

    Attributes:
        model_class: Set to Zone for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = ZoneRepository(session)

            # Get zone by ID
            zone = await repo.get_by_id("zone_id")

            # Get all zones for a camera
            zones = await repo.get_by_camera_id("front_door")

            # Get enabled zones only
            enabled = await repo.get_enabled_zones("front_door")
    """

    model_class = Zone

    async def get_by_camera_id(self, camera_id: str) -> Sequence[Zone]:
        """Get all zones for a specific camera.

        Args:
            camera_id: The camera ID to filter by.

        Returns:
            A sequence of zones associated with the camera, ordered by priority (descending).
        """
        stmt = (
            select(Zone)
            .where(Zone.camera_id == camera_id)
            .order_by(Zone.priority.desc(), Zone.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_name(self, camera_id: str, name: str) -> Zone | None:
        """Find a zone by camera ID and name.

        Args:
            camera_id: The camera ID to filter by.
            name: The zone name to search for.

        Returns:
            The Zone if found, None otherwise.

        Note:
            Zone names should be unique per camera.
        """
        stmt = select(Zone).where(Zone.camera_id == camera_id, Zone.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_enabled_zones(self, camera_id: str) -> Sequence[Zone]:
        """Get all enabled zones for a specific camera.

        Args:
            camera_id: The camera ID to filter by.

        Returns:
            A sequence of enabled zones for the camera, ordered by priority (descending).
        """
        stmt = (
            select(Zone)
            .where(Zone.camera_id == camera_id, Zone.enabled == True)  # noqa: E712
            .order_by(Zone.priority.desc(), Zone.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_type(self, zone_type: ZoneType | str) -> Sequence[Zone]:
        """Get all zones with a specific type.

        Args:
            zone_type: The zone type to filter by (e.g., ZoneType.ENTRY_POINT or "entry_point").

        Returns:
            A sequence of zones with the specified type.
        """
        type_value = zone_type.value if isinstance(zone_type, ZoneType) else zone_type
        stmt = (
            select(Zone)
            .where(Zone.zone_type == type_value)
            .order_by(Zone.camera_id, Zone.priority.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def set_enabled(self, zone_id: str, enabled: bool) -> Zone | None:
        """Enable or disable a zone.

        Args:
            zone_id: The ID of the zone to update.
            enabled: True to enable, False to disable.

        Returns:
            The updated Zone if found, None if the zone doesn't exist.
        """
        zone = await self.get_by_id(zone_id)
        if zone is None:
            return None

        zone.enabled = enabled
        await self.session.flush()
        await self.session.refresh(zone)
        return zone

    async def update_priority(self, zone_id: str, priority: int) -> Zone | None:
        """Update a zone's priority.

        Higher priority zones are checked first for detection containment.

        Args:
            zone_id: The ID of the zone to update.
            priority: The new priority value (must be >= 0).

        Returns:
            The updated Zone if found, None if the zone doesn't exist.
        """
        zone = await self.get_by_id(zone_id)
        if zone is None:
            return None

        zone.priority = priority
        await self.session.flush()
        await self.session.refresh(zone)
        return zone

    async def get_by_camera_and_type(
        self, camera_id: str, zone_type: ZoneType | str
    ) -> Sequence[Zone]:
        """Get all zones for a camera with a specific type.

        Args:
            camera_id: The camera ID to filter by.
            zone_type: The zone type to filter by.

        Returns:
            A sequence of zones matching both camera and type.
        """
        type_value = zone_type.value if isinstance(zone_type, ZoneType) else zone_type
        stmt = (
            select(Zone)
            .where(Zone.camera_id == camera_id, Zone.zone_type == type_value)
            .order_by(Zone.priority.desc(), Zone.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_camera(self, camera_id: str) -> int:
        """Count the total number of zones for a camera.

        Args:
            camera_id: The camera ID to count zones for.

        Returns:
            The number of zones associated with the camera.
        """
        stmt = select(Zone).where(Zone.camera_id == camera_id)
        result = await self.session.execute(stmt)
        zones = result.scalars().all()
        return len(zones)

    async def exists_by_name(self, camera_id: str, name: str) -> bool:
        """Check if a zone with the given name exists for a camera.

        Args:
            camera_id: The camera ID to check.
            name: The zone name to check.

        Returns:
            True if a zone with the name exists for the camera, False otherwise.
        """
        zone = await self.get_by_name(camera_id, name)
        return zone is not None

    async def delete_by_camera_id(self, camera_id: str) -> int:
        """Delete all zones for a specific camera.

        Args:
            camera_id: The camera ID to delete zones for.

        Returns:
            The number of zones deleted.
        """
        zones = await self.get_by_camera_id(camera_id)
        count = len(zones)
        for zone in zones:
            await self.delete(zone)
        return count
