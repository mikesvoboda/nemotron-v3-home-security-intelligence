"""Repository for Event entity database operations.

This module provides the EventRepository class which extends the generic
Repository base class with event-specific query methods.

Example:
    async with get_session() as session:
        repo = EventRepository(session)
        unreviewed = await repo.get_unreviewed()
        high_risk = await repo.get_high_risk_events(threshold=70)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import desc, func, select
from sqlalchemy.orm import joinedload, selectinload

from backend.models import Event
from backend.repositories.base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


class EventRepository(Repository[Event]):
    """Repository for Event entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    event-specific query methods for filtering, searching, and updating events.

    Attributes:
        model_class: Set to Event for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = EventRepository(session)

            # Get unreviewed events
            unreviewed = await repo.get_unreviewed()

            # Get high-risk events
            high_risk = await repo.get_high_risk_events(threshold=70)

            # Mark event as reviewed
            await repo.mark_reviewed(event_id, notes="False alarm")
    """

    model_class = Event

    async def get_by_camera_id(self, camera_id: str) -> Sequence[Event]:
        """Get all events for a specific camera.

        Args:
            camera_id: The ID of the camera to filter by.

        Returns:
            A sequence of events from the specified camera.
        """
        stmt = select(Event).where(Event.camera_id == camera_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_batch_id(self, batch_id: str) -> Event | None:
        """Get an event by its batch processing ID.

        Args:
            batch_id: The batch ID assigned during event processing.

        Returns:
            The Event if found, None otherwise.
        """
        stmt = select(Event).where(Event.batch_id == batch_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_unreviewed(self) -> Sequence[Event]:
        """Get all events that haven't been reviewed yet.

        Returns:
            A sequence of events where reviewed=False.
        """
        stmt = select(Event).where(Event.reviewed == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_unreviewed_count(self) -> int:
        """Count the number of unreviewed events.

        Returns:
            The count of events where reviewed=False.

        Note:
            More efficient than len(get_unreviewed()) as it uses SQL COUNT.
        """
        stmt = select(func.count()).select_from(Event).where(Event.reviewed == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_risk_level(self, risk_level: str) -> Sequence[Event]:
        """Get events filtered by risk level.

        Args:
            risk_level: The risk level to filter by
                        (e.g., "low", "medium", "high", "critical").

        Returns:
            A sequence of events with the specified risk level.
        """
        stmt = select(Event).where(Event.risk_level == risk_level)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_high_risk_events(self, threshold: int = 70) -> Sequence[Event]:
        """Get events with risk score at or above a threshold.

        Args:
            threshold: The minimum risk score (inclusive). Default is 70.

        Returns:
            A sequence of events with risk_score >= threshold.
        """
        stmt = select(Event).where(Event.risk_score >= threshold)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_in_date_range(
        self, start: datetime, end: datetime, *, eager_load_camera: bool = False
    ) -> Sequence[Event]:
        """Get events within a date range.

        Args:
            start: The start of the date range (inclusive).
            end: The end of the date range (inclusive).
            eager_load_camera: If True, eager load the camera relationship
                to avoid lazy loading issues in async context.

        Returns:
            A sequence of events where started_at is within the range.
        """
        stmt = select(Event).where(Event.started_at >= start, Event.started_at <= end)
        if eager_load_camera:
            stmt = stmt.options(selectinload(Event.camera))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 10) -> Sequence[Event]:
        """Get the most recent events.

        Args:
            limit: Maximum number of events to return. Default is 10.

        Returns:
            A sequence of events ordered by started_at descending,
            limited to the specified count.
        """
        stmt = select(Event).order_by(desc(Event.started_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_reviewed(self, event_id: int, notes: str | None = None) -> Event | None:
        """Mark an event as reviewed with optional notes.

        Args:
            event_id: The ID of the event to mark as reviewed.
            notes: Optional notes to add to the event (e.g., review comments).

        Returns:
            The updated Event if found, None if the event doesn't exist.
        """
        event = await self.get_by_id(event_id)
        if event is None:
            return None

        event.reviewed = True
        if notes is not None:
            event.notes = notes

        await self.session.flush()
        await self.session.refresh(event)
        return event

    # =========================================================================
    # Eager Loading Methods (NEM-3758)
    # =========================================================================

    async def get_event_with_camera(self, event_id: int) -> Event | None:
        """Get a single event with camera relationship eagerly loaded.

        Uses joinedload to fetch camera data in a single query, preventing
        lazy loading issues in async context and N+1 queries.

        Args:
            event_id: ID of the event to fetch

        Returns:
            Event with camera pre-loaded, or None if not found

        Loading Strategy:
            - camera: joinedload (many-to-one, single JOIN)
        """
        stmt = select(Event).options(joinedload(Event.camera)).where(Event.id == event_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_events_with_relationships(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Event]:
        """List events with camera relationship eagerly loaded.

        Uses joinedload for the camera relationship to prevent N+1 queries
        when iterating over events and accessing their cameras.

        Args:
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            Sequence of Event objects with camera pre-loaded

        Loading Strategy:
            - camera: joinedload (many-to-one, single JOIN)
        """
        stmt = (
            select(Event)
            .options(joinedload(Event.camera))
            .order_by(desc(Event.started_at))
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent_events_with_camera(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> Sequence[Event]:
        """Get recent events with camera relationship eagerly loaded.

        Fetches events from the last N hours with camera data pre-loaded
        to avoid N+1 queries.

        Args:
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of events to return

        Returns:
            Sequence of Event objects with camera pre-loaded

        Loading Strategy:
            - camera: joinedload (many-to-one, single JOIN)
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        stmt = (
            select(Event)
            .options(joinedload(Event.camera))
            .where(Event.started_at >= cutoff)
            .order_by(desc(Event.started_at))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()
