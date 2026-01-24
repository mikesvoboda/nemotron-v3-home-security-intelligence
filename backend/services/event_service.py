"""Event service for managing events with cascade soft delete support.

This module provides the EventService class for managing event lifecycle,
including cascade soft delete that propagates to related detections and alerts.

The cascade soft delete uses the same timestamp for the parent event and its
related records, enabling identification of cascade-deleted records for restore.

File deletion is scheduled with a 5-minute delay to support undo operations.
When an event is restored, pending file deletions are cancelled.

Related Linear issues: NEM-1956, NEM-1988
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from backend.core.logging import get_logger
from backend.models.alert import Alert
from backend.models.event import Event
from backend.services.file_service import FileService, get_file_service

logger = get_logger(__name__)


class EventService:
    """Service for managing events with cascade soft delete support.

    This service provides methods for:
    - Soft deleting events with cascade to related detections and alerts
    - Restoring soft-deleted events with cascade to related records
    - Querying events with soft delete awareness
    - Scheduling file deletion when events are soft-deleted
    - Cancelling file deletion when events are restored

    The cascade soft delete uses the same timestamp for the parent event and
    its children, enabling identification of which records were deleted as
    part of the same cascade operation.
    """

    def __init__(self, file_service: FileService | None = None):
        """Initialize the event service.

        Args:
            file_service: Optional FileService instance. If not provided,
                will use the singleton instance.
        """
        self._file_service = file_service

    def _get_file_service(self) -> FileService:
        """Get the file service instance.

        Returns:
            FileService instance
        """
        if self._file_service:
            return self._file_service
        return get_file_service()

    def _collect_file_paths(self, event: Event) -> list[str]:
        """Collect all file paths associated with an event.

        This includes the event's clip path and all detection file paths
        and thumbnail paths.

        Args:
            event: Event with detections loaded

        Returns:
            List of file paths (may include empty strings or None, filtered later)
        """
        file_paths: list[str] = []

        # Add event clip path
        if event.clip_path:
            file_paths.append(event.clip_path)

        # Add detection file paths and thumbnails
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
        """Soft delete an event and optionally cascade to related records.

        When cascade=True, also schedules associated files for deletion
        after a 5-minute delay to support undo operations.

        Args:
            event_id: ID of the event to delete
            db: Database session
            cascade: If True, cascade soft delete to related detections and alerts,
                and schedule file deletion

        Returns:
            The soft-deleted event

        Raises:
            ValueError: If event not found or already deleted
        """
        # Fetch the event with related detections
        stmt = select(Event).options(selectinload(Event.detections)).where(Event.id == event_id)
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            raise ValueError(f"Event not found: {event_id}")

        if event.is_deleted:
            raise ValueError(f"Event already deleted: {event_id}")

        # Use a single timestamp for the cascade operation
        # This enables identifying which records were deleted together
        now = datetime.now(UTC)
        event.deleted_at = now

        if cascade:
            # Note: Detections do NOT have soft delete capability (no deleted_at column).
            # The cascade parameter is preserved for potential future use when related
            # entities gain soft delete support. Currently, only the event is soft deleted.
            detection_count = len(event.detections)
            if detection_count > 0:
                logger.info(
                    f"Event {event_id} has {detection_count} detections that remain unchanged "
                    "(detections do not support soft delete)"
                )

            # Count alerts for logging (alerts don't have soft delete, just count)
            alert_stmt = select(Alert).where(Alert.event_id == event_id)
            alert_result = await db.execute(alert_stmt)
            alert_count = len(list(alert_result.scalars().all()))

            if alert_count > 0:
                logger.info(
                    f"Event {event_id} has {alert_count} alerts that remain unchanged "
                    "(alerts do not support soft delete)"
                )

            # Schedule file deletion with delay (NEM-1988)
            file_paths = self._collect_file_paths(event)
            if file_paths:
                file_service = self._get_file_service()
                job_id = await file_service.schedule_deletion(
                    file_paths=file_paths,
                    event_id=event_id,
                )
                if job_id:
                    logger.info(
                        f"Scheduled {len(file_paths)} files for deletion "
                        f"(event_id={event_id}, job_id={job_id})"
                    )

        await db.flush()
        logger.info(
            f"Soft deleted event {event_id} with cascade={cascade}, timestamp={now.isoformat()}"
        )

        return event

    async def restore_event(
        self,
        event_id: int,
        db: AsyncSession,
        *,
        cascade: bool = True,
    ) -> Event:
        """Restore a soft-deleted event and optionally cascade to related records.

        When cascade=True, this method restores detections that were deleted
        at the same timestamp as the event (indicating they were cascade-deleted),
        and cancels any pending file deletions.

        Args:
            event_id: ID of the event to restore
            db: Database session
            cascade: If True, cascade restore to related records deleted at same time,
                and cancel pending file deletions

        Returns:
            The restored event

        Raises:
            ValueError: If event not found or not deleted
        """
        # Fetch the event with soft delete (need to bypass normal filtering)
        # Eagerly load deferred columns to prevent lazy loading errors
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

        # Store the deletion timestamp for cascade restore
        event_deleted_at = event.deleted_at

        # Restore the event
        event.deleted_at = None

        if cascade and event_deleted_at is not None:
            # Note: Detections do NOT have soft delete capability (no deleted_at column).
            # The cascade parameter is preserved for potential future use when related
            # entities gain soft delete support. Currently, only the event is restored.
            detection_count = len(event.detections)
            if detection_count > 0:
                logger.info(
                    f"Event {event_id} has {detection_count} detections (no cascade restore needed)"
                )

            # Cancel pending file deletions (NEM-1988)
            file_service = self._get_file_service()
            cancelled_count = await file_service.cancel_deletion_by_event_id(event_id)
            if cancelled_count > 0:
                logger.info(
                    f"Cancelled {cancelled_count} pending file deletion jobs for event {event_id}"
                )

        await db.flush()
        logger.info(f"Restored event {event_id} with cascade={cascade}")

        return event

    async def hard_delete_event(
        self,
        event_id: int,
        db: AsyncSession,
    ) -> tuple[int, int]:
        """Hard delete an event and immediately delete associated files.

        This method performs immediate file deletion (not scheduled) for hard
        delete scenarios where the event is being permanently removed from the
        database.

        Note: This method only handles file deletion. The caller is responsible
        for actually deleting the event from the database after this call.

        Args:
            event_id: ID of the event to delete
            db: Database session

        Returns:
            Tuple of (files_deleted, files_failed) indicating the result
            of file deletion operations.

        Raises:
            ValueError: If event not found
        """
        # Fetch the event with related detections
        stmt = select(Event).options(selectinload(Event.detections)).where(Event.id == event_id)
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            raise ValueError(f"Event not found: {event_id}")

        # Collect file paths
        file_paths = self._collect_file_paths(event)

        if not file_paths:
            logger.debug(f"No files to delete for event {event_id}")
            return 0, 0

        # Delete files immediately (not scheduled)
        file_service = self._get_file_service()
        files_deleted, files_failed = await file_service.delete_files_immediately(
            file_paths=file_paths
        )

        logger.info(
            f"Hard delete event {event_id}: deleted {files_deleted} files, {files_failed} failed"
        )

        return files_deleted, files_failed

    async def get_event(
        self,
        event_id: int,
        db: AsyncSession,
        *,
        include_deleted: bool = False,
    ) -> Event | None:
        """Get an event by ID with optional soft delete filtering.

        Args:
            event_id: ID of the event to fetch
            db: Database session
            include_deleted: If True, include soft-deleted events

        Returns:
            The event or None if not found
        """
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
        """Get a soft-deleted event by ID.

        This is a convenience method for fetching events that have been
        soft-deleted, useful for restore operations.

        Args:
            event_id: ID of the event to fetch
            db: Database session

        Returns:
            The deleted event or None if not found or not deleted
        """
        stmt = select(Event).where(Event.id == event_id).where(Event.deleted_at.is_not(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class _EventServiceSingleton:
    """Singleton holder for EventService instance.

    This class-based approach avoids using global statements,
    which are discouraged by PLW0603 linter rule.
    """

    _instance: EventService | None = None

    @classmethod
    def get_instance(cls) -> EventService:
        """Get the EventService singleton instance.

        Returns:
            The EventService instance
        """
        if cls._instance is None:
            cls._instance = EventService()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None


def get_event_service() -> EventService:
    """Get the EventService singleton instance.

    Returns:
        The EventService instance
    """
    return _EventServiceSingleton.get_instance()


def reset_event_service() -> None:
    """Reset the EventService singleton (for testing)."""
    _EventServiceSingleton.reset()
