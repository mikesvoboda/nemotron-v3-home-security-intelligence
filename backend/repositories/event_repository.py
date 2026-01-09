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

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc, func, select

from backend.models import Event
from backend.repositories.base import Repository
from backend.services.cascade_delete import CascadeDeleteResult, CascadeSoftDeleteService

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

    async def get_by_camera_id(
        self, camera_id: str, *, include_deleted: bool = False
    ) -> Sequence[Event]:
        """Get all events for a specific camera.

        By default, soft-deleted records are excluded. Use include_deleted=True
        to include soft-deleted events.

        Args:
            camera_id: The ID of the camera to filter by.
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            A sequence of events from the specified camera
            (excluding soft-deleted unless include_deleted=True).
        """
        stmt = select(Event).where(Event.camera_id == camera_id)
        # Filter out soft-deleted events unless explicitly requested
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_batch_id(
        self, batch_id: str, *, include_deleted: bool = False
    ) -> Event | None:
        """Get an event by its batch processing ID.

        By default, soft-deleted records are excluded. Use include_deleted=True
        to include soft-deleted events.

        Args:
            batch_id: The batch ID assigned during event processing.
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            The Event if found (and not soft-deleted unless include_deleted=True),
            None otherwise.
        """
        stmt = select(Event).where(Event.batch_id == batch_id)
        # Filter out soft-deleted events unless explicitly requested
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_unreviewed(self, *, include_deleted: bool = False) -> Sequence[Event]:
        """Get all events that haven't been reviewed yet.

        By default, soft-deleted records are excluded.

        Args:
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            A sequence of events where reviewed=False
            (excluding soft-deleted unless include_deleted=True).
        """
        stmt = select(Event).where(Event.reviewed == False)  # noqa: E712
        # Filter out soft-deleted events unless explicitly requested
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_unreviewed_count(self, *, include_deleted: bool = False) -> int:
        """Count the number of unreviewed events.

        By default, soft-deleted records are excluded.

        Args:
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            The count of events where reviewed=False
            (excluding soft-deleted unless include_deleted=True).

        Note:
            More efficient than len(get_unreviewed()) as it uses SQL COUNT.
        """
        # Build subquery with soft delete filter
        subquery = select(Event).where(Event.reviewed == False)  # noqa: E712
        if not include_deleted:
            subquery = subquery.where(Event.deleted_at.is_(None))
        stmt = select(func.count()).select_from(subquery.subquery())
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_risk_level(
        self, risk_level: str, *, include_deleted: bool = False
    ) -> Sequence[Event]:
        """Get events filtered by risk level.

        By default, soft-deleted records are excluded.

        Args:
            risk_level: The risk level to filter by
                        (e.g., "low", "medium", "high", "critical").
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            A sequence of events with the specified risk level
            (excluding soft-deleted unless include_deleted=True).
        """
        stmt = select(Event).where(Event.risk_level == risk_level)
        # Filter out soft-deleted events unless explicitly requested
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_high_risk_events(
        self, threshold: int = 70, *, include_deleted: bool = False
    ) -> Sequence[Event]:
        """Get events with risk score at or above a threshold.

        By default, soft-deleted records are excluded.

        Args:
            threshold: The minimum risk score (inclusive). Default is 70.
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            A sequence of events with risk_score >= threshold
            (excluding soft-deleted unless include_deleted=True).
        """
        stmt = select(Event).where(Event.risk_score >= threshold)
        # Filter out soft-deleted events unless explicitly requested
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_in_date_range(
        self, start: datetime, end: datetime, *, include_deleted: bool = False
    ) -> Sequence[Event]:
        """Get events within a date range.

        By default, soft-deleted records are excluded.

        Args:
            start: The start of the date range (inclusive).
            end: The end of the date range (inclusive).
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            A sequence of events where started_at is within the range
            (excluding soft-deleted unless include_deleted=True).
        """
        stmt = select(Event).where(Event.started_at >= start, Event.started_at <= end)
        # Filter out soft-deleted events unless explicitly requested
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(
        self, limit: int = 10, *, include_deleted: bool = False
    ) -> Sequence[Event]:
        """Get the most recent events.

        By default, soft-deleted records are excluded.

        Args:
            limit: Maximum number of events to return. Default is 10.
            include_deleted: If True, include soft-deleted events. Default False.

        Returns:
            A sequence of events ordered by started_at descending,
            limited to the specified count
            (excluding soft-deleted unless include_deleted=True).
        """
        stmt = select(Event)
        # Filter out soft-deleted events unless explicitly requested
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        stmt = stmt.order_by(desc(Event.started_at)).limit(limit)
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

    async def get_active(self) -> Sequence[Event]:
        """Get all non-deleted events.

        Note:
            This method is equivalent to calling get_all() since soft-deleted
            records are now excluded by default. Kept for backward compatibility.

        Returns:
            A sequence of events where deleted_at is None.
        """
        return await self.get_all()

    async def get_active_by_camera_id(self, camera_id: str) -> Sequence[Event]:
        """Get all non-deleted events for a specific camera.

        Note:
            This method is equivalent to calling get_by_camera_id() since soft-deleted
            records are now excluded by default. Kept for backward compatibility.

        Args:
            camera_id: The ID of the camera to filter by.

        Returns:
            A sequence of non-deleted events from the specified camera.
        """
        return await self.get_by_camera_id(camera_id)

    async def soft_delete(
        self,
        event_id: int,
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Soft delete an event and optionally cascade to related detections.

        When cascade=True (default), this will also soft delete detections
        that are only associated with this event.

        Args:
            event_id: The ID of the event to soft delete.
            cascade: If True, also soft delete related detections.

        Returns:
            CascadeDeleteResult with counts of deleted records.

        Raises:
            ValueError: If event not found.
        """
        service = CascadeSoftDeleteService(self.session)
        return await service.soft_delete_event(event_id, cascade=cascade)

    async def soft_delete_bulk(
        self,
        event_ids: Sequence[int],
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Soft delete multiple events in a single operation.

        Args:
            event_ids: IDs of events to soft delete.
            cascade: If True, also soft delete related detections.

        Returns:
            CascadeDeleteResult with counts of deleted records.
        """
        service = CascadeSoftDeleteService(self.session)
        return await service.soft_delete_events_bulk(event_ids, cascade=cascade)

    async def restore(
        self,
        event_id: int,
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Restore a soft-deleted event and optionally its related detections.

        Args:
            event_id: The ID of the event to restore.
            cascade: If True, also restore related detections.

        Returns:
            CascadeDeleteResult with counts of restored records.

        Raises:
            ValueError: If event not found.
        """
        service = CascadeSoftDeleteService(self.session)
        return await service.restore_event(event_id, cascade=cascade)
