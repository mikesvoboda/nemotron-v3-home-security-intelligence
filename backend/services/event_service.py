"""Event service for managing events with soft delete and restore support.

This module provides the EventService class for managing the soft-delete
lifecycle of events:
- Soft deleting events (moving them to Trash by setting `deleted_at`)
- Dismissing any alert whose covered events are all in Trash (`B4.4` / `4n-trash.md`)
- Restoring soft-deleted events from Trash (without reopening dismissed alerts)
- Querying events with soft-delete awareness

Permanent deletion (purge) of trashed events, their detections, files, and
derived rows lives in `backend/services/event_purger.py` (`EventPurger`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from backend.core.logging import get_logger
from backend.models.alert import Alert, AlertEvent, AlertStatusEnum
from backend.models.event import Event

logger = get_logger(__name__)


class EventService:
    """Service for managing events with soft delete and restore support."""

    def __init__(self) -> None:
        """Initialize the event service."""

    def _collect_file_paths(self, event: Event) -> list[str]:
        """Collect all file paths associated with an event.

        Args:
            event: Event with detections loaded

        Returns:
            List of file paths (clip, detection files, and thumbnails)
        """
        file_paths: list[str] = []

        if event.clip_path:
            file_paths.append(event.clip_path)

        for detection in event.detections:
            if detection.file_path:
                file_paths.append(detection.file_path)
            if detection.thumbnail_path:
                file_paths.append(detection.thumbnail_path)

        return file_paths

    async def soft_delete_event(
        self,
        event_id: int,
        db: AsyncSession,
        *,
        cascade: bool = True,
    ) -> Event:
        """Soft delete an event (move to Trash) and update affected alerts.

        Soft delete never schedules or deletes media files; files remain intact
        while the event is in Trash so it can be viewed or restored. When all
        events covered by an alert are in Trash, the alert is dismissed with
        reason `"events moved to Trash"`.

        Args:
            event_id: ID of the event to delete
            db: Database session
            cascade: If True, evaluate related alerts for all-trashed dismissal

        Returns:
            The soft-deleted event

        Raises:
            ValueError: If event not found or already deleted
        """
        stmt = select(Event).options(selectinload(Event.detections)).where(Event.id == event_id)
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            raise ValueError(f"Event not found: {event_id}")

        if event.is_deleted:
            raise ValueError(f"Event already deleted: {event_id}")

        now = datetime.now(UTC)
        event.deleted_at = now

        if cascade:
            detection_count = len(event.detections)
            if detection_count > 0:
                logger.info(
                    f"Event {event_id} has {detection_count} detections that remain unchanged "
                    "(detections do not support soft delete)"
                )

            await self._dismiss_alerts_if_all_events_trashed(db, event_id)

        await db.flush()
        logger.info(
            f"Soft deleted event {event_id} with cascade={cascade}, timestamp={now.isoformat()}"
        )

        return event

    async def _dismiss_alerts_if_all_events_trashed(
        self,
        db: AsyncSession,
        trashed_event_id: int,
    ) -> None:
        """Dismiss any alert covering `trashed_event_id` whose events are now all in Trash."""
        alert_stmt = (
            select(Alert)
            .options(selectinload(Alert.alert_events))
            .where(
                or_(
                    Alert.event_id == trashed_event_id,
                    Alert.last_event_id == trashed_event_id,
                    Alert.id.in_(
                        select(AlertEvent.alert_id).where(AlertEvent.event_id == trashed_event_id)
                    ),
                )
            )
        )
        alert_result = await db.execute(alert_stmt)
        alerts = list(alert_result.scalars().all())
        if not alerts:
            return

        for alert in alerts:
            covered_ids: set[int] = {
                ae.event_id for ae in (getattr(alert, "alert_events", None) or ())
            }
            ev_id = getattr(alert, "event_id", None)
            if isinstance(ev_id, int):
                covered_ids.add(ev_id)
            last_eid = getattr(alert, "last_event_id", None)
            if isinstance(last_eid, int):
                covered_ids.add(last_eid)

            other_ids = covered_ids - {trashed_event_id}
            if other_ids:
                live_res = await db.execute(
                    select(Event.id).where(
                        Event.id.in_(other_ids),
                        Event.deleted_at.is_(None),
                    )
                )
                if live_res.scalar_one_or_none() is not None:
                    continue

            alert.status = AlertStatusEnum.DISMISSED
            raw_meta = getattr(alert, "alert_metadata", None)
            meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
            meta["dismissed_reason"] = "events moved to Trash"
            alert.alert_metadata = meta

    async def restore_event(
        self,
        event_id: int,
        db: AsyncSession,
        *,
        cascade: bool = True,
    ) -> Event:
        """Restore a soft-deleted event from Trash.

        Restoring an event clears `deleted_at`; it does not reopen alerts that
        were dismissed when their events moved to Trash (`4n-trash.md`).

        Args:
            event_id: ID of the event to restore
            db: Database session
            cascade: Preserved for API compatibility

        Returns:
            The restored event

        Raises:
            ValueError: If event not found or not deleted
        """
        stmt = (
            select(Event)
            .options(
                selectinload(Event.detections),
                undefer(Event.reasoning),
                undefer(Event.llm_prompt),
            )
            .where(Event.id == event_id)
        )
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            raise ValueError(f"Event not found: {event_id}")

        if not event.is_deleted:
            raise ValueError(f"Event is not deleted: {event_id}")

        event.deleted_at = None

        if cascade and len(event.detections) > 0:
            logger.info(
                f"Event {event_id} has {len(event.detections)} detections (no cascade restore needed)"
            )

        await db.flush()
        logger.info(f"Restored event {event_id} with cascade={cascade}")

        return event

    async def get_event(
        self,
        event_id: int,
        db: AsyncSession,
        *,
        include_deleted: bool = False,
    ) -> Event | None:
        """Get an event by ID with optional soft delete filtering."""
        stmt = select(Event).where(Event.id == event_id)

        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_deleted_event(
        self,
        event_id: int,
        db: AsyncSession,
    ) -> Event | None:
        """Get a soft-deleted event by ID."""
        stmt = select(Event).where(Event.id == event_id).where(Event.deleted_at.is_not(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class _EventServiceSingleton:
    """Singleton holder for EventService instance."""

    _instance: EventService | None = None

    @classmethod
    def get_instance(cls) -> EventService:
        """Get the EventService singleton instance."""
        if cls._instance is None:
            cls._instance = EventService()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None


def get_event_service() -> EventService:
    """Get the EventService singleton instance."""
    return _EventServiceSingleton.get_instance()


def reset_event_service() -> None:
    """Reset the EventService singleton (for testing)."""
    _EventServiceSingleton.reset()
