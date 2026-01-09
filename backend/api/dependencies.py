"""Reusable dependencies and utility functions for FastAPI routes.

This module provides:

1. FastAPI Depends() functions - Dependency injection functions for services
   and resources that can be used with FastAPI's Depends() mechanism.

2. Entity existence checks - Utility functions that abstract the repeated pattern of
   querying for an entity by ID and raising a 404 if not found.

3. Generic factory for get_or_404 patterns - A factory function to create
   entity lookup functions with consistent 404 handling.

4. Service dependencies - FastAPI dependency injection functions for services,
   enabling proper DI patterns and easier testing through dependency overrides.

Usage (Orchestrator DI):
    from backend.api.dependencies import get_orchestrator

    @router.get("/services")
    async def list_services(
        orchestrator: ContainerOrchestrator = Depends(get_orchestrator),
    ):
        return orchestrator.get_all_services()

Usage (Entity Existence):
    from backend.api.dependencies import get_camera_or_404

    @router.get("/{camera_id}")
    async def get_camera(
        camera_id: str,
        db: AsyncSession = Depends(get_db),
    ) -> CameraResponse:
        camera = await get_camera_or_404(camera_id, db)
        return camera

Usage (Factory Pattern):
    from backend.api.dependencies import get_or_404_factory
    from backend.models import MyModel

    get_my_model_or_404 = get_or_404_factory(MyModel, "MyModel")

    @router.get("/{model_id}")
    async def get_model(model_id: str, db: AsyncSession = Depends(get_db)):
        return await get_my_model_or_404(model_id, db)

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

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import TYPE_CHECKING, Any, cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.redis import RedisClient, get_redis
from backend.models.alert import AlertRule
from backend.models.audit import AuditLog
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.models.prompt_version import PromptVersion
from backend.models.zone import Zone
from backend.services.cache_service import CacheService

if TYPE_CHECKING:
    from backend.services.container_orchestrator import ContainerOrchestrator


# =============================================================================
# FastAPI Depends() Functions
# =============================================================================
#
# These functions can be used with FastAPI's Depends() mechanism to inject
# common services and resources into route handlers.
# =============================================================================


async def get_orchestrator(request: Request) -> ContainerOrchestrator:
    """Get the container orchestrator from app state.

    This dependency retrieves the ContainerOrchestrator instance that was
    initialized during application startup and stored in app.state.

    Args:
        request: FastAPI Request object containing app state

    Returns:
        ContainerOrchestrator instance

    Raises:
        HTTPException: 503 Service Unavailable if orchestrator is not available
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Container orchestrator not available",
        )
    # Import at runtime to avoid circular imports

    return cast("ContainerOrchestrator", orchestrator)


# =============================================================================
# Entity Lookup Utilities
# =============================================================================
#
# These utility functions abstract the repeated pattern of querying for an
# entity by ID and raising a 404 if not found.
# =============================================================================


async def get_camera_or_404(
    camera_id: str,
    db: AsyncSession,
    include_deleted: bool = False,
) -> Camera:
    """Get a camera by ID or raise 404 if not found.

    This utility function queries the database for a camera with the given ID
    and raises an HTTPException with status 404 if not found.

    By default, soft-deleted cameras (with non-null deleted_at) are excluded.
    Use include_deleted=True to include them (e.g., for admin/trash views).

    Args:
        camera_id: The camera ID to look up
        db: Database session
        include_deleted: If True, include soft-deleted cameras (default: False)

    Returns:
        Camera object if found

    Raises:
        HTTPException: 404 if camera not found or soft-deleted (when include_deleted=False)
    """
    query = select(Camera).where(Camera.id == camera_id)

    # Filter out soft-deleted records unless explicitly requested
    if not include_deleted:
        query = query.where(Camera.deleted_at.is_(None))

    result = await db.execute(query)
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
    include_deleted: bool = False,
) -> Event:
    """Get an event by ID or raise 404 if not found.

    This utility function queries the database for an event with the given ID
    and raises an HTTPException with status 404 if not found.

    By default, soft-deleted events (with non-null deleted_at) are excluded.
    Use include_deleted=True to include them (e.g., for admin/trash views).

    Args:
        event_id: The event ID to look up
        db: Database session
        include_deleted: If True, include soft-deleted events (default: False)

    Returns:
        Event object if found

    Raises:
        HTTPException: 404 if event not found or soft-deleted (when include_deleted=False)
    """
    query = select(Event).where(Event.id == event_id)

    # Filter out soft-deleted records unless explicitly requested
    if not include_deleted:
        query = query.where(Event.deleted_at.is_(None))

    result = await db.execute(query)
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


async def get_alert_rule_or_404(
    rule_id: str,
    db: AsyncSession,
) -> AlertRule:
    """Get an alert rule by ID or raise 404 if not found.

    This utility function queries the database for an alert rule with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        rule_id: The alert rule ID (UUID string) to look up
        db: Database session

    Returns:
        AlertRule object if found

    Raises:
        HTTPException: 404 if alert rule not found
    """
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule with id {rule_id} not found",
        )

    return rule


async def get_zone_or_404(
    zone_id: str,
    db: AsyncSession,
    camera_id: str | None = None,
) -> Zone:
    """Get a zone by ID or raise 404 if not found.

    This utility function queries the database for a zone with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        zone_id: The zone ID to look up
        db: Database session
        camera_id: Optional camera ID to filter by (if provided, zone must belong to this camera)

    Returns:
        Zone object if found

    Raises:
        HTTPException: 404 if zone not found or doesn't belong to specified camera
    """
    query = select(Zone).where(Zone.id == zone_id)

    if camera_id is not None:
        query = query.where(Zone.camera_id == camera_id)

    result = await db.execute(query)
    zone = result.scalar_one_or_none()

    if not zone:
        if camera_id is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Zone with id {zone_id} not found for camera {camera_id}",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone with id {zone_id} not found",
        )

    return zone


async def get_prompt_version_or_404(
    version_id: int,
    db: AsyncSession,
) -> PromptVersion:
    """Get a prompt version by ID or raise 404 if not found.

    This utility function queries the database for a prompt version with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        version_id: The prompt version ID to look up
        db: Database session

    Returns:
        PromptVersion object if found

    Raises:
        HTTPException: 404 if prompt version not found
    """
    result = await db.execute(select(PromptVersion).where(PromptVersion.id == version_id))
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt version with id {version_id} not found",
        )

    return version


async def get_event_audit_or_404(
    event_id: int,
    db: AsyncSession,
) -> EventAudit:
    """Get an event audit by event ID or raise 404 if not found.

    This utility function queries the database for an event audit record associated
    with the given event ID and raises an HTTPException with status 404 if not found.

    Args:
        event_id: The event ID whose audit to look up
        db: Database session

    Returns:
        EventAudit object if found

    Raises:
        HTTPException: 404 if event audit not found
    """
    result = await db.execute(select(EventAudit).where(EventAudit.event_id == event_id))
    audit = result.scalar_one_or_none()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit found for event {event_id}",
        )

    return audit


# =============================================================================
# Generic Factory for Entity Lookup
# =============================================================================
#
# This factory function creates get_or_404 functions for any model, reducing
# code duplication while maintaining type safety and consistent error handling.
# =============================================================================


def get_or_404_factory[ModelT](
    model_class: type[ModelT],
    entity_name: str,
    id_field: str = "id",
) -> Callable[[str | int, AsyncSession], Coroutine[Any, Any, ModelT]]:
    """Factory function to create a get_or_404 helper for any model.

    This factory creates an async function that queries the database for an entity
    by ID and raises a 404 HTTPException if not found. It provides a consistent
    pattern for entity lookup across different models.

    Args:
        model_class: The SQLAlchemy model class to query
        entity_name: Human-readable name for error messages (e.g., "Camera", "Event")
        id_field: The field name to use for the ID lookup (default: "id")

    Returns:
        An async function that takes (resource_id, db) and returns the entity or raises 404

    Example::

        from backend.api.dependencies import get_or_404_factory
        from backend.models import AlertRule

        get_alert_rule_or_404 = get_or_404_factory(AlertRule, "Alert rule")

        # Usage in route:
        rule = await get_alert_rule_or_404(rule_id, db)
    """

    async def get_or_404(
        resource_id: str | int,
        db: AsyncSession,
    ) -> ModelT:
        """Get an entity by ID or raise 404 if not found.

        Args:
            resource_id: The ID to look up
            db: Database session

        Returns:
            Entity object if found

        Raises:
            HTTPException: 404 if entity not found
        """
        id_column = getattr(model_class, id_field)
        result = await db.execute(select(model_class).where(id_column == resource_id))
        entity = result.scalar_one_or_none()

        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{entity_name} with {id_field} {resource_id} not found",
            )

        return cast("ModelT", entity)

    return get_or_404


async def get_audit_log_or_404(
    audit_id: int,
    db: AsyncSession,
) -> AuditLog:
    """Get an audit log by ID or raise 404 if not found.

    This utility function queries the database for an audit log with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        audit_id: The audit log ID (integer) to look up
        db: Database session

    Returns:
        AuditLog object if found

    Raises:
        HTTPException: 404 if audit log not found
    """
    result = await db.execute(select(AuditLog).where(AuditLog.id == audit_id))
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log with id {audit_id} not found",
        )

    return log


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
