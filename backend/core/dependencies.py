"""FastAPI dependencies using the DI container (NEM-1636).

This module provides FastAPI-compatible dependency functions that can be used
with Depends() to inject services from the DI container into route handlers.

Usage:
    from fastapi import Depends
    from backend.core.dependencies import get_redis_dependency, get_detector_dependency

    @router.get("/detections")
    async def get_detections(
        redis: RedisClient = Depends(get_redis_dependency),
        detector: DetectorClient = Depends(get_detector_dependency),
    ):
        ...

Note: These dependencies are optional and provide an alternative to the existing
global singleton patterns. Both approaches work - use what fits your use case.
"""

from __future__ import annotations

__all__ = [
    "get_context_enricher_dependency",
    "get_detector_dependency",
    "get_enrichment_pipeline_dependency",
    "get_entity_clustering_service",
    "get_entity_repository",
    "get_face_detector_service_dependency",
    "get_hybrid_entity_storage",
    "get_nemotron_analyzer_dependency",
    "get_ocr_service_dependency",
    "get_plate_detector_service_dependency",
    "get_redis_dependency",
    "get_reid_service_dependency",
    "get_yolo_world_service_dependency",
]

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from backend.core.container import get_container

if TYPE_CHECKING:
    from backend.core.redis import RedisClient
    from backend.repositories.entity_repository import EntityRepository
    from backend.services.ai_services import (
        FaceDetectorService,
        OCRService,
        PlateDetectorService,
        YOLOWorldService,
    )
    from backend.services.context_enricher import ContextEnricher
    from backend.services.detector_client import DetectorClient
    from backend.services.enrichment_pipeline import EnrichmentPipeline
    from backend.services.entity_clustering_service import EntityClusteringService
    from backend.services.hybrid_entity_storage import HybridEntityStorage
    from backend.services.nemotron_analyzer import NemotronAnalyzer
    from backend.services.reid_service import ReIdentificationService


async def get_redis_dependency() -> AsyncGenerator[RedisClient]:
    """FastAPI dependency for RedisClient.

    This provides the RedisClient from the DI container. The client
    is a singleton that is initialized once and reused for all requests.

    Yields:
        RedisClient instance from the container
    """
    container = get_container()
    redis = await container.get_async("redis_client")
    yield redis


async def get_context_enricher_dependency() -> AsyncGenerator[ContextEnricher]:
    """FastAPI dependency for ContextEnricher.

    Yields:
        ContextEnricher instance from the container
    """
    container = get_container()
    enricher = container.get("context_enricher")
    yield enricher


async def get_enrichment_pipeline_dependency() -> AsyncGenerator[EnrichmentPipeline]:
    """FastAPI dependency for EnrichmentPipeline.

    Yields:
        EnrichmentPipeline instance from the container
    """
    container = get_container()
    pipeline = await container.get_async("enrichment_pipeline")
    yield pipeline


async def get_nemotron_analyzer_dependency() -> AsyncGenerator[NemotronAnalyzer]:
    """FastAPI dependency for NemotronAnalyzer.

    Yields:
        NemotronAnalyzer instance from the container
    """
    container = get_container()
    analyzer = await container.get_async("nemotron_analyzer")
    yield analyzer


async def get_detector_dependency() -> AsyncGenerator[DetectorClient]:
    """FastAPI dependency for DetectorClient.

    Yields:
        DetectorClient instance from the container
    """
    container = get_container()
    detector = container.get("detector_client")
    yield detector


async def get_face_detector_service_dependency() -> AsyncGenerator[FaceDetectorService]:
    """FastAPI dependency for FaceDetectorService.

    This provides the FaceDetectorService from the DI container for face
    detection operations in person detection regions.

    Yields:
        FaceDetectorService instance from the container
    """
    container = get_container()
    service = container.get("face_detector_service")
    yield service


async def get_plate_detector_service_dependency() -> AsyncGenerator[PlateDetectorService]:
    """FastAPI dependency for PlateDetectorService.

    This provides the PlateDetectorService from the DI container for license
    plate detection operations in vehicle regions.

    Yields:
        PlateDetectorService instance from the container
    """
    container = get_container()
    service = container.get("plate_detector_service")
    yield service


async def get_ocr_service_dependency() -> AsyncGenerator[OCRService]:
    """FastAPI dependency for OCRService.

    This provides the OCRService from the DI container for license plate
    text recognition using PaddleOCR.

    Yields:
        OCRService instance from the container
    """
    container = get_container()
    service = container.get("ocr_service")
    yield service


async def get_yolo_world_service_dependency() -> AsyncGenerator[YOLOWorldService]:
    """FastAPI dependency for YOLOWorldService.

    This provides the YOLOWorldService from the DI container for open-vocabulary
    object detection using text prompts.

    Yields:
        YOLOWorldService instance from the container
    """
    container = get_container()
    service = container.get("yolo_world_service")
    yield service


async def get_entity_repository() -> AsyncGenerator[EntityRepository]:
    """FastAPI dependency for EntityRepository.

    This provides an EntityRepository instance with a managed database session.
    The session is automatically created and cleaned up for each request.

    Usage:
        @router.get("/entities")
        async def list_entities(
            repo: EntityRepository = Depends(get_entity_repository),
        ):
            entities, total = await repo.list(limit=50)
            return {"entities": entities, "total": total}

    Yields:
        EntityRepository instance with active database session

    Related to NEM-2496: Create EntityRepository for PostgreSQL CRUD.
    """
    from backend.core.database import get_session
    from backend.repositories.entity_repository import EntityRepository

    async with get_session() as session:
        yield EntityRepository(session)


async def get_entity_clustering_service() -> AsyncGenerator[EntityClusteringService]:
    """FastAPI dependency for EntityClusteringService.

    This provides an EntityClusteringService instance with a managed database session.
    The service is created with an EntityRepository that has its own session,
    which is automatically cleaned up for each request.

    Usage:
        @router.post("/entities/assign")
        async def assign_entity(
            service: EntityClusteringService = Depends(get_entity_clustering_service),
        ):
            entity, is_new, similarity = await service.assign_entity(...)
            return {"entity_id": str(entity.id), "is_new": is_new}

    Yields:
        EntityClusteringService instance with active database session

    Related to NEM-2497: Create Entity Clustering Service.
    """
    from backend.core.database import get_session
    from backend.repositories.entity_repository import EntityRepository
    from backend.services.entity_clustering_service import EntityClusteringService

    async with get_session() as session:
        repo = EntityRepository(session)
        yield EntityClusteringService(entity_repository=repo)


async def get_hybrid_entity_storage() -> AsyncGenerator[HybridEntityStorage]:
    """FastAPI dependency for HybridEntityStorage.

    This provides a HybridEntityStorage instance with all required dependencies:
    - Redis client from the DI container
    - EntityRepository with managed database session
    - EntityClusteringService for entity assignment
    - ReIdentificationService for Redis embedding operations

    The service coordinates entity storage between Redis (hot cache) and
    PostgreSQL (persistence) for the Hybrid Entity Storage Architecture.

    Usage:
        @router.post("/entities/store")
        async def store_entity_embedding(
            storage: HybridEntityStorage = Depends(get_hybrid_entity_storage),
        ):
            entity_id, is_new = await storage.store_detection_embedding(...)
            return {"entity_id": str(entity_id), "is_new": is_new}

    Yields:
        HybridEntityStorage instance with active database session

    Related to NEM-2498: Implement Hybrid Storage Bridge (Redis <-> PostgreSQL).
    """
    from backend.core.database import get_session
    from backend.repositories.entity_repository import EntityRepository
    from backend.services.entity_clustering_service import EntityClusteringService
    from backend.services.hybrid_entity_storage import HybridEntityStorage
    from backend.services.reid_service import get_reid_service

    container = get_container()
    redis = await container.get_async("redis_client")
    reid_service = get_reid_service()

    async with get_session() as session:
        repo = EntityRepository(session)
        clustering_service = EntityClusteringService(entity_repository=repo)
        yield HybridEntityStorage(
            redis_client=redis,
            entity_repository=repo,
            clustering_service=clustering_service,
            reid_service=reid_service,
        )


async def get_reid_service_dependency() -> AsyncGenerator[ReIdentificationService]:
    """FastAPI dependency for ReIdentificationService with optional hybrid storage.

    This provides a ReIdentificationService instance with HybridEntityStorage
    injected for PostgreSQL persistence support. When hybrid_storage is configured,
    the service can store and search entities in both Redis and PostgreSQL.

    Usage:
        @router.post("/detections/embedding")
        async def store_embedding(
            reid: ReIdentificationService = Depends(get_reid_service_dependency),
        ):
            entity_id = await reid.store_embedding(
                redis_client, embedding, persist_to_postgres=True
            )
            return {"entity_id": str(entity_id)}

    Yields:
        ReIdentificationService instance with HybridEntityStorage configured

    Related to NEM-2499: Update ReIdentificationService to Use Hybrid Storage.
    """
    from backend.core.database import get_session
    from backend.repositories.entity_repository import EntityRepository
    from backend.services.entity_clustering_service import EntityClusteringService
    from backend.services.hybrid_entity_storage import HybridEntityStorage
    from backend.services.reid_service import ReIdentificationService

    container = get_container()
    redis = await container.get_async("redis_client")

    async with get_session() as session:
        repo = EntityRepository(session)
        clustering_service = EntityClusteringService(entity_repository=repo)

        # Create a basic ReIdentificationService first (without circular dependency)
        base_reid_service = ReIdentificationService()

        # Create HybridEntityStorage with the base service
        hybrid_storage = HybridEntityStorage(
            redis_client=redis,
            entity_repository=repo,
            clustering_service=clustering_service,
            reid_service=base_reid_service,
        )

        # Create and yield the final ReIdentificationService with hybrid storage
        yield ReIdentificationService(hybrid_storage=hybrid_storage)
