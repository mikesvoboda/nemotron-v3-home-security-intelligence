"""Reusable dependencies and utility functions for FastAPI routes.

This module provides:

1. Entity existence checks - Utility functions that abstract the repeated pattern of
   querying for an entity by ID and raising a 404 if not found.

2. Service dependencies - FastAPI dependency injection functions for services,
   enabling proper DI patterns and easier testing through dependency overrides.

Usage (Entity Existence):
    from backend.api.dependencies import get_camera_or_404

    @router.get("/{camera_id}")
    async def get_camera(
        camera_id: str,
        db: AsyncSession = Depends(get_db),
    ) -> CameraResponse:
        camera = await get_camera_or_404(camera_id, db)
        return camera

Usage (Service DI):
    from backend.api.dependencies import get_cache_service_dep

    @router.get("/stats")
    async def get_stats(
        cache: CacheService = Depends(get_cache_service_dep),
        db: AsyncSession = Depends(get_db),
    ):
        cached = await cache.get("key")
        ...

These patterns simplify the common patterns and enable:
- Clean testability via FastAPI dependency_overrides
- Proper separation of concerns
- Consistent error handling
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.redis import RedisClient, get_redis
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.cache_service import CacheService


async def get_camera_or_404(
    camera_id: str,
    db: AsyncSession,
) -> Camera:
    """Get a camera by ID or raise 404 if not found.

    This utility function queries the database for a camera with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        camera_id: The camera ID to look up
        db: Database session

    Returns:
        Camera object if found

    Raises:
        HTTPException: 404 if camera not found
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found",
        )

    return camera


async def get_event_or_404(
    event_id: int,
    db: AsyncSession,
) -> Event:
    """Get an event by ID or raise 404 if not found.

    This utility function queries the database for an event with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        event_id: The event ID to look up
        db: Database session

    Returns:
        Event object if found

    Raises:
        HTTPException: 404 if event not found
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )

    return event


async def get_detection_or_404(
    detection_id: int,
    db: AsyncSession,
) -> Detection:
    """Get a detection by ID or raise 404 if not found.

    This utility function queries the database for a detection with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        detection_id: The detection ID to look up
        db: Database session

    Returns:
        Detection object if found

    Raises:
        HTTPException: 404 if detection not found
    """
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection with id {detection_id} not found",
        )

    return detection


# =============================================================================
# Service Dependency Injection Functions
# =============================================================================
#
# These functions implement proper FastAPI dependency injection for services.
# This pattern:
# 1. Enables clean testing via app.dependency_overrides
# 2. Allows FastAPI to manage service lifecycle
# 3. Provides consistent patterns across all routes
# =============================================================================


async def get_cache_service_dep(
    redis: RedisClient = Depends(get_redis),
) -> AsyncGenerator[CacheService]:
    """FastAPI dependency for CacheService.

    This dependency properly injects the CacheService with its Redis dependency,
    enabling clean testing through FastAPI's dependency_overrides mechanism.

    Args:
        redis: Redis client injected via Depends(get_redis)

    Yields:
        CacheService instance

    Example usage in routes::

        from backend.api.dependencies import get_cache_service_dep

        @router.get("/stats")
        async def get_stats(
            cache: CacheService = Depends(get_cache_service_dep),
        ):
            cached = await cache.get("key")
            ...

    Example usage in tests::

        app.dependency_overrides[get_cache_service_dep] = lambda: mock_cache
    """
    yield CacheService(redis)


async def get_cache_service_optional_dep(
    redis: RedisClient = Depends(get_redis),
) -> AsyncGenerator[CacheService | None]:
    """FastAPI dependency for optional CacheService.

    Like get_cache_service_dep but returns None if Redis is unavailable,
    allowing routes to gracefully degrade when cache is not available.

    Args:
        redis: Redis client injected via Depends(get_redis)

    Yields:
        CacheService instance or None if Redis unavailable
    """
    try:
        yield CacheService(redis)
    except Exception:
        yield None
