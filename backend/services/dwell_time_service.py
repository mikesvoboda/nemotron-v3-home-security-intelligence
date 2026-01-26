"""Service for managing dwell time tracking and loitering detection.

This module provides the DwellTimeService class for tracking how long objects
stay within polygon zones. It supports:
- Recording zone entry and exit events
- Calculating dwell time for active and historical records
- Checking for loitering alerts based on configurable thresholds
- Querying dwell history for analytics

Example:
    async with get_session() as session:
        service = DwellTimeService(session)

        # Record entry into a zone
        record = await service.record_entry(
            zone_id=1,
            track_id=42,
            camera_id="front_door",
            object_class="person",
        )

        # Check for loitering (threshold in seconds)
        alerts = await service.check_loitering(
            zone_id=1,
            threshold_seconds=300,  # 5 minutes
        )
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from sqlalchemy import and_, select, update
from sqlalchemy.engine import CursorResult

from backend.api.schemas.dwell_time import (
    LoiteringAlert,
)
from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.dwell_time import DwellTimeRecord

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class DwellTimeService:
    """Service for managing dwell time tracking and loitering detection.

    This service provides operations for tracking object dwell time within
    polygon zones. It enables loitering detection by recording entry/exit
    times and calculating total presence duration.

    The service maintains dwell time records that can be queried for:
    - Active objects currently in a zone
    - Historical dwell time data for analytics
    - Loitering alerts when thresholds are exceeded

    Attributes:
        db: The async database session for operations.

    Example:
        async with get_session() as session:
            service = DwellTimeService(session)

            # Record entry
            record = await service.record_entry(
                zone_id=1,
                track_id=42,
                camera_id="front_door",
                object_class="person",
            )

            # Later, record exit
            await service.record_exit(zone_id=1, track_id=42)
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the dwell time service.

        Args:
            db: An async SQLAlchemy session for database operations.
        """
        self.db = db

    async def record_entry(
        self,
        zone_id: int,
        track_id: int,
        camera_id: str,
        object_class: str,
        entry_time: datetime | None = None,
    ) -> DwellTimeRecord:
        """Record an object entering a zone.

        Creates a new dwell time record for an object entering a polygon zone.
        If the object already has an active record (no exit time) for this zone,
        returns the existing record instead of creating a duplicate.

        Args:
            zone_id: The ID of the polygon zone being entered.
            track_id: The tracking ID of the object from the detection pipeline.
            camera_id: The ID of the camera where the detection occurred.
            object_class: The classification of the object (e.g., "person").
            entry_time: Optional entry time. If None, uses current UTC time.

        Returns:
            The created or existing DwellTimeRecord.

        Example:
            record = await service.record_entry(
                zone_id=1,
                track_id=42,
                camera_id="front_door",
                object_class="person",
            )
        """
        # Check for existing active record
        existing = await self.get_active_record(zone_id, track_id)
        if existing is not None:
            logger.debug(
                f"Object {track_id} already has active dwell record in zone {zone_id}",
                extra={
                    "zone_id": zone_id,
                    "track_id": track_id,
                    "record_id": existing.id,
                },
            )
            return existing

        # Create new record
        record = DwellTimeRecord(
            zone_id=zone_id,
            track_id=track_id,
            camera_id=camera_id,
            object_class=object_class,
            entry_time=entry_time or utc_now(),
            total_seconds=0.0,
            triggered_alert=False,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        logger.info(
            f"Recorded zone entry: track {track_id} entered zone {zone_id}",
            extra={
                "record_id": record.id,
                "zone_id": zone_id,
                "track_id": track_id,
                "camera_id": camera_id,
                "object_class": object_class,
            },
        )

        return record

    async def record_exit(
        self,
        zone_id: int,
        track_id: int,
        exit_time: datetime | None = None,
    ) -> DwellTimeRecord | None:
        """Record an object exiting a zone.

        Updates the active dwell time record for the object with the exit time
        and calculates the total dwell duration.

        Args:
            zone_id: The ID of the polygon zone being exited.
            track_id: The tracking ID of the object.
            exit_time: Optional exit time. If None, uses current UTC time.

        Returns:
            The updated DwellTimeRecord if found, None if no active record exists.

        Example:
            record = await service.record_exit(zone_id=1, track_id=42)
            if record:
                print(f"Object dwelled for {record.total_seconds:.1f} seconds")
        """
        record = await self.get_active_record(zone_id, track_id)
        if record is None:
            logger.warning(
                f"No active dwell record found for track {track_id} in zone {zone_id}",
                extra={
                    "zone_id": zone_id,
                    "track_id": track_id,
                },
            )
            return None

        # Calculate exit time and duration
        actual_exit_time = exit_time or utc_now()
        record.exit_time = actual_exit_time
        record.total_seconds = (actual_exit_time - record.entry_time).total_seconds()

        await self.db.flush()
        await self.db.refresh(record)

        logger.info(
            f"Recorded zone exit: track {track_id} exited zone {zone_id} "
            f"after {record.total_seconds:.1f}s",
            extra={
                "record_id": record.id,
                "zone_id": zone_id,
                "track_id": track_id,
                "total_seconds": record.total_seconds,
                "triggered_alert": record.triggered_alert,
            },
        )

        return record

    async def get_active_record(
        self,
        zone_id: int,
        track_id: int,
    ) -> DwellTimeRecord | None:
        """Get the active dwell record for an object in a zone.

        Args:
            zone_id: The zone ID.
            track_id: The object's tracking ID.

        Returns:
            The active DwellTimeRecord if found, None otherwise.
        """
        stmt = select(DwellTimeRecord).where(
            and_(
                DwellTimeRecord.zone_id == zone_id,
                DwellTimeRecord.track_id == track_id,
                DwellTimeRecord.exit_time.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_dwellers(
        self,
        zone_id: int,
    ) -> Sequence[DwellTimeRecord]:
        """Get all objects currently dwelling in a zone.

        Returns all dwell time records that have an entry time but no exit time,
        indicating the objects are still present in the zone.

        Args:
            zone_id: The ID of the zone to query.

        Returns:
            A sequence of active DwellTimeRecord instances.

        Example:
            dwellers = await service.get_active_dwellers(zone_id=1)
            print(f"{len(dwellers)} objects currently in zone")
        """
        stmt = (
            select(DwellTimeRecord)
            .where(
                and_(
                    DwellTimeRecord.zone_id == zone_id,
                    DwellTimeRecord.exit_time.is_(None),
                )
            )
            .order_by(DwellTimeRecord.entry_time)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_dwell_history(
        self,
        zone_id: int,
        start_time: datetime,
        end_time: datetime,
        include_active: bool = True,
    ) -> Sequence[DwellTimeRecord]:
        """Get historical dwell time records for a zone.

        Retrieves all dwell time records that overlap with the specified
        time window. This includes records that started before start_time
        but were still active during the window.

        Args:
            zone_id: The ID of the zone to query.
            start_time: The start of the time window.
            end_time: The end of the time window.
            include_active: Whether to include currently active records.

        Returns:
            A sequence of DwellTimeRecord instances ordered by entry time.

        Example:
            from datetime import datetime, timedelta
            end = datetime.now(UTC)
            start = end - timedelta(hours=1)
            history = await service.get_dwell_history(
                zone_id=1,
                start_time=start,
                end_time=end,
            )
        """
        # Build query conditions
        conditions = [
            DwellTimeRecord.zone_id == zone_id,
            DwellTimeRecord.entry_time <= end_time,
        ]

        # Records that exited during or after start_time, or are still active
        if include_active:
            conditions.append(
                (DwellTimeRecord.exit_time >= start_time) | (DwellTimeRecord.exit_time.is_(None))
            )
        else:
            conditions.append(DwellTimeRecord.exit_time >= start_time)
            conditions.append(DwellTimeRecord.exit_time.isnot(None))

        stmt = select(DwellTimeRecord).where(and_(*conditions)).order_by(DwellTimeRecord.entry_time)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def check_loitering(
        self,
        zone_id: int,
        threshold_seconds: float,
        current_time: datetime | None = None,
    ) -> list[LoiteringAlert]:
        """Check for loitering alerts in a zone.

        Identifies objects that have been dwelling in the zone longer than
        the specified threshold. For active dwellers, calculates the current
        dwell time; for completed records, uses the recorded total.

        Args:
            zone_id: The ID of the zone to check.
            threshold_seconds: The dwell time threshold in seconds.
            current_time: Time to use for calculating active dwell times.
                If None, uses current UTC time.

        Returns:
            A list of LoiteringAlert for objects exceeding the threshold.

        Example:
            alerts = await service.check_loitering(
                zone_id=1,
                threshold_seconds=300,  # 5 minutes
            )
            for alert in alerts:
                print(f"Alert: {alert.object_class} loitering for {alert.dwell_seconds}s")
        """
        now = current_time or utc_now()
        alerts: list[LoiteringAlert] = []

        # Get active dwellers
        active_records = await self.get_active_dwellers(zone_id)

        for record in active_records:
            dwell_seconds = record.calculate_dwell_time(now)
            if dwell_seconds >= threshold_seconds:
                alerts.append(
                    LoiteringAlert(
                        zone_id=zone_id,
                        track_id=record.track_id,
                        camera_id=record.camera_id,
                        object_class=record.object_class,
                        entry_time=record.entry_time,
                        dwell_seconds=dwell_seconds,
                        threshold_seconds=threshold_seconds,
                        record_id=record.id,
                    )
                )

                # Mark alert as triggered if not already
                if not record.triggered_alert:
                    record.triggered_alert = True
                    await self.db.flush()

                    logger.warning(
                        f"Loitering detected: track {record.track_id} in zone {zone_id} "
                        f"for {dwell_seconds:.1f}s (threshold: {threshold_seconds}s)",
                        extra={
                            "record_id": record.id,
                            "zone_id": zone_id,
                            "track_id": record.track_id,
                            "dwell_seconds": dwell_seconds,
                            "threshold_seconds": threshold_seconds,
                        },
                    )

        return alerts

    async def mark_alert_triggered(
        self,
        record_id: int,
    ) -> bool:
        """Mark a dwell time record as having triggered an alert.

        Args:
            record_id: The ID of the record to update.

        Returns:
            True if the record was updated, False if not found.
        """
        stmt = (
            update(DwellTimeRecord)
            .where(DwellTimeRecord.id == record_id)
            .values(triggered_alert=True)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        cursor_result = cast("CursorResult[tuple[()]]", result)
        return cursor_result.rowcount > 0

    async def cleanup_stale_records(
        self,
        zone_id: int,
        max_age_seconds: float,
        current_time: datetime | None = None,
    ) -> int:
        """Clean up stale active records that may have missed exit events.

        Records that have been active for longer than max_age_seconds are
        assumed to have missed their exit event and are closed with the
        current time.

        Args:
            zone_id: The zone to clean up.
            max_age_seconds: Maximum age for active records before cleanup.
            current_time: Time to use as exit time. If None, uses current UTC time.

        Returns:
            Number of records cleaned up.
        """
        now = current_time or utc_now()
        active_records = await self.get_active_dwellers(zone_id)
        cleaned = 0

        for record in active_records:
            dwell_time = record.calculate_dwell_time(now)
            if dwell_time >= max_age_seconds:
                record.exit_time = now
                record.total_seconds = dwell_time
                cleaned += 1
                logger.info(
                    f"Cleaned up stale dwell record {record.id} for track {record.track_id}",
                    extra={
                        "record_id": record.id,
                        "zone_id": zone_id,
                        "track_id": record.track_id,
                        "total_seconds": dwell_time,
                    },
                )

        if cleaned > 0:
            await self.db.flush()

        return cleaned

    async def get_record_by_id(self, record_id: int) -> DwellTimeRecord | None:
        """Get a dwell time record by ID.

        Args:
            record_id: The record ID.

        Returns:
            The DwellTimeRecord if found, None otherwise.
        """
        stmt = select(DwellTimeRecord).where(DwellTimeRecord.id == record_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_zone_statistics(
        self,
        zone_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Get dwell time statistics for a zone.

        Args:
            zone_id: The zone to query.
            start_time: Start of the time window.
            end_time: End of the time window.

        Returns:
            Dictionary with statistics including total_records, avg_dwell_seconds,
            max_dwell_seconds, alerts_triggered.
        """
        records = await self.get_dwell_history(
            zone_id=zone_id,
            start_time=start_time,
            end_time=end_time,
            include_active=False,
        )

        if not records:
            return {
                "total_records": 0,
                "avg_dwell_seconds": 0.0,
                "max_dwell_seconds": 0.0,
                "min_dwell_seconds": 0.0,
                "alerts_triggered": 0,
            }

        dwell_times = [r.total_seconds for r in records]
        alerts = sum(1 for r in records if r.triggered_alert)

        return {
            "total_records": len(records),
            "avg_dwell_seconds": sum(dwell_times) / len(dwell_times),
            "max_dwell_seconds": max(dwell_times),
            "min_dwell_seconds": min(dwell_times),
            "alerts_triggered": alerts,
        }


def get_dwell_time_service(db: AsyncSession) -> DwellTimeService:
    """Get a DwellTimeService instance for the given session.

    This creates a new DwellTimeService bound to the provided session.
    Each request/transaction should use its own session and service.

    Args:
        db: An async SQLAlchemy session for database operations.

    Returns:
        A DwellTimeService instance bound to the session.

    Example:
        async with get_session() as session:
            service = get_dwell_time_service(session)
            dwellers = await service.get_active_dwellers(zone_id=1)
    """
    return DwellTimeService(db)
