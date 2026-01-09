"""Cascade soft delete service for maintaining data consistency.

This module provides utilities for cascading soft delete operations across
related records. When a parent record is soft-deleted, related child records
should also be soft-deleted to maintain data consistency.

Cascade relationships:
- Camera -> Events: When camera is soft-deleted, all events are soft-deleted
- Camera -> Detections: When camera is soft-deleted, all detections are soft-deleted
- Event -> Detections: When event is soft-deleted, related detections are soft-deleted

Example:
    from backend.services.cascade_delete import CascadeSoftDeleteService

    async with get_session() as session:
        service = CascadeSoftDeleteService(session)
        count = await service.soft_delete_camera("front_door", cascade=True)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from backend.core.logging import get_logger, sanitize_log_value
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import EventDetection

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass
class CascadeDeleteResult:
    """Result of a cascade soft delete operation.

    Attributes:
        parent_deleted: Whether the parent record was soft-deleted
        events_deleted: Number of events soft-deleted
        detections_deleted: Number of detections soft-deleted
        total_deleted: Total number of records soft-deleted (including parent)
    """

    parent_deleted: bool
    events_deleted: int = 0
    detections_deleted: int = 0

    @property
    def total_deleted(self) -> int:
        """Total number of records soft-deleted including parent."""
        return (1 if self.parent_deleted else 0) + self.events_deleted + self.detections_deleted


class CascadeSoftDeleteService:
    """Service for cascading soft delete operations.

    This service handles soft-deleting parent records along with their
    related child records to maintain data consistency.

    Attributes:
        session: SQLAlchemy async session for database operations
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the cascade soft delete service.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def soft_delete_camera(
        self,
        camera_id: str,
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Soft delete a camera and optionally cascade to related records.

        When cascade=True (default), this will:
        1. Soft delete all events associated with the camera
        2. Soft delete all detections associated with the camera
        3. Soft delete the camera itself

        Args:
            camera_id: ID of the camera to soft delete
            cascade: If True, also soft delete related events and detections

        Returns:
            CascadeDeleteResult with counts of deleted records

        Raises:
            ValueError: If camera not found
        """
        # Get the camera
        result = await self.session.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()

        if camera is None:
            raise ValueError(f"Camera with id {camera_id} not found")

        # Already soft-deleted
        if camera.is_deleted:
            logger.debug(
                "Camera already soft-deleted",
                extra={"camera_id": sanitize_log_value(camera_id)},
            )
            return CascadeDeleteResult(parent_deleted=False)

        now = datetime.now(UTC)
        events_deleted = 0
        detections_deleted = 0

        if cascade:
            # Soft delete all events for this camera
            events_result = await self.session.execute(
                update(Event)
                .where(Event.camera_id == camera_id)
                .where(Event.deleted_at.is_(None))
                .values(deleted_at=now)
            )
            events_deleted = events_result.rowcount or 0  # type: ignore[attr-defined]

            # Soft delete all detections for this camera
            detections_result = await self.session.execute(
                update(Detection)
                .where(Detection.camera_id == camera_id)
                .where(Detection.deleted_at.is_(None))
                .values(deleted_at=now)
            )
            detections_deleted = detections_result.rowcount or 0  # type: ignore[attr-defined]

            logger.info(
                "Cascade soft deleted camera children",
                extra={
                    "camera_id": sanitize_log_value(camera_id),
                    "events_deleted": events_deleted,
                    "detections_deleted": detections_deleted,
                },
            )

        # Soft delete the camera
        camera.deleted_at = now
        await self.session.flush()

        logger.info(
            "Soft deleted camera",
            extra={
                "camera_id": sanitize_log_value(camera_id),
                "cascade": cascade,
                "total_deleted": 1 + events_deleted + detections_deleted,
            },
        )

        return CascadeDeleteResult(
            parent_deleted=True,
            events_deleted=events_deleted,
            detections_deleted=detections_deleted,
        )

    async def soft_delete_event(
        self,
        event_id: int,
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Soft delete an event and optionally cascade to related detections.

        When cascade=True (default), this will:
        1. Soft delete all detections associated with the event via event_detections
        2. Soft delete the event itself

        Note: Detections may be shared across multiple events. When cascade=True,
        detections are only soft-deleted if they are not associated with any
        other non-deleted events.

        Args:
            event_id: ID of the event to soft delete
            cascade: If True, also soft delete related detections (only if not
                     associated with other non-deleted events)

        Returns:
            CascadeDeleteResult with counts of deleted records

        Raises:
            ValueError: If event not found
        """
        # Get the event
        result = await self.session.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()

        if event is None:
            raise ValueError(f"Event with id {event_id} not found")

        # Already soft-deleted
        if event.is_deleted:
            logger.debug(
                "Event already soft-deleted",
                extra={"event_id": event_id},
            )
            return CascadeDeleteResult(parent_deleted=False)

        now = datetime.now(UTC)
        detections_deleted = 0

        if cascade:
            # Get detection IDs associated with this event
            detection_ids_result = await self.session.execute(
                select(EventDetection.detection_id).where(EventDetection.event_id == event_id)
            )
            detection_ids = [row[0] for row in detection_ids_result.all()]

            if detection_ids:
                # Find detections that are ONLY associated with this event
                # (not shared with other non-deleted events)
                # Subquery: detection IDs that have other non-deleted events
                other_events_subquery = (
                    select(EventDetection.detection_id)
                    .join(Event, EventDetection.event_id == Event.id)
                    .where(EventDetection.event_id != event_id)
                    .where(Event.deleted_at.is_(None))
                    .distinct()
                )

                # Soft delete detections that are only associated with this event
                detections_result = await self.session.execute(
                    update(Detection)
                    .where(Detection.id.in_(detection_ids))
                    .where(Detection.deleted_at.is_(None))
                    .where(Detection.id.not_in(other_events_subquery))
                    .values(deleted_at=now)
                )
                detections_deleted = detections_result.rowcount or 0  # type: ignore[attr-defined]

                if detections_deleted > 0:
                    logger.info(
                        "Cascade soft deleted event detections",
                        extra={
                            "event_id": event_id,
                            "detections_deleted": detections_deleted,
                        },
                    )

        # Soft delete the event
        event.deleted_at = now
        await self.session.flush()

        logger.info(
            "Soft deleted event",
            extra={
                "event_id": event_id,
                "cascade": cascade,
                "detections_deleted": detections_deleted,
            },
        )

        return CascadeDeleteResult(
            parent_deleted=True,
            events_deleted=0,
            detections_deleted=detections_deleted,
        )

    async def soft_delete_events_bulk(
        self,
        event_ids: Sequence[int],
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Soft delete multiple events in a single operation.

        Args:
            event_ids: IDs of events to soft delete
            cascade: If True, also soft delete related detections

        Returns:
            CascadeDeleteResult with counts of deleted records
        """
        if not event_ids:
            return CascadeDeleteResult(parent_deleted=False)

        now = datetime.now(UTC)
        events_deleted = 0
        detections_deleted = 0

        if cascade:
            # Get detection IDs associated with these events
            detection_ids_result = await self.session.execute(
                select(EventDetection.detection_id)
                .where(EventDetection.event_id.in_(event_ids))
                .distinct()
            )
            detection_ids = [row[0] for row in detection_ids_result.all()]

            if detection_ids:
                # Find detections that are ONLY associated with events being deleted
                other_events_subquery = (
                    select(EventDetection.detection_id)
                    .join(Event, EventDetection.event_id == Event.id)
                    .where(EventDetection.event_id.not_in(event_ids))
                    .where(Event.deleted_at.is_(None))
                    .distinct()
                )

                # Soft delete detections not associated with other events
                detections_result = await self.session.execute(
                    update(Detection)
                    .where(Detection.id.in_(detection_ids))
                    .where(Detection.deleted_at.is_(None))
                    .where(Detection.id.not_in(other_events_subquery))
                    .values(deleted_at=now)
                )
                detections_deleted = detections_result.rowcount or 0  # type: ignore[attr-defined]

        # Soft delete the events
        events_result = await self.session.execute(
            update(Event)
            .where(Event.id.in_(event_ids))
            .where(Event.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        events_deleted = events_result.rowcount or 0  # type: ignore[attr-defined]

        await self.session.flush()

        logger.info(
            "Bulk soft deleted events",
            extra={
                "event_count": len(event_ids),
                "events_deleted": events_deleted,
                "detections_deleted": detections_deleted,
                "cascade": cascade,
            },
        )

        return CascadeDeleteResult(
            parent_deleted=events_deleted > 0,
            events_deleted=events_deleted,
            detections_deleted=detections_deleted,
        )

    async def restore_camera(
        self,
        camera_id: str,
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Restore a soft-deleted camera and optionally its related records.

        When cascade=True (default), this will:
        1. Restore the camera
        2. Restore all events that were soft-deleted at the same time (or after)
        3. Restore all detections that were soft-deleted at the same time (or after)

        Args:
            camera_id: ID of the camera to restore
            cascade: If True, also restore related events and detections

        Returns:
            CascadeDeleteResult with counts of restored records

        Raises:
            ValueError: If camera not found
        """
        # Get the camera
        result = await self.session.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()

        if camera is None:
            raise ValueError(f"Camera with id {camera_id} not found")

        # Not soft-deleted
        if not camera.is_deleted:
            logger.debug(
                "Camera not soft-deleted, nothing to restore",
                extra={"camera_id": sanitize_log_value(camera_id)},
            )
            return CascadeDeleteResult(parent_deleted=False)

        camera_deleted_at = camera.deleted_at
        events_restored = 0
        detections_restored = 0

        if cascade and camera_deleted_at:
            # Restore events soft-deleted at the same time (within 1 second tolerance)
            events_result = await self.session.execute(
                update(Event)
                .where(Event.camera_id == camera_id)
                .where(Event.deleted_at.isnot(None))
                .where(Event.deleted_at >= camera_deleted_at)
                .values(deleted_at=None)
            )
            events_restored = events_result.rowcount or 0  # type: ignore[attr-defined]

            # Restore detections soft-deleted at the same time
            detections_result = await self.session.execute(
                update(Detection)
                .where(Detection.camera_id == camera_id)
                .where(Detection.deleted_at.isnot(None))
                .where(Detection.deleted_at >= camera_deleted_at)
                .values(deleted_at=None)
            )
            detections_restored = detections_result.rowcount or 0  # type: ignore[attr-defined]

            logger.info(
                "Cascade restored camera children",
                extra={
                    "camera_id": sanitize_log_value(camera_id),
                    "events_restored": events_restored,
                    "detections_restored": detections_restored,
                },
            )

        # Restore the camera
        camera.deleted_at = None
        await self.session.flush()

        logger.info(
            "Restored camera",
            extra={
                "camera_id": sanitize_log_value(camera_id),
                "cascade": cascade,
                "total_restored": 1 + events_restored + detections_restored,
            },
        )

        return CascadeDeleteResult(
            parent_deleted=True,
            events_deleted=events_restored,  # Reusing field for restored count
            detections_deleted=detections_restored,
        )

    async def restore_event(
        self,
        event_id: int,
        *,
        cascade: bool = True,
    ) -> CascadeDeleteResult:
        """Restore a soft-deleted event and optionally its related detections.

        Args:
            event_id: ID of the event to restore
            cascade: If True, also restore related detections

        Returns:
            CascadeDeleteResult with counts of restored records

        Raises:
            ValueError: If event not found
        """
        # Get the event
        result = await self.session.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()

        if event is None:
            raise ValueError(f"Event with id {event_id} not found")

        # Not soft-deleted
        if not event.is_deleted:
            logger.debug(
                "Event not soft-deleted, nothing to restore",
                extra={"event_id": event_id},
            )
            return CascadeDeleteResult(parent_deleted=False)

        event_deleted_at = event.deleted_at
        detections_restored = 0

        if cascade and event_deleted_at:
            # Get detection IDs associated with this event
            detection_ids_result = await self.session.execute(
                select(EventDetection.detection_id).where(EventDetection.event_id == event_id)
            )
            detection_ids = [row[0] for row in detection_ids_result.all()]

            if detection_ids:
                # Restore detections soft-deleted at the same time
                detections_result = await self.session.execute(
                    update(Detection)
                    .where(Detection.id.in_(detection_ids))
                    .where(Detection.deleted_at.isnot(None))
                    .where(Detection.deleted_at >= event_deleted_at)
                    .values(deleted_at=None)
                )
                detections_restored = detections_result.rowcount or 0  # type: ignore[attr-defined]

        # Restore the event
        event.deleted_at = None
        await self.session.flush()

        logger.info(
            "Restored event",
            extra={
                "event_id": event_id,
                "cascade": cascade,
                "detections_restored": detections_restored,
            },
        )

        return CascadeDeleteResult(
            parent_deleted=True,
            events_deleted=0,
            detections_deleted=detections_restored,
        )


def get_cascade_soft_delete_service(session: AsyncSession) -> CascadeSoftDeleteService:
    """Factory function to create a CascadeSoftDeleteService.

    Args:
        session: SQLAlchemy async session

    Returns:
        CascadeSoftDeleteService instance
    """
    return CascadeSoftDeleteService(session)
