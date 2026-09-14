"""Tests for FastAPI dependency injection functions (NEM-2748).

This module tests the FastAPI-compatible dependency functions that inject
services from the DI container into route handlers.

Test Strategy:
- Dependency resolution for all service types
- AsyncGenerator cleanup and resource management
- Error handling for missing services and container issues
- Integration with FastAPI Depends()
- Database session management
- Redis client resolution
- Service dependencies (AI services, enrichment, etc.)
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.container import Container, ServiceNotFoundError


class TestRedisDependency:
    """Tests for get_redis_dependency."""

    @pytest.mark.asyncio
    async def test_redis_dependency_returns_client(self) -> None:
        """Redis dependency should yield RedisClient from container."""
        from backend.core.dependencies import get_redis_dependency

        mock_redis = AsyncMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get_async = AsyncMock(return_value=mock_redis)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_redis_dependency()
            redis = await gen.__anext__()

            assert redis is mock_redis
            mock_container.get_async.assert_called_once_with("redis_client")

            # Verify it's a generator
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

    @pytest.mark.asyncio
    async def test_redis_dependency_handles_service_not_found(self) -> None:
        """Redis dependency should propagate ServiceNotFoundError."""
        from backend.core.dependencies import get_redis_dependency

        mock_container = MagicMock(spec=Container)
        mock_container.get_async = AsyncMock(side_effect=ServiceNotFoundError("redis_client"))

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_redis_dependency()
            with pytest.raises(ServiceNotFoundError):
                await gen.__anext__()


class TestContextEnricherDependency:
    """Tests for get_context_enricher_dependency."""

    @pytest.mark.asyncio
    async def test_context_enricher_dependency_returns_service(self) -> None:
        """Context enricher dependency should yield ContextEnricher from container."""
        from backend.core.dependencies import get_context_enricher_dependency

        mock_enricher = MagicMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get = MagicMock(return_value=mock_enricher)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_context_enricher_dependency()
            enricher = await gen.__anext__()

            assert enricher is mock_enricher
            mock_container.get.assert_called_once_with("context_enricher")


class TestEnrichmentPipelineDependency:
    """Tests for get_enrichment_pipeline_dependency."""

    @pytest.mark.asyncio
    async def test_enrichment_pipeline_dependency_returns_service(self) -> None:
        """Enrichment pipeline dependency should yield EnrichmentPipeline from container."""
        from backend.core.dependencies import get_enrichment_pipeline_dependency

        mock_pipeline = AsyncMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get_async = AsyncMock(return_value=mock_pipeline)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_enrichment_pipeline_dependency()
            pipeline = await gen.__anext__()

            assert pipeline is mock_pipeline
            mock_container.get_async.assert_called_once_with("enrichment_pipeline")


class TestNemotronAnalyzerDependency:
    """Tests for get_nemotron_analyzer_dependency."""

    @pytest.mark.asyncio
    async def test_nemotron_analyzer_dependency_returns_service(self) -> None:
        """Nemotron analyzer dependency should yield NemotronAnalyzer from container."""
        from backend.core.dependencies import get_nemotron_analyzer_dependency

        mock_analyzer = AsyncMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get_async = AsyncMock(return_value=mock_analyzer)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_nemotron_analyzer_dependency()
            analyzer = await gen.__anext__()

            assert analyzer is mock_analyzer
            mock_container.get_async.assert_called_once_with("nemotron_analyzer")


class TestDetectorDependency:
    """Tests for get_detector_dependency."""

    @pytest.mark.asyncio
    async def test_detector_dependency_returns_client(self) -> None:
        """Detector dependency should yield DetectorClient from container."""
        from backend.core.dependencies import get_detector_dependency

        mock_detector = MagicMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get = MagicMock(return_value=mock_detector)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_detector_dependency()
            detector = await gen.__anext__()

            assert detector is mock_detector
            mock_container.get.assert_called_once_with("detector_client")


class TestAIServiceDependencies:
    """Tests for AI service dependencies (face, plate, OCR, YOLO-World)."""

    @pytest.mark.asyncio
    async def test_face_detector_service_dependency_returns_service(self) -> None:
        """Face detector dependency should yield FaceDetectorService from container."""
        from backend.core.dependencies import get_face_detector_service_dependency

        mock_service = MagicMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get = MagicMock(return_value=mock_service)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_face_detector_service_dependency()
            service = await gen.__anext__()

            assert service is mock_service
            mock_container.get.assert_called_once_with("face_detector_service")

    @pytest.mark.asyncio
    async def test_plate_detector_service_dependency_returns_service(self) -> None:
        """Plate detector dependency should yield PlateDetectorService from container."""
        from backend.core.dependencies import get_plate_detector_service_dependency

        mock_service = MagicMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get = MagicMock(return_value=mock_service)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_plate_detector_service_dependency()
            service = await gen.__anext__()

            assert service is mock_service
            mock_container.get.assert_called_once_with("plate_detector_service")

    @pytest.mark.asyncio
    async def test_ocr_service_dependency_returns_service(self) -> None:
        """OCR service dependency should yield OCRService from container."""
        from backend.core.dependencies import get_ocr_service_dependency

        mock_service = MagicMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get = MagicMock(return_value=mock_service)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_ocr_service_dependency()
            service = await gen.__anext__()

            assert service is mock_service
            mock_container.get.assert_called_once_with("ocr_service")

    @pytest.mark.asyncio
    async def test_yolo_world_service_dependency_returns_service(self) -> None:
        """YOLO-World service dependency should yield YOLOWorldService from container."""
        from backend.core.dependencies import get_yolo_world_service_dependency

        mock_service = MagicMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get = MagicMock(return_value=mock_service)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_yolo_world_service_dependency()
            service = await gen.__anext__()

            assert service is mock_service
            mock_container.get.assert_called_once_with("yolo_world_service")


class TestEntityRepositoryDependency:
    """Tests for get_entity_repository dependency."""

    @pytest.mark.asyncio
    async def test_entity_repository_dependency_creates_repository_with_session(self) -> None:
        """Entity repository dependency should create EntityRepository with database session."""
        from backend.core.dependencies import get_entity_repository

        mock_session = AsyncMock()
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.core.database.get_session", return_value=mock_session_context):
            with patch(
                "backend.repositories.entity_repository.EntityRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo_class.return_value = mock_repo

                gen = get_entity_repository()
                repo = await gen.__anext__()

                assert repo is mock_repo
                mock_repo_class.assert_called_once_with(mock_session)

                # Cleanup
                with pytest.raises(StopAsyncIteration):
                    await gen.__anext__()

    @pytest.mark.asyncio
    async def test_entity_repository_dependency_cleans_up_session(self) -> None:
        """Entity repository dependency should clean up database session after use."""
        from backend.core.dependencies import get_entity_repository

        mock_session = AsyncMock()
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.core.database.get_session", return_value=mock_session_context):
            with patch("backend.repositories.entity_repository.EntityRepository"):
                gen = get_entity_repository()
                await gen.__anext__()

                # Trigger cleanup
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass

                # Verify session context manager was exited
                mock_session_context.__aexit__.assert_called_once()


class TestEntityClusteringServiceDependency:
    """Tests for get_entity_clustering_service dependency."""

    @pytest.mark.asyncio
    async def test_entity_clustering_service_dependency_creates_service(self) -> None:
        """Entity clustering service dependency should create service with repository."""
        from backend.core.dependencies import get_entity_clustering_service

        mock_session = AsyncMock()
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.core.database.get_session", return_value=mock_session_context):
            with patch(
                "backend.repositories.entity_repository.EntityRepository"
            ) as mock_repo_class:
                with patch(
                    "backend.services.entity_clustering_service.EntityClusteringService"
                ) as mock_service_class:
                    mock_repo = MagicMock()
                    mock_service = MagicMock()
                    mock_repo_class.return_value = mock_repo
                    mock_service_class.return_value = mock_service

                    gen = get_entity_clustering_service()
                    service = await gen.__anext__()

                    assert service is mock_service
                    mock_service_class.assert_called_once_with(entity_repository=mock_repo)


class TestHybridEntityStorageDependency:
    """Tests for get_hybrid_entity_storage dependency."""

    @pytest.mark.asyncio
    async def test_hybrid_entity_storage_dependency_creates_storage_with_dependencies(self) -> None:
        """Hybrid entity storage dependency should create storage with all dependencies."""
        from backend.core.dependencies import get_hybrid_entity_storage

        mock_redis = AsyncMock()
        mock_session = AsyncMock()
        mock_reid_service = MagicMock()
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        mock_container = MagicMock(spec=Container)
        mock_container.get_async = AsyncMock(return_value=mock_redis)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            with patch("backend.core.database.get_session", return_value=mock_session_context):
                with patch(
                    "backend.services.reid_service.get_reid_service", return_value=mock_reid_service
                ):
                    with patch(
                        "backend.repositories.entity_repository.EntityRepository"
                    ) as mock_repo_class:
                        with patch(
                            "backend.services.entity_clustering_service.EntityClusteringService"
                        ) as mock_clustering_class:
                            with patch(
                                "backend.services.hybrid_entity_storage.HybridEntityStorage"
                            ) as mock_storage_class:
                                mock_repo = MagicMock()
                                mock_clustering = MagicMock()
                                mock_storage = MagicMock()
                                mock_repo_class.return_value = mock_repo
                                mock_clustering_class.return_value = mock_clustering
                                mock_storage_class.return_value = mock_storage

                                gen = get_hybrid_entity_storage()
                                storage = await gen.__anext__()

                                assert storage is mock_storage
                                mock_storage_class.assert_called_once_with(
                                    redis_client=mock_redis,
                                    entity_repository=mock_repo,
                                    clustering_service=mock_clustering,
                                    reid_service=mock_reid_service,
                                )


class TestReIDServiceDependency:
    """Tests for get_reid_service_dependency."""

    @pytest.mark.asyncio
    async def test_reid_service_dependency_creates_service_with_hybrid_storage(self) -> None:
        """ReID service dependency should create service with hybrid storage configured."""
        from backend.core.dependencies import get_reid_service_dependency

        mock_redis = AsyncMock()
        mock_session = AsyncMock()
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        mock_container = MagicMock(spec=Container)
        mock_container.get_async = AsyncMock(return_value=mock_redis)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            with patch("backend.core.database.get_session", return_value=mock_session_context):
                with patch("backend.repositories.entity_repository.EntityRepository"):
                    with patch(
                        "backend.services.entity_clustering_service.EntityClusteringService"
                    ):
                        with patch(
                            "backend.services.hybrid_entity_storage.HybridEntityStorage"
                        ) as mock_storage_class:
                            with patch(
                                "backend.services.reid_service.ReIdentificationService"
                            ) as mock_reid_class:
                                mock_storage = MagicMock()
                                mock_reid = MagicMock()
                                mock_storage_class.return_value = mock_storage
                                # First call returns base service, second call returns final service
                                mock_reid_class.side_effect = [MagicMock(), mock_reid]

                                gen = get_reid_service_dependency()
                                service = await gen.__anext__()

                                assert service is mock_reid
                                # Verify ReIdentificationService was called twice (base + final)
                                assert mock_reid_class.call_count == 2
                                # Final call should have hybrid_storage kwarg
                                final_call_kwargs = mock_reid_class.call_args_list[1][1]
                                assert "hybrid_storage" in final_call_kwargs


class TestPaginationLimits:
    """Tests for PaginationLimits and get_pagination_limits."""

    def test_pagination_limits_init(self) -> None:
        """PaginationLimits should store max_limit and default_limit."""
        from backend.core.dependencies import PaginationLimits

        limits = PaginationLimits(max_limit=100, default_limit=50)
        assert limits.max_limit == 100
        assert limits.default_limit == 50

    def test_get_pagination_limits_returns_limits_from_settings(self) -> None:
        """get_pagination_limits should return PaginationLimits from settings."""
        from backend.core.dependencies import get_pagination_limits

        mock_settings = MagicMock()
        mock_settings.pagination_max_limit = 100
        mock_settings.pagination_default_limit = 25

        with patch("backend.core.config.get_settings", return_value=mock_settings):
            limits = get_pagination_limits()
            assert limits.max_limit == 100
            assert limits.default_limit == 25


class TestAsyncGeneratorCleanup:
    """Tests for AsyncGenerator cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_redis_dependency_is_async_generator(self) -> None:
        """Redis dependency should be an AsyncGenerator for proper cleanup."""
        from backend.core.dependencies import get_redis_dependency

        mock_redis = AsyncMock()
        mock_container = MagicMock(spec=Container)
        mock_container.get_async = AsyncMock(return_value=mock_redis)

        with patch("backend.core.dependencies.get_container", return_value=mock_container):
            gen = get_redis_dependency()

            # Verify it's an async generator
            assert isinstance(gen, AsyncGenerator)

    @pytest.mark.asyncio
    async def test_entity_repository_dependency_cleans_up_on_exception(self) -> None:
        """Entity repository dependency should clean up session even on exception."""
        from backend.core.dependencies import get_entity_repository

        mock_session = AsyncMock()
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.core.database.get_session", return_value=mock_session_context):
            with patch(
                "backend.repositories.entity_repository.EntityRepository"
            ) as mock_repo_class:
                # Make EntityRepository raise an exception
                mock_repo_class.side_effect = RuntimeError("Test exception")

                gen = get_entity_repository()
                with pytest.raises(RuntimeError, match="Test exception"):
                    await gen.__anext__()

                # Session context should still be cleaned up
                mock_session_context.__aexit__.assert_called_once()
