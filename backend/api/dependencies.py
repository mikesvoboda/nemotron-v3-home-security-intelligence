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

5. NullCache and graceful degradation - NEM-2538: When Redis is unavailable,
   non-critical paths can use NullCache as a no-op fallback.

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

Usage (Cache with graceful degradation - NEM-2538):
    from backend.api.dependencies import get_cache, NullCache

    @router.get("/data")
    async def get_data():
        cache = await anext(get_cache(allow_degraded=True))
        # cache will be NullCache if Redis unavailable
        if isinstance(cache, NullCache):
            logger.warning("Operating in degraded mode without cache")
        cached = await cache.get("key")  # Returns None for NullCache
        ...

These patterns simplify the common patterns and enable:
- Clean testability via FastAPI dependency_overrides
- Proper separation of concerns
- Consistent error handling
- Graceful degradation when cache is unavailable (NEM-2538)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import TYPE_CHECKING, Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from backend.core.database import get_db, get_read_db
from backend.core.exceptions import CacheUnavailableError
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, get_redis
from backend.models.alert import AlertRule
from backend.models.audit import AuditLog
from backend.models.camera import Camera
from backend.models.camera_zone import CameraZone
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.models.prompt_version import PromptVersion
from backend.services.cache_service import CacheService

logger = get_logger(__name__)


# =============================================================================
# Cache Availability Tracking (NEM-2538)
# =============================================================================
#
# Module-level state to track cache availability for health checks.
# This allows health endpoints to report degraded status without failing.
# =============================================================================

_cache_available: bool = True
_cache_degraded_since: float | None = None


def is_cache_available() -> bool:
    """Check if cache is currently available.

    Returns:
        True if cache is available, False if operating in degraded mode.
    """
    return _cache_available


def get_cache_degraded_since() -> float | None:
    """Get the timestamp when cache entered degraded mode.

    Returns:
        Unix timestamp when degraded mode started, or None if cache is available.
    """
    return _cache_degraded_since


def _set_cache_available(available: bool) -> None:
    """Update cache availability state (internal use only).

    Args:
        available: Whether cache is available.
    """
    global _cache_available, _cache_degraded_since  # noqa: PLW0603
    import time

    if available and not _cache_available:
        logger.info(
            "Cache connectivity restored, exiting degraded mode",
            extra={"degraded_duration_seconds": time.time() - (_cache_degraded_since or 0)},
        )
        _cache_degraded_since = None
    elif not available and _cache_available:
        logger.warning(
            "Cache unavailable, entering degraded mode",
            extra={"timestamp": time.time()},
        )
        _cache_degraded_since = time.time()

    _cache_available = available


# =============================================================================
# NullCache Pattern (NEM-2538)
# =============================================================================
#
# Null object pattern for cache when Redis is unavailable.
# All operations are no-ops that return safe default values.
# =============================================================================


class NullCache:
    """Null object pattern for cache when Redis is unavailable.

    This class implements the same interface as RedisClient cache operations
    but performs no-op operations. This enables graceful degradation when
    Redis is unavailable - code can continue to function without caching.

    NEM-2538: Added for graceful degradation support.

    Example:
        cache = NullCache()
        await cache.set("key", "value")  # No-op, returns None
        result = await cache.get("key")   # Always returns None
        exists = await cache.exists("key")  # Always returns False
    """

    async def get(self, _key: str) -> None:
        """Get a value from cache (always returns None).

        Args:
            _key: Cache key (ignored).

        Returns:
            Always None since cache is unavailable.
        """
        return None

    async def set(self, _key: str, _value: Any, expire: int | None = None) -> None:
        """Set a value in cache (no-op).

        Args:
            _key: Cache key (ignored).
            _value: Value to store (ignored).
            expire: Expiration time in seconds (ignored).
        """
        del expire  # Unused but part of interface

    async def delete(self, *_keys: str) -> int:
        """Delete keys from cache (no-op).

        Args:
            *_keys: Keys to delete (ignored).

        Returns:
            Always 0 since no keys are deleted.
        """
        return 0

    async def exists(self, *_keys: str) -> int:
        """Check if keys exist in cache (always returns 0).

        Args:
            *_keys: Keys to check (ignored).

        Returns:
            Always 0 since cache is unavailable.
        """
        return 0

    async def expire(self, _key: str, _seconds: int) -> bool:
        """Set TTL on a key (no-op).

        Args:
            _key: Key to set TTL on (ignored).
            _seconds: TTL in seconds (ignored).

        Returns:
            Always False since key doesn't exist.
        """
        return False

    async def health_check(self) -> dict[str, Any]:
        """Check cache health (returns degraded status).

        Returns:
            Dictionary indicating cache is in degraded mode.
        """
        return {
            "status": "degraded",
            "connected": False,
            "mode": "null_cache",
            "error": "Redis unavailable, using NullCache fallback",
        }


# =============================================================================
# Cache Dependency with Graceful Degradation (NEM-2538)
# =============================================================================


async def get_cache(
    allow_degraded: bool = True,
) -> AsyncGenerator[RedisClient | NullCache]:
    """Get cache client with optional graceful degradation.

    This dependency provides a cache client that can gracefully degrade
    to a NullCache when Redis is unavailable. Use allow_degraded=True
    for non-critical paths where caching is optional.

    Args:
        allow_degraded: If True, returns NullCache when Redis is unavailable.
            If False, raises CacheUnavailableError when Redis is unavailable.
            Default is True for backward compatibility.

    Yields:
        RedisClient if connected, or NullCache if Redis unavailable and
        allow_degraded=True.

    Raises:
        CacheUnavailableError: If Redis is unavailable and allow_degraded=False.

    Example (non-critical path - allow degradation)::

        @router.get("/data")
        async def get_data(
            cache: RedisClient | NullCache = Depends(lambda: get_cache(allow_degraded=True))
        ):
            # Will use NullCache if Redis unavailable
            cached = await cache.get("key")

    Example (critical path - require cache)::

        @router.post("/critical")
        async def critical_operation(
            cache: RedisClient = Depends(lambda: get_cache(allow_degraded=False))
        ):
            # Will raise CacheUnavailableError if Redis unavailable
            await cache.set("lock", "1", expire=60)
    """
    try:
        # Try to get Redis client via the existing dependency
        async for redis_client in get_redis():
            # Test connectivity
            await redis_client.health_check()
            _set_cache_available(True)
            yield redis_client
            return
    except (RedisConnectionError, RedisTimeoutError, RuntimeError) as e:
        _set_cache_available(False)

        if allow_degraded:
            logger.warning(
                "Redis unavailable, using NullCache fallback",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "allow_degraded": allow_degraded,
                },
            )
            yield NullCache()
            return
        else:
            logger.error(
                "Redis unavailable and degraded mode not allowed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "allow_degraded": allow_degraded,
                },
            )
            raise CacheUnavailableError(
                "Cache service unavailable and degraded mode not allowed",
                original_error=e,
                allow_degraded=allow_degraded,
            ) from e


if TYPE_CHECKING:
    from backend.services.alert_engine import AlertRuleEngine
    from backend.services.baseline import BaselineService
    from backend.services.clip_generator import ClipGenerator
    from backend.services.container_orchestrator import ContainerOrchestrator
    from backend.services.nemotron_analyzer import NemotronAnalyzer
    from backend.services.thumbnail_generator import ThumbnailGenerator
    from backend.services.video_processor import VideoProcessor


# =============================================================================
# UUID Validation Utilities
# =============================================================================
#
# These utilities validate UUID format before database queries to prevent
# injection attacks and provide clear 400 Bad Request errors for malformed IDs.
# =============================================================================


def validate_uuid(id_str: str, field_name: str) -> UUID:
    """Validate that a string is a valid UUID format.

    This utility validates that the provided string is a valid UUID before
    using it in database queries. This prevents injection attacks and provides
    clear error messages for malformed IDs.

    Args:
        id_str: The string to validate as a UUID
        field_name: Human-readable field name for error messages (e.g., "camera_id")

    Returns:
        UUID object if valid

    Raises:
        HTTPException: 400 Bad Request if the string is not a valid UUID format
    """
    try:
        return UUID(id_str)
    except (ValueError, AttributeError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: '{id_str}' is not a valid UUID",
        ) from err


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
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
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

    NEM-3597: Eagerly loads the 'areas' relationship to support the expanded
    CameraResponse schema that includes property_id and areas.

    Args:
        camera_id: The camera ID (string) to look up. Camera IDs are normalized
                   folder names (e.g., "front_door"), not UUIDs.
        db: Database session
        include_deleted: If True, include soft-deleted cameras in the lookup.
                         Required for restore operations (NEM-1955).

    Returns:
        Camera object if found (with areas relationship loaded)

    Raises:
        HTTPException: 404 if camera not found
    """
    # Note: Camera IDs are strings (normalized folder names), not UUIDs

    query = select(Camera).options(selectinload(Camera.areas)).where(Camera.id == camera_id)
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

    Args:
        event_id: The event ID to look up
        db: Database session
        include_deleted: If True, include soft-deleted events in the lookup.
                         Required for restore operations (NEM-1955).

    Returns:
        Event object if found with deferred columns loaded

    Raises:
        HTTPException: 404 if event not found
    """
    # Eagerly load deferred columns (reasoning, llm_prompt) to prevent lazy loading
    # errors when the session is closed (NEM-XXXX)
    query = (
        select(Event)
        .options(undefer(Event.reasoning), undefer(Event.llm_prompt))
        .where(Event.id == event_id)
    )
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
        Detection object if found with deferred columns loaded

    Raises:
        HTTPException: 404 if detection not found
    """
    # Eagerly load deferred column (enrichment_data) to prevent lazy loading
    # errors when the session is closed (NEM-XXXX)
    query = (
        select(Detection)
        .options(undefer(Detection.enrichment_data))
        .where(Detection.id == detection_id)
    )
    result = await db.execute(query)
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
        rule_id: The alert rule ID (string) to look up
        db: Database session

    Returns:
        AlertRule object if found

    Raises:
        HTTPException: 404 if alert rule not found
    """
    # Note: AlertRule IDs are strings, not UUIDs

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
) -> CameraZone:
    """Get a camera zone by ID or raise 404 if not found.

    This utility function queries the database for a camera zone with the given ID
    and raises an HTTPException with status 404 if not found.

    Args:
        zone_id: The zone ID (string) to look up
        db: Database session
        camera_id: Optional camera ID (string) to filter by (if provided, zone must belong to this camera)

    Returns:
        CameraZone object if found

    Raises:
        HTTPException: 404 if zone not found or doesn't belong to specified camera
    """
    # Note: CameraZone and Camera IDs are strings, not UUIDs

    query = select(CameraZone).where(CameraZone.id == zone_id)

    if camera_id is not None:
        query = query.where(CameraZone.camera_id == camera_id)

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
    *,
    validate_uuid_format: bool = False,
) -> Callable[[str | int, AsyncSession], Coroutine[Any, Any, ModelT]]:
    """Factory function to create a get_or_404 helper for any model.

    This factory creates an async function that queries the database for an entity
    by ID and raises a 404 HTTPException if not found. It provides a consistent
    pattern for entity lookup across different models.

    Args:
        model_class: The SQLAlchemy model class to query
        entity_name: Human-readable name for error messages (e.g., "Camera", "Event")
        id_field: The field name to use for the ID lookup (default: "id")
        validate_uuid_format: If True, validate that the resource_id is a valid UUID
                              before querying the database (NEM-2563)

    Returns:
        An async function that takes (resource_id, db) and returns the entity or raises 404

    Example::

        from backend.api.dependencies import get_or_404_factory
        from backend.models import AlertRule

        # For models with UUID primary keys
        get_alert_rule_or_404 = get_or_404_factory(
            AlertRule, "Alert rule", validate_uuid_format=True
        )

        # For models with integer primary keys
        get_event_or_404 = get_or_404_factory(Event, "Event")

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
            HTTPException: 400 if validate_uuid_format is True and ID is not a valid UUID
            HTTPException: 404 if entity not found
        """
        # Validate UUID format if required (NEM-2563)
        if validate_uuid_format and isinstance(resource_id, str):
            validate_uuid(resource_id, id_field)

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


def get_baseline_service_dep() -> BaselineService:
    """FastAPI dependency for BaselineService (NEM-2032).

    Returns the global BaselineService singleton instance.

    Returns:
        BaselineService singleton instance
    """
    from backend.services.baseline import get_baseline_service

    return get_baseline_service()


def get_clip_generator_dep() -> ClipGenerator:
    """FastAPI dependency for ClipGenerator (NEM-2032).

    Returns the global ClipGenerator singleton instance.

    Returns:
        ClipGenerator singleton instance
    """
    from backend.services.clip_generator import get_clip_generator

    return get_clip_generator()


def get_alert_rule_engine_dep(
    db: AsyncSession = Depends(get_db),
) -> AlertRuleEngine:
    """FastAPI dependency for AlertRuleEngine (NEM-2032).

    Creates an AlertRuleEngine instance with the injected database session.

    Args:
        db: Database session injected via Depends(get_db)

    Returns:
        AlertRuleEngine instance
    """
    from backend.services.alert_engine import AlertRuleEngine

    return AlertRuleEngine(db)


def get_thumbnail_generator_dep() -> ThumbnailGenerator:
    """FastAPI dependency for ThumbnailGenerator (NEM-2032).

    Returns a ThumbnailGenerator instance.

    Returns:
        ThumbnailGenerator instance
    """
    from backend.services.thumbnail_generator import ThumbnailGenerator

    return ThumbnailGenerator()


def get_video_processor_dep() -> VideoProcessor:
    """FastAPI dependency for VideoProcessor (NEM-2032).

    Returns a VideoProcessor instance.

    Returns:
        VideoProcessor instance
    """
    from backend.services.video_processor import VideoProcessor

    return VideoProcessor()


async def get_nemotron_analyzer_dep(
    redis: RedisClient = Depends(get_redis),
) -> AsyncGenerator[NemotronAnalyzer]:
    """FastAPI dependency for NemotronAnalyzer (NEM-2032).

    Creates a NemotronAnalyzer instance with the injected Redis client.

    Args:
        redis: Redis client injected via Depends(get_redis)

    Yields:
        NemotronAnalyzer instance
    """
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    yield NemotronAnalyzer(redis_client=redis)


def get_job_tracker_dep(
    redis: RedisClient = Depends(get_redis),
) -> JobTracker:
    """FastAPI dependency for JobTracker (NEM-1989).

    Returns the global JobTracker singleton instance with Redis persistence.

    Args:
        redis: Redis client for job persistence.

    Returns:
        JobTracker singleton instance
    """
    from backend.services.job_tracker import get_job_tracker

    return get_job_tracker(redis_client=redis)


def get_export_service_dep(
    db: AsyncSession = Depends(get_db),
) -> ExportService:
    """FastAPI dependency for ExportService (NEM-1989).

    Creates an ExportService instance with the injected database session.

    Args:
        db: Database session injected via Depends(get_db)

    Returns:
        ExportService instance
    """
    from backend.services.export_service import ExportService

    return ExportService(db)


def get_face_detector_service_dep() -> FaceDetectorService:
    """FastAPI dependency for FaceDetectorService (NEM-2003).

    Returns the FaceDetectorService singleton from the DI container.
    This service wraps face detection functionality for detecting faces
    within person bounding box regions.

    Returns:
        FaceDetectorService singleton instance from DI container
    """
    from backend.core.container import get_container

    container = get_container()
    return cast("FaceDetectorService", container.get("face_detector_service"))


def get_plate_detector_service_dep() -> PlateDetectorService:
    """FastAPI dependency for PlateDetectorService (NEM-2003).

    Returns the PlateDetectorService singleton from the DI container.
    This service wraps license plate detection functionality for detecting
    plates within vehicle bounding box regions.

    Returns:
        PlateDetectorService singleton instance from DI container
    """
    from backend.core.container import get_container

    container = get_container()
    return cast("PlateDetectorService", container.get("plate_detector_service"))


def get_ocr_service_dep() -> OCRService:
    """FastAPI dependency for OCRService (NEM-2003).

    Returns the OCRService singleton from the DI container.
    This service wraps PaddleOCR functionality for reading text
    from license plate images.

    Returns:
        OCRService singleton instance from DI container
    """
    from backend.core.container import get_container

    container = get_container()
    return cast("OCRService", container.get("ocr_service"))


def get_yolo_world_service_dep() -> YOLOWorldService:
    """FastAPI dependency for YOLOWorldService (NEM-2003).

    Returns the YOLOWorldService singleton from the DI container.
    This service wraps YOLO-World open-vocabulary detection functionality
    for detecting custom object classes via text prompts.

    Returns:
        YOLOWorldService singleton instance from DI container
    """
    from backend.core.container import get_container

    container = get_container()
    return cast("YOLOWorldService", container.get("yolo_world_service"))


def get_job_service_dep(
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
    redis: RedisClient = Depends(get_redis),
) -> JobService:
    """FastAPI dependency for JobService (NEM-2390).

    Returns a JobService instance with the injected JobTracker and Redis client.
    Provides detailed job information retrieval and transformation.

    Args:
        job_tracker: JobTracker instance injected via Depends.
        redis: Redis client for job persistence.

    Returns:
        JobService instance
    """
    from backend.services.job_service import JobService

    return JobService(job_tracker=job_tracker, redis_client=redis)


def get_job_search_service_dep(
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> JobSearchService:
    """FastAPI dependency for JobSearchService (NEM-2392).

    Returns a JobSearchService instance with the injected JobTracker.
    Provides job search, filtering, and aggregation capabilities.

    Args:
        job_tracker: JobTracker instance injected via Depends.

    Returns:
        JobSearchService instance
    """
    from backend.services.job_search_service import JobSearchService

    return JobSearchService(job_tracker=job_tracker)


async def get_job_history_service_dep(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[JobHistoryService]:
    """FastAPI dependency for JobHistoryService (NEM-2396).

    Returns a JobHistoryService instance with the injected database session.
    Provides job history, transitions, attempts, and logs retrieval.

    Args:
        db: Database session injected via Depends(get_db).

    Yields:
        JobHistoryService instance
    """
    from backend.services.job_history_service import JobHistoryService

    yield JobHistoryService(db)


def get_health_service_registry_dep() -> HealthServiceRegistry:
    """FastAPI dependency for HealthServiceRegistry (NEM-2611).

    Returns the HealthServiceRegistry singleton from the DI container.
    This registry provides centralized access to health monitoring services
    without using global state.

    Returns:
        HealthServiceRegistry singleton instance from DI container

    Raises:
        HTTPException: 503 if health registry is not available
    """
    from backend.core.container import ServiceNotFoundError, get_container

    container = get_container()
    try:
        return cast("HealthServiceRegistry", container.get("health_service_registry"))
    except ServiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health service registry not available",
        ) from e


def get_health_event_emitter_dep() -> HealthEventEmitter:
    """FastAPI dependency for HealthEventEmitter (NEM-2611).

    Returns the HealthEventEmitter singleton from the DI container.
    This service manages WebSocket health event emission.

    Returns:
        HealthEventEmitter singleton instance from DI container

    Raises:
        HTTPException: 503 if health event emitter is not available
    """
    from backend.core.container import ServiceNotFoundError, get_container

    container = get_container()
    try:
        return cast("HealthEventEmitter", container.get("health_event_emitter"))
    except ServiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health event emitter not available",
        ) from e


def get_transcoding_service_dep() -> TranscodingService:
    """FastAPI dependency for TranscodingService (NEM-2681).

    Returns the global TranscodingService singleton instance for
    transcoding videos to browser-compatible formats.

    Returns:
        TranscodingService singleton instance
    """
    from backend.services.transcoding_service import get_transcoding_service

    return get_transcoding_service()


# Type-hint-only imports for dependency injection return types
if TYPE_CHECKING:
    from backend.services.ai_services import (
        FaceDetectorService,
        OCRService,
        PlateDetectorService,
        YOLOWorldService,
    )
    from backend.services.export_service import ExportService
    from backend.services.health_event_emitter import HealthEventEmitter
    from backend.services.health_service_registry import HealthServiceRegistry
    from backend.services.job_history_service import JobHistoryService
    from backend.services.job_search_service import JobSearchService
    from backend.services.job_service import JobService
    from backend.services.job_tracker import JobTracker
    from backend.services.transcoding_service import TranscodingService


# =============================================================================
# Transaction Management Utilities (NEM-3346)
# =============================================================================
#
# These utilities provide proper transaction management and scoping for
# database operations, ensuring correct commit/rollback timing.
# =============================================================================


async def get_db_readonly() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency for read-only database sessions.

    This dependency provides a session intended for read-only operations.
    Use this for endpoints that only read data to make the intent clear.

    Yields:
        AsyncSession: A session intended for read-only operations
    """
    from backend.core.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class TransactionContext:
    """Helper class for explicit transaction control.

    Provides methods for explicit transaction management within a request.
    Use this when you need fine-grained control over commit/rollback points.

    NEM-3346: Proper transaction timing for complex operations.

    Attributes:
        session: The underlying database session

    Example:
        @router.post("/transfer")
        async def transfer_funds(
            request: TransferRequest,
            db: AsyncSession = Depends(get_db)
        ):
            tx = TransactionContext(db)

            # Debit source account
            await debit_account(request.source_id, request.amount, db)
            await tx.flush()  # Ensure debit is visible within transaction

            # Credit destination account
            await credit_account(request.dest_id, request.amount, db)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize transaction context with a session.

        Args:
            session: The database session from get_db()
        """
        self.session = session

    async def flush(self) -> None:
        """Flush pending changes to the database.

        This sends pending INSERT/UPDATE/DELETE statements to the database
        but does NOT commit the transaction.
        """
        await self.session.flush()

    async def refresh(self, instance: object, attribute_names: list[str] | None = None) -> None:
        """Refresh an instance from the database.

        Args:
            instance: The model instance to refresh
            attribute_names: Optional list of specific attributes to refresh
        """
        await self.session.refresh(instance, attribute_names=attribute_names)


def get_transaction_context(session: AsyncSession) -> TransactionContext:
    """Factory function to create a TransactionContext.

    Args:
        session: The database session from get_db()

    Returns:
        TransactionContext for explicit transaction management
    """
    return TransactionContext(session)


async def nested_transaction(session: AsyncSession) -> AsyncGenerator[None]:
    """Context manager for nested transactions (savepoints).

    Use this within a request to create a savepoint that can be
    independently rolled back without affecting the outer transaction.

    Args:
        session: The database session from get_db()

    Yields:
        None - the session is used directly within the context
    """
    async with session.begin_nested():
        yield


# =============================================================================
# Annotated Dependency Type Aliases (NEM-3742)
# =============================================================================
# Modern FastAPI dependency injection using Annotated pattern from Python 3.9+
# and FastAPI 0.95+. These type aliases provide:
# 1. Reusability across multiple endpoints
# 2. Cleaner function signatures (no = Depends(...) in parameters)
# 3. Better IDE support with explicit type hints
# 4. Centralized dependency configuration
#
# See backend/api/AGENTS.md for usage examples.
# =============================================================================


async def get_redis_optional() -> RedisClient | None:
    """Get Redis client or None if unavailable.

    This is useful for endpoints that can function without Redis but
    benefit from having it available (e.g., health checks, debug endpoints).

    Returns:
        RedisClient if available, None otherwise.
    """
    try:
        async for redis in get_redis():
            return redis
    except Exception:
        return None
    return None


# -----------------------------------------------------------------------------
# Core Database Dependencies
# -----------------------------------------------------------------------------

#: Database session dependency for write operations.
#: Provides an AsyncSession from the primary database with automatic
#: commit/rollback handling.
DbSession = Annotated[AsyncSession, Depends(get_db)]

#: Database session dependency for read-only operations (NEM-3392).
#: Uses read replica if configured, otherwise falls back to primary.
ReadDbSession = Annotated[AsyncSession, Depends(get_read_db)]

# -----------------------------------------------------------------------------
# Redis/Cache Dependencies
# -----------------------------------------------------------------------------

#: Redis client dependency for cache and pub/sub operations.
RedisDep = Annotated[RedisClient, Depends(get_redis)]

#: Optional Redis dependency that returns None if Redis is unavailable.
RedisOptionalDep = Annotated[RedisClient | None, Depends(get_redis_optional)]

#: Cache service dependency with Redis backend.
CacheDep = Annotated[CacheService, Depends(get_cache_service_dep)]

#: Cache dependency with graceful degradation (NEM-2538).
#: Returns NullCache when Redis is unavailable.
CacheWithFallbackDep = Annotated[
    RedisClient | NullCache,
    Depends(lambda: get_cache(allow_degraded=True)),
]

#: Strict cache dependency that raises when Redis is unavailable.
StrictCacheDep = Annotated[
    RedisClient,
    Depends(lambda: get_cache(allow_degraded=False)),
]

# -----------------------------------------------------------------------------
# Service Dependencies
# -----------------------------------------------------------------------------

#: Container orchestrator dependency for service management.
OrchestratorDep = Annotated["ContainerOrchestrator", Depends(get_orchestrator)]

#: Baseline service dependency for activity baseline operations.
BaselineServiceDep = Annotated["BaselineService", Depends(get_baseline_service_dep)]

#: Clip generator dependency for video clip extraction.
ClipGeneratorDep = Annotated["ClipGenerator", Depends(get_clip_generator_dep)]

#: Alert rule engine dependency for alert evaluation.
AlertRuleEngineDep = Annotated["AlertRuleEngine", Depends(get_alert_rule_engine_dep)]

#: Thumbnail generator dependency for image thumbnail creation.
ThumbnailGeneratorDep = Annotated["ThumbnailGenerator", Depends(get_thumbnail_generator_dep)]

#: Video processor dependency for video file operations.
VideoProcessorDep = Annotated["VideoProcessor", Depends(get_video_processor_dep)]

#: Nemotron analyzer dependency for LLM-based analysis.
NemotronAnalyzerDep = Annotated["NemotronAnalyzer", Depends(get_nemotron_analyzer_dep)]

#: Job tracker dependency for async job management.
JobTrackerDep = Annotated["JobTracker", Depends(get_job_tracker_dep)]

#: Export service dependency for data export operations.
ExportServiceDep = Annotated["ExportService", Depends(get_export_service_dep)]

#: Job service dependency for detailed job information.
JobServiceDep = Annotated["JobService", Depends(get_job_service_dep)]

#: Job search service dependency for job filtering and aggregation.
JobSearchServiceDep = Annotated["JobSearchService", Depends(get_job_search_service_dep)]

#: Job history service dependency for job history retrieval.
JobHistoryServiceDep = Annotated["JobHistoryService", Depends(get_job_history_service_dep)]

#: Health service registry dependency for health monitoring.
HealthServiceRegistryDep = Annotated[
    "HealthServiceRegistry",
    Depends(get_health_service_registry_dep),
]

#: Health event emitter dependency for WebSocket health events.
HealthEventEmitterDep = Annotated["HealthEventEmitter", Depends(get_health_event_emitter_dep)]

#: Transcoding service dependency for video transcoding.
TranscodingServiceDep = Annotated["TranscodingService", Depends(get_transcoding_service_dep)]

# -----------------------------------------------------------------------------
# Request Dependencies
# -----------------------------------------------------------------------------

#: FastAPI Request object dependency.
RequestDep = Annotated[Request, Depends()]
