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
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
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

    Args:
        camera_id: The camera ID (UUID string) to look up
        db: Database session
        include_deleted: If True, include soft-deleted cameras in the lookup.
                         Required for restore operations (NEM-1955).

    Returns:
        Camera object if found

    Raises:
        HTTPException: 400 if camera_id is not a valid UUID format
        HTTPException: 404 if camera not found
    """
    # Validate UUID format before database query (NEM-2563)
    validate_uuid(camera_id, "camera_id")

    query = select(Camera).where(Camera.id == camera_id)
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
        Event object if found

    Raises:
        HTTPException: 404 if event not found
    """
    query = select(Event).where(Event.id == event_id)
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
        HTTPException: 400 if rule_id is not a valid UUID format
        HTTPException: 404 if alert rule not found
    """
    # Validate UUID format before database query (NEM-2563)
    validate_uuid(rule_id, "rule_id")

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
        zone_id: The zone ID (UUID string) to look up
        db: Database session
        camera_id: Optional camera ID (UUID string) to filter by (if provided, zone must belong to this camera)

    Returns:
        Zone object if found

    Raises:
        HTTPException: 400 if zone_id or camera_id is not a valid UUID format
        HTTPException: 404 if zone not found or doesn't belong to specified camera
    """
    # Validate UUID format before database query (NEM-2563)
    validate_uuid(zone_id, "zone_id")

    if camera_id is not None:
        validate_uuid(camera_id, "camera_id")

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
    from backend.services.ai_services import FaceDetectorService as FDS

    container = get_container()
    return cast("FDS", container.get("face_detector_service"))


def get_plate_detector_service_dep() -> PlateDetectorService:
    """FastAPI dependency for PlateDetectorService (NEM-2003).

    Returns the PlateDetectorService singleton from the DI container.
    This service wraps license plate detection functionality for detecting
    plates within vehicle bounding box regions.

    Returns:
        PlateDetectorService singleton instance from DI container
    """
    from backend.core.container import get_container
    from backend.services.ai_services import PlateDetectorService as PDS

    container = get_container()
    return cast("PDS", container.get("plate_detector_service"))


def get_ocr_service_dep() -> OCRService:
    """FastAPI dependency for OCRService (NEM-2003).

    Returns the OCRService singleton from the DI container.
    This service wraps PaddleOCR functionality for reading text
    from license plate images.

    Returns:
        OCRService singleton instance from DI container
    """
    from backend.core.container import get_container
    from backend.services.ai_services import OCRService as OCRS

    container = get_container()
    return cast("OCRS", container.get("ocr_service"))


def get_yolo_world_service_dep() -> YOLOWorldService:
    """FastAPI dependency for YOLOWorldService (NEM-2003).

    Returns the YOLOWorldService singleton from the DI container.
    This service wraps YOLO-World open-vocabulary detection functionality
    for detecting custom object classes via text prompts.

    Returns:
        YOLOWorldService singleton instance from DI container
    """
    from backend.core.container import get_container
    from backend.services.ai_services import YOLOWorldService as YWS

    container = get_container()
    return cast("YWS", container.get("yolo_world_service"))


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


# Type-hint-only imports for dependency injection return types
if TYPE_CHECKING:
    from backend.services.ai_services import (
        FaceDetectorService,
        OCRService,
        PlateDetectorService,
        YOLOWorldService,
    )
    from backend.services.export_service import ExportService
    from backend.services.job_history_service import JobHistoryService
    from backend.services.job_search_service import JobSearchService
    from backend.services.job_service import JobService
    from backend.services.job_tracker import JobTracker
