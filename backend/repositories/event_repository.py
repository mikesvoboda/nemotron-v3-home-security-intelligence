"""Event-specific repository operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.models.event import Event
from backend.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event, int]):
    """Repository for Event-specific database operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the event repository.

        Args:
            db: The async database session
        """
        super().__init__(Event, db)

    async def get_by_id_with_camera(self, event_id: int) -> Event | None:
        """Get an event with its camera eagerly loaded.

        Args:
            event_id: The event ID

        Returns:
            The event with camera loaded, or None
        """
        stmt = select(Event).options(joinedload(Event.camera)).where(Event.id == event_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_camera_id(self, camera_id: str) -> list[Event]:
        """Find all events for a specific camera.

        Args:
            camera_id: The camera ID

        Returns:
            List of events for the camera
        """
        stmt = select(Event).where(Event.camera_id == camera_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_risk_level(self, risk_level: str) -> list[Event]:
        """Find all events with a specific risk level.

        Args:
            risk_level: The risk level (e.g., 'low', 'medium', 'high')

        Returns:
            List of events with matching risk level
        """
        stmt = select(Event).where(Event.risk_level == risk_level)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_unreviewed(self) -> list[Event]:
        """Find all unreviewed events.

        Returns:
            List of unreviewed events
        """
        stmt = select(Event).where(Event.reviewed == False)  # noqa: E712
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_batch_id(self, batch_id: str) -> list[Event]:
        """Find all events in a specific batch.

        Args:
            batch_id: The batch ID

        Returns:
            List of events in the batch
        """
        stmt = select(Event).where(Event.batch_id == batch_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_time_range(self, start_time: datetime, end_time: datetime) -> list[Event]:
        """Find events within a time range.

        Args:
            start_time: Start of the time range
            end_time: End of the time range

        Returns:
            List of events within the range
        """
        stmt = select(Event).where(Event.started_at >= start_time, Event.started_at <= end_time)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_high_risk(self, min_score: int = 70) -> list[Event]:
        """Find events with high risk scores.

        Args:
            min_score: Minimum risk score threshold

        Returns:
            List of high-risk events
        """
        stmt = select(Event).where(Event.risk_score >= min_score)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def mark_reviewed(self, event_id: int, notes: str | None = None) -> bool:
        """Mark an event as reviewed.

        Args:
            event_id: The event ID
            notes: Optional review notes

        Returns:
            True if updated, False if event not found
        """
        values: dict = {"reviewed": True}
        if notes is not None:
            values["notes"] = notes
        stmt = update(Event).where(Event.id == event_id).values(**values)
        result: CursorResult = await self.db.execute(stmt)  # type: ignore[assignment]
        await self.db.flush()
        return bool(result.rowcount and result.rowcount > 0)

    async def count_unreviewed(self) -> int:
        """Count unreviewed events.

        Returns:
            Number of unreviewed events
        """
        stmt = select(func.count()).select_from(Event).where(Event.reviewed == False)  # noqa: E712
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_by_camera(self, camera_id: str) -> int:
        """Count events for a specific camera.

        Args:
            camera_id: The camera ID

        Returns:
            Number of events for the camera
        """
        stmt = select(func.count()).select_from(Event).where(Event.camera_id == camera_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()
