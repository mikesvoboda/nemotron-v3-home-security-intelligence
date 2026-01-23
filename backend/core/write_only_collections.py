"""Write-only collection accessors for large relationships.

NEM-3349: Implements WriteOnlyMapped-like patterns for large collections
to prevent accidental loading of entire collections into memory.

This module provides helper functions that work with existing relationships
but provide safe write-only access patterns. This approach is backward-compatible
with existing code while offering performance optimization opportunities.

Why not use WriteOnlyMapped directly?
- Changing existing relationships to WriteOnlyMapped would break existing code
- WriteOnlyMapped requires SQLAlchemy 2.0+ with specific ORM configurations
- This approach provides incremental adoption path

Usage:
    from backend.core.write_only_collections import (
        add_detection_to_camera,
        add_detection_to_event,
        get_detection_count_for_event,
    )

    # Safe: doesn't load entire collection
    await add_detection_to_camera(session, camera_id, detection)

    # Safe: uses SQL COUNT
    count = await get_detection_count_for_event(session, event_id)

    # Unsafe (existing code - loads all detections):
    # event.detections  # This loads ALL detections into memory!
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from backend.models.detection import Detection
    from backend.models.event import Event

__all__ = [
    "add_detection_to_camera",
    "add_detection_to_event",
    "add_event_to_camera",
    "get_detection_count_for_camera",
    "get_detection_count_for_event",
    "get_event_count_for_camera",
    "get_recent_detections_for_camera",
    "get_recent_events_for_camera",
    "remove_detection_from_event",
]


async def add_detection_to_camera(
    session: AsyncSession,
    camera_id: str,
    detection: Detection,
) -> None:
    """Add a detection to a camera without loading the camera's detections collection.

    This is the safe way to add detections when a camera might have thousands
    of existing detections.

    Args:
        session: The async database session
        camera_id: The camera ID to add the detection to
        detection: The detection object (must already be associated with camera_id)
    """
    # Simply set the camera_id and add to session
    # No need to load the camera's detections collection
    detection.camera_id = camera_id
    session.add(detection)


async def add_event_to_camera(
    session: AsyncSession,
    camera_id: str,
    event: Event,
) -> None:
    """Add an event to a camera without loading the camera's events collection.

    Args:
        session: The async database session
        camera_id: The camera ID to add the event to
        event: The event object
    """
    event.camera_id = camera_id
    session.add(event)


async def add_detection_to_event(
    session: AsyncSession,
    event_id: int,
    detection_id: int,
) -> None:
    """Add a detection to an event via the junction table.

    This doesn't load either the event's detections or the detection's events.

    Args:
        session: The async database session
        event_id: The event ID
        detection_id: The detection ID
    """
    from backend.models.event_detection import EventDetection

    # Create junction table entry directly
    event_detection = EventDetection(event_id=event_id, detection_id=detection_id)
    session.add(event_detection)


async def remove_detection_from_event(
    session: AsyncSession,
    event_id: int,
    detection_id: int,
) -> bool:
    """Remove a detection from an event via the junction table.

    Args:
        session: The async database session
        event_id: The event ID
        detection_id: The detection ID

    Returns:
        True if the link was removed, False if it didn't exist
    """
    from backend.models.event_detection import EventDetection

    stmt = select(EventDetection).where(
        EventDetection.event_id == event_id,
        EventDetection.detection_id == detection_id,
    )
    result = await session.execute(stmt)
    event_detection = result.scalar_one_or_none()

    if event_detection:
        await session.delete(event_detection)
        return True
    return False


async def get_detection_count_for_camera(
    session: AsyncSession,
    camera_id: str,
) -> int:
    """Get the count of detections for a camera without loading them.

    Args:
        session: The async database session
        camera_id: The camera ID

    Returns:
        Count of detections for the camera
    """
    from backend.models.detection import Detection

    stmt = select(func.count()).select_from(Detection).where(Detection.camera_id == camera_id)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_detection_count_for_event(
    session: AsyncSession,
    event_id: int,
) -> int:
    """Get the count of detections for an event without loading them.

    Args:
        session: The async database session
        event_id: The event ID

    Returns:
        Count of detections linked to the event
    """
    from backend.models.event_detection import EventDetection

    stmt = (
        select(func.count()).select_from(EventDetection).where(EventDetection.event_id == event_id)
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_event_count_for_camera(
    session: AsyncSession,
    camera_id: str,
) -> int:
    """Get the count of events for a camera without loading them.

    Args:
        session: The async database session
        camera_id: The camera ID

    Returns:
        Count of events for the camera
    """
    from backend.models.event import Event

    stmt = select(func.count()).select_from(Event).where(Event.camera_id == camera_id)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_recent_detections_for_camera(
    session: AsyncSession,
    camera_id: str,
    limit: int = 10,
) -> list[Detection]:
    """Get recent detections for a camera with a limit.

    Use this instead of accessing camera.detections directly when you only
    need a few recent detections.

    Args:
        session: The async database session
        camera_id: The camera ID
        limit: Maximum number of detections to return

    Returns:
        List of recent detections (ordered by detected_at desc)
    """
    from backend.models.detection import Detection

    stmt = (
        select(Detection)
        .where(Detection.camera_id == camera_id)
        .order_by(Detection.detected_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_recent_events_for_camera(
    session: AsyncSession,
    camera_id: str,
    limit: int = 10,
) -> list[Event]:
    """Get recent events for a camera with a limit.

    Use this instead of accessing camera.events directly when you only
    need a few recent events.

    Args:
        session: The async database session
        camera_id: The camera ID
        limit: Maximum number of events to return

    Returns:
        List of recent events (ordered by started_at desc)
    """
    from backend.models.event import Event

    stmt = (
        select(Event)
        .where(Event.camera_id == camera_id)
        .order_by(Event.started_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
