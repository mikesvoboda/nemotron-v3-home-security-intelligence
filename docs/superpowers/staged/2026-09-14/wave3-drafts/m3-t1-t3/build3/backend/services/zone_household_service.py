"""Zone household service for managing zone-household linkage.

This service provides business logic for:
- Zone household configuration CRUD operations
- Trust level calculations based on zone ownership and access rules
- Schedule checking for time-based access control

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.schemas.zone_household import TrustLevelResult
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.zone_household_config import ZoneHouseholdConfig

logger = get_logger(__name__)


def check_schedule(cron_expression: str, at_time: datetime) -> bool:
    """Check if a time matches a cron expression.

    Supports standard 5-field cron syntax: minute hour day month weekday
    - minute: 0-59
    - hour: 0-23 (ranges like 9-17)
    - day: 1-31
    - month: 1-12
    - weekday: 0-6 (0=Sunday) or 1-7 (1=Monday in some systems)

    Supports:
    - * for any value
    - Single values (e.g., 5)
    - Ranges (e.g., 9-17)
    - Lists (e.g., 1,2,3)
    - Combinations (e.g., 1-5,7)

    Args:
        cron_expression: Cron expression string (5 fields)
        at_time: Time to check against

    Returns:
        True if the time matches the cron expression, False otherwise
    """
    try:
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            logger.warning(
                "Invalid cron expression format, expected 5 fields",
                extra={"cron_expression": cron_expression, "fields": len(parts)},
            )
            return False

        minute_spec, hour_spec, day_spec, month_spec, weekday_spec = parts

        # Extract time components
        current_minute = at_time.minute
        current_hour = at_time.hour
        current_day = at_time.day
        current_month = at_time.month
        current_weekday = at_time.weekday()  # Monday=0, Sunday=6
        # Convert Python weekday to cron weekday (Sunday=0, Monday=1, ..., Saturday=6)
        cron_weekday = (current_weekday + 1) % 7

        return (
            _match_cron_field(minute_spec, current_minute, 0, 59)
            and _match_cron_field(hour_spec, current_hour, 0, 23)
            and _match_cron_field(day_spec, current_day, 1, 31)
            and _match_cron_field(month_spec, current_month, 1, 12)
            and _match_cron_field(weekday_spec, cron_weekday, 0, 6)
        )
    except (ValueError, IndexError) as e:
        logger.warning(
            "Error parsing cron expression",
            extra={"cron_expression": cron_expression, "error": str(e)},
        )
        return False


def _match_cron_field(spec: str, value: int, min_val: int, max_val: int) -> bool:
    """Check if a value matches a cron field specification.

    Args:
        spec: Cron field specification (e.g., "*", "5", "1-5", "1,3,5")
        value: Current value to check
        min_val: Minimum valid value for this field (reserved for future validation)
        max_val: Maximum valid value for this field (reserved for future validation)

    Returns:
        True if value matches the specification
    """
    # Handle wildcard
    if spec == "*":
        return True

    # Handle list (e.g., "1,3,5") - delegates to recursive calls
    if "," in spec:
        return any(
            _match_cron_field(part.strip(), value, min_val, max_val) for part in spec.split(",")
        )

    # Handle range (e.g., "1-5" or "9-17")
    if "-" in spec:
        return _match_cron_range(spec, value)

    # Handle step (e.g., "*/5") - simplified support
    if spec.startswith("*/"):
        return _match_cron_step(spec, value)

    # Handle single value
    return _match_cron_single(spec, value)


def _match_cron_range(spec: str, value: int) -> bool:
    """Check if value falls within a cron range specification."""
    try:
        range_parts = spec.split("-")
        if len(range_parts) == 2:
            start = int(range_parts[0])
            end = int(range_parts[1])
            return start <= value <= end
    except ValueError:
        pass
    return False


def _match_cron_step(spec: str, value: int) -> bool:
    """Check if value matches a cron step specification."""
    try:
        step = int(spec[2:])
        return value % step == 0
    except ValueError:
        return False


def _match_cron_single(spec: str, value: int) -> bool:
    """Check if value matches a single cron value."""
    try:
        return value == int(spec)
    except ValueError:
        return False


class ZoneHouseholdService:
    """Service for zone-household linkage operations.

    Provides methods for:
    - Getting and managing zone household configurations
    - Checking trust levels for entities in zones
    - Evaluating time-based access schedules

    Usage:
        service = ZoneHouseholdService(session)
        config = await service.get_config(zone_id)
        trust = await service.get_trust_level(zone_id, entity_id, "member")
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: Async database session for queries
        """
        self._session = session

    async def get_config(self, zone_id: str) -> ZoneHouseholdConfig | None:
        """Get the household configuration for a zone.

        Args:
            zone_id: ID of the zone

        Returns:
            ZoneHouseholdConfig if found, None otherwise
        """
        from backend.models.zone_household_config import ZoneHouseholdConfig

        query = select(ZoneHouseholdConfig).where(ZoneHouseholdConfig.zone_id == zone_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def create_config(
        self,
        zone_id: str,
        *,
        owner_id: int | None = None,
        allowed_member_ids: list[int] | None = None,
        allowed_vehicle_ids: list[int] | None = None,
        access_schedules: list[dict] | None = None,
    ) -> ZoneHouseholdConfig:
        """Create a new household configuration for a zone.

        Args:
            zone_id: ID of the zone
            owner_id: Optional owner household member ID
            allowed_member_ids: List of allowed member IDs
            allowed_vehicle_ids: List of allowed vehicle IDs
            access_schedules: List of access schedule dictionaries

        Returns:
            Created ZoneHouseholdConfig
        """
        from backend.models.zone_household_config import ZoneHouseholdConfig

        config = ZoneHouseholdConfig(
            zone_id=zone_id,
            owner_id=owner_id,
            allowed_member_ids=allowed_member_ids or [],
            allowed_vehicle_ids=allowed_vehicle_ids or [],
            access_schedules=access_schedules or [],
        )

        self._session.add(config)
        await self._session.flush()
        await self._session.refresh(config)

        logger.info(
            "Created zone household config",
            extra={"zone_id": zone_id, "config_id": config.id},
        )

        return config

    async def update_config(
        self,
        config: ZoneHouseholdConfig,
        *,
        owner_id: int | None = ...,  # type: ignore[assignment]
        allowed_member_ids: list[int] | None = None,
        allowed_vehicle_ids: list[int] | None = None,
        access_schedules: list[dict] | None = None,
    ) -> ZoneHouseholdConfig:
        """Update an existing household configuration.

        Args:
            config: Existing configuration to update
            owner_id: New owner ID (pass explicitly to set, use ... to skip)
            allowed_member_ids: New allowed member IDs (None to skip update)
            allowed_vehicle_ids: New allowed vehicle IDs (None to skip update)
            access_schedules: New access schedules (None to skip update)

        Returns:
            Updated ZoneHouseholdConfig
        """
        if owner_id is not ...:
            config.owner_id = owner_id
        if allowed_member_ids is not None:
            config.allowed_member_ids = allowed_member_ids
        if allowed_vehicle_ids is not None:
            config.allowed_vehicle_ids = allowed_vehicle_ids
        if access_schedules is not None:
            config.access_schedules = access_schedules

        await self._session.flush()
        await self._session.refresh(config)

        logger.info(
            "Updated zone household config",
            extra={"zone_id": config.zone_id, "config_id": config.id},
        )

        return config

    async def delete_config(self, config: ZoneHouseholdConfig) -> None:
        """Delete a household configuration.

        Args:
            config: Configuration to delete
        """
        zone_id = config.zone_id
        config_id = config.id
        await self._session.delete(config)
        await self._session.flush()

        logger.info(
            "Deleted zone household config",
            extra={"zone_id": zone_id, "config_id": config_id},
        )

    async def get_trust_level(
        self,
        zone_id: str,
        entity_id: int,
        entity_type: Literal["member", "vehicle"],
        at_time: datetime | None = None,
    ) -> tuple[TrustLevelResult, str]:
        """Get the trust level for an entity in a zone.

        Evaluates the trust level based on:
        1. Zone ownership (full trust)
        2. Allowed members/vehicles list (partial trust)
        3. Time-based access schedules (monitor trust)
        4. No configuration (none)

        Args:
            zone_id: ID of the zone to check
            entity_id: ID of the entity (member or vehicle)
            entity_type: Type of entity ("member" or "vehicle")
            at_time: Time to check for schedule-based access (defaults to now)

        Returns:
            Tuple of (TrustLevelResult, reason_string)
        """
        from backend.core.time_utils import utc_now

        config = await self.get_config(zone_id)
        if config is None:
            return TrustLevelResult.NONE, "No household configuration for this zone"

        if at_time is None:
            at_time = utc_now()

        # Check ownership (full trust)
        if entity_type == "member" and config.owner_id == entity_id:
            return TrustLevelResult.FULL, "Entity is the zone owner"

        # Check allowed lists (partial trust)
        if entity_type == "member" and entity_id in config.allowed_member_ids:
            return TrustLevelResult.PARTIAL, "Entity is in allowed members list"
        if entity_type == "vehicle" and entity_id in config.allowed_vehicle_ids:
            return TrustLevelResult.PARTIAL, "Entity is in allowed vehicles list"

        # Check schedules (monitor trust) - only for members
        if entity_type == "member" and config.access_schedules:
            for schedule in config.access_schedules:
                member_ids = schedule.get("member_ids", [])
                cron_expr = schedule.get("cron_expression", "")
                if entity_id in member_ids and check_schedule(cron_expr, at_time):
                    description = schedule.get("description", "scheduled access")
                    return TrustLevelResult.MONITOR, f"Entity has {description}"

        return TrustLevelResult.NONE, "Entity has no trust configuration in this zone"

    async def get_zones_for_member(self, member_id: int) -> list[dict]:
        """Get all zones where a member has trust.

        Returns zones where the member is:
        - The owner (full trust)
        - In the allowed members list (partial trust)
        - In any access schedule (potential monitor trust)

        Args:
            member_id: ID of the household member

        Returns:
            List of dictionaries with zone_id, trust_level, and reason
        """
        from backend.models.zone_household_config import ZoneHouseholdConfig

        # Query all configs
        query = select(ZoneHouseholdConfig).options(selectinload(ZoneHouseholdConfig.zone))
        result = await self._session.execute(query)
        configs = result.scalars().all()

        zones: list[dict] = []
        for config in configs:
            # Check if member is owner
            if config.owner_id == member_id:
                zones.append(
                    {
                        "zone_id": config.zone_id,
                        "trust_level": TrustLevelResult.FULL.value,
                        "reason": "Zone owner",
                    }
                )
                continue

            # Check if member is in allowed list
            if member_id in config.allowed_member_ids:
                zones.append(
                    {
                        "zone_id": config.zone_id,
                        "trust_level": TrustLevelResult.PARTIAL.value,
                        "reason": "In allowed members list",
                    }
                )
                continue

            # Check if member is in any schedule
            for schedule in config.access_schedules:
                if member_id in schedule.get("member_ids", []):
                    description = schedule.get("description", "scheduled access")
                    zones.append(
                        {
                            "zone_id": config.zone_id,
                            "trust_level": TrustLevelResult.MONITOR.value,
                            "reason": f"Has {description}",
                        }
                    )
                    break

        return zones

    async def get_zones_for_vehicle(self, vehicle_id: int) -> list[dict]:
        """Get all zones where a vehicle has trust.

        Returns zones where the vehicle is in the allowed vehicles list.

        Args:
            vehicle_id: ID of the registered vehicle

        Returns:
            List of dictionaries with zone_id, trust_level, and reason
        """
        from backend.models.zone_household_config import ZoneHouseholdConfig

        # Query configs that contain this vehicle ID
        # Note: We can't efficiently filter by array containment in SQLAlchemy without
        # raw SQL, so we fetch all and filter in Python for now
        query = select(ZoneHouseholdConfig).options(selectinload(ZoneHouseholdConfig.zone))
        result = await self._session.execute(query)
        configs = result.scalars().all()

        zones: list[dict] = []
        for config in configs:
            if vehicle_id in config.allowed_vehicle_ids:
                zones.append(
                    {
                        "zone_id": config.zone_id,
                        "trust_level": TrustLevelResult.PARTIAL.value,
                        "reason": "In allowed vehicles list",
                    }
                )

        return zones


# =============================================================================
# Module-level convenience functions
# =============================================================================


def get_zone_household_service(session: AsyncSession) -> ZoneHouseholdService:
    """Factory function to create a ZoneHouseholdService instance.

    Args:
        session: Database session

    Returns:
        ZoneHouseholdService instance
    """
    return ZoneHouseholdService(session)
