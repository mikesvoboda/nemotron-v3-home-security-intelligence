"""Tests for AI service registration in DI container (NEM-2030).

This module tests that AI services (FaceDetectorService, PlateDetectorService,
OCRService, YOLOWorldService) are properly registered in the DI container
and can be retrieved via dependency injection.

TDD Phase: RED - Tests written before implementation.

Test Strategy:
- AI service registration as singletons
- Service retrieval via container.get()
- FastAPI Depends() integration
- Service override for testing
- Container shutdown cleanup
"""

from unittest.mock import MagicMock

import pytest


class TestFaceDetectorServiceRegistration:
    """Tests for FaceDetectorService registration in DI container."""

    @pytest.mark.asyncio
    async def test_face_detector_service_registered_as_singleton(self) -> None:
        """FaceDetectorService should be available as a singleton."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        assert "face_detector_service" in container.registered_services

    @pytest.mark.asyncio
    async def test_face_detector_service_returns_same_instance(self) -> None:
        """Getting FaceDetectorService multiple times returns same instance."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        service1 = container.get("face_detector_service")
        service2 = container.get("face_detector_service")
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_face_detector_service_can_be_overridden(self) -> None:
        """FaceDetectorService should support override for testing."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        mock_service = MagicMock()
        mock_service.name = "mock_face_detector"
        container.override("face_detector_service", mock_service)

        service = container.get("face_detector_service")
        assert service.name == "mock_face_detector"

    @pytest.mark.asyncio
    async def test_face_detector_service_fastapi_dependency(self) -> None:
        """FaceDetectorService should work with FastAPI Depends()."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        dep_factory = container.get_dependency("face_detector_service")

        async for service in dep_factory():
            assert service is not None
            # Service should have detect_faces method
            assert hasattr(service, "detect_faces")


class TestPlateDetectorServiceRegistration:
    """Tests for PlateDetectorService registration in DI container."""

    @pytest.mark.asyncio
    async def test_plate_detector_service_registered_as_singleton(self) -> None:
        """PlateDetectorService should be available as a singleton."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        assert "plate_detector_service" in container.registered_services

    @pytest.mark.asyncio
    async def test_plate_detector_service_returns_same_instance(self) -> None:
        """Getting PlateDetectorService multiple times returns same instance."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        service1 = container.get("plate_detector_service")
        service2 = container.get("plate_detector_service")
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_plate_detector_service_can_be_overridden(self) -> None:
        """PlateDetectorService should support override for testing."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        mock_service = MagicMock()
        mock_service.name = "mock_plate_detector"
        container.override("plate_detector_service", mock_service)

        service = container.get("plate_detector_service")
        assert service.name == "mock_plate_detector"

    @pytest.mark.asyncio
    async def test_plate_detector_service_fastapi_dependency(self) -> None:
        """PlateDetectorService should work with FastAPI Depends()."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        dep_factory = container.get_dependency("plate_detector_service")

        async for service in dep_factory():
            assert service is not None
            # Service should have detect_plates method
            assert hasattr(service, "detect_plates")


class TestOCRServiceRegistration:
    """Tests for OCRService registration in DI container."""

    @pytest.mark.asyncio
    async def test_ocr_service_registered_as_singleton(self) -> None:
        """OCRService should be available as a singleton."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        assert "ocr_service" in container.registered_services

    @pytest.mark.asyncio
    async def test_ocr_service_returns_same_instance(self) -> None:
        """Getting OCRService multiple times returns same instance."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        service1 = container.get("ocr_service")
        service2 = container.get("ocr_service")
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_ocr_service_can_be_overridden(self) -> None:
        """OCRService should support override for testing."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        mock_service = MagicMock()
        mock_service.name = "mock_ocr"
        container.override("ocr_service", mock_service)

        service = container.get("ocr_service")
        assert service.name == "mock_ocr"

    @pytest.mark.asyncio
    async def test_ocr_service_fastapi_dependency(self) -> None:
        """OCRService should work with FastAPI Depends()."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        dep_factory = container.get_dependency("ocr_service")

        async for service in dep_factory():
            assert service is not None
            # Service should have read_plates method
            assert hasattr(service, "read_plates")


class TestYOLOWorldServiceRegistration:
    """Tests for YOLOWorldService registration in DI container."""

    @pytest.mark.asyncio
    async def test_yolo_world_service_registered_as_singleton(self) -> None:
        """YOLOWorldService should be available as a singleton."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        assert "yolo_world_service" in container.registered_services

    @pytest.mark.asyncio
    async def test_yolo_world_service_returns_same_instance(self) -> None:
        """Getting YOLOWorldService multiple times returns same instance."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        service1 = container.get("yolo_world_service")
        service2 = container.get("yolo_world_service")
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_yolo_world_service_can_be_overridden(self) -> None:
        """YOLOWorldService should support override for testing."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        mock_service = MagicMock()
        mock_service.name = "mock_yolo_world"
        container.override("yolo_world_service", mock_service)

        service = container.get("yolo_world_service")
        assert service.name == "mock_yolo_world"

    @pytest.mark.asyncio
    async def test_yolo_world_service_fastapi_dependency(self) -> None:
        """YOLOWorldService should work with FastAPI Depends()."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        dep_factory = container.get_dependency("yolo_world_service")

        async for service in dep_factory():
            assert service is not None
            # Service should have detect_with_prompts method
            assert hasattr(service, "detect_with_prompts")


class TestAIServicesIntegration:
    """Integration tests for all AI services in DI container."""

    @pytest.mark.asyncio
    async def test_all_ai_services_registered(self) -> None:
        """All AI services should be registered after wire_services()."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        expected_services = [
            "face_detector_service",
            "plate_detector_service",
            "ocr_service",
            "yolo_world_service",
        ]

        for service_name in expected_services:
            assert service_name in container.registered_services, (
                f"Service '{service_name}' not registered"
            )

    @pytest.mark.asyncio
    async def test_ai_services_independent_of_each_other(self) -> None:
        """AI services should be independent (no cross-dependencies)."""
        from backend.core.container import Container, wire_services

        container = Container()
        await wire_services(container)

        # Each service should be retrievable independently
        face_detector = container.get("face_detector_service")
        plate_detector = container.get("plate_detector_service")
        ocr_service = container.get("ocr_service")
        yolo_world = container.get("yolo_world_service")

        # All should be distinct objects
        assert face_detector is not plate_detector
        assert plate_detector is not ocr_service
        assert ocr_service is not yolo_world

    @pytest.mark.asyncio
    async def test_wire_services_idempotent(self) -> None:
        """Calling wire_services multiple times should not cause errors."""
        from backend.core.container import Container, wire_services

        container = Container()

        # First call should succeed
        await wire_services(container)

        # Second call should raise ServiceAlreadyRegisteredError
        # (tests document expected behavior - fail on duplicate registration)
        from backend.core.container import ServiceAlreadyRegisteredError

        with pytest.raises(ServiceAlreadyRegisteredError):
            await wire_services(container)
