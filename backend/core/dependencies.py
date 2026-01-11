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

__all__ = [
    "get_context_enricher_dependency",
    "get_detector_dependency",
    "get_enrichment_pipeline_dependency",
    "get_face_detector_service_dependency",
    "get_nemotron_analyzer_dependency",
    "get_ocr_service_dependency",
    "get_plate_detector_service_dependency",
    "get_redis_dependency",
    "get_yolo_world_service_dependency",
]

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from backend.core.container import get_container

if TYPE_CHECKING:
    from backend.core.redis import RedisClient
    from backend.services.ai_services import (
        FaceDetectorService,
        OCRService,
        PlateDetectorService,
        YOLOWorldService,
    )
    from backend.services.context_enricher import ContextEnricher
    from backend.services.detector_client import DetectorClient
    from backend.services.enrichment_pipeline import EnrichmentPipeline
    from backend.services.nemotron_analyzer import NemotronAnalyzer


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
