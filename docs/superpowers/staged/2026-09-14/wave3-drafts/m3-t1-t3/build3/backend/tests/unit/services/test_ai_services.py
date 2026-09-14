"""Unit tests for AI service wrapper classes (NEM-2030).

This module tests the AI service wrappers that provide dependency injection
interfaces for face detection, plate detection, OCR, and YOLO-World detection.

Test Strategy:
- Service initialization
- Delegation to underlying functions
- Model lifecycle management
- Error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.ai_services import (
    FaceDetectorService,
    OCRService,
    PlateDetectorService,
    YOLOWorldService,
)


class TestFaceDetectorService:
    """Tests for FaceDetectorService wrapper class."""

    def test_initialization_without_model(self) -> None:
        """Service should initialize without a model."""
        service = FaceDetectorService()
        assert service.model is None

    def test_initialization_with_model(self) -> None:
        """Service should store model if provided."""
        mock_model = MagicMock()
        service = FaceDetectorService(model=mock_model)
        assert service.model is mock_model

    @pytest.mark.asyncio
    async def test_detect_faces_delegates_to_function(self) -> None:
        """detect_faces should delegate to face_detector.detect_faces."""
        mock_model = MagicMock()
        service = FaceDetectorService(model=mock_model)

        mock_detections = [MagicMock()]
        mock_images = {"path.jpg": MagicMock()}
        mock_result = [MagicMock()]

        with patch(
            "backend.services.face_detector.detect_faces", new_callable=AsyncMock
        ) as mock_detect:
            mock_detect.return_value = mock_result

            result = await service.detect_faces(
                person_detections=mock_detections,
                images=mock_images,
                confidence_threshold=0.5,
            )

            mock_detect.assert_called_once_with(
                model=mock_model,
                person_detections=mock_detections,
                images=mock_images,
                confidence_threshold=0.5,
                head_ratio=0.4,
                padding=0.2,
            )
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_detect_faces_uses_model_override(self) -> None:
        """detect_faces should use model parameter over self.model."""
        default_model = MagicMock(name="default")
        override_model = MagicMock(name="override")
        service = FaceDetectorService(model=default_model)

        with patch(
            "backend.services.face_detector.detect_faces", new_callable=AsyncMock
        ) as mock_detect:
            mock_detect.return_value = []

            await service.detect_faces(
                person_detections=[],
                model=override_model,
            )

            # Should use override model, not default
            call_kwargs = mock_detect.call_args.kwargs
            assert call_kwargs["model"] is override_model


class TestPlateDetectorService:
    """Tests for PlateDetectorService wrapper class."""

    def test_initialization_without_model(self) -> None:
        """Service should initialize without a model."""
        service = PlateDetectorService()
        assert service.model is None

    def test_initialization_with_model(self) -> None:
        """Service should store model if provided."""
        mock_model = MagicMock()
        service = PlateDetectorService(model=mock_model)
        assert service.model is mock_model

    @pytest.mark.asyncio
    async def test_detect_plates_delegates_to_function(self) -> None:
        """detect_plates should delegate to plate_detector.detect_plates."""
        mock_model = MagicMock()
        service = PlateDetectorService(model=mock_model)

        mock_detections = [MagicMock()]
        mock_images = {"path.jpg": MagicMock()}
        mock_result = [MagicMock()]

        with patch(
            "backend.services.plate_detector.detect_plates", new_callable=AsyncMock
        ) as mock_detect:
            mock_detect.return_value = mock_result

            result = await service.detect_plates(
                vehicle_detections=mock_detections,
                images=mock_images,
                confidence_threshold=0.3,
            )

            mock_detect.assert_called_once_with(
                model=mock_model,
                vehicle_detections=mock_detections,
                images=mock_images,
                confidence_threshold=0.3,
                padding=0.1,
            )
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_detect_plates_uses_model_override(self) -> None:
        """detect_plates should use model parameter over self.model."""
        default_model = MagicMock(name="default")
        override_model = MagicMock(name="override")
        service = PlateDetectorService(model=default_model)

        with patch(
            "backend.services.plate_detector.detect_plates", new_callable=AsyncMock
        ) as mock_detect:
            mock_detect.return_value = []

            await service.detect_plates(
                vehicle_detections=[],
                model=override_model,
            )

            call_kwargs = mock_detect.call_args.kwargs
            assert call_kwargs["model"] is override_model


class TestOCRService:
    """Tests for OCRService wrapper class."""

    def test_initialization_without_model(self) -> None:
        """Service should initialize without a model."""
        service = OCRService()
        assert service.model is None

    def test_initialization_with_model(self) -> None:
        """Service should store model if provided."""
        mock_model = MagicMock()
        service = OCRService(model=mock_model)
        assert service.model is mock_model

    @pytest.mark.asyncio
    async def test_read_plates_delegates_to_function(self) -> None:
        """read_plates should delegate to ocr_service.read_plates."""
        mock_model = MagicMock()
        service = OCRService(model=mock_model)

        mock_detections = [MagicMock()]
        mock_images = {"path.jpg": MagicMock()}
        mock_result = [MagicMock()]

        with patch("backend.services.ocr_service.read_plates", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = mock_result

            result = await service.read_plates(
                plate_detections=mock_detections,
                images=mock_images,
                min_confidence=0.6,
            )

            mock_read.assert_called_once_with(
                ocr_model=mock_model,
                plate_detections=mock_detections,
                images=mock_images,
                image_paths=None,
                min_confidence=0.6,
            )
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_read_single_plate_delegates_to_function(self) -> None:
        """read_single_plate should delegate to ocr_service.read_single_plate."""
        mock_model = MagicMock()
        service = OCRService(model=mock_model)

        mock_image = MagicMock()
        mock_result = MagicMock()

        with patch(
            "backend.services.ocr_service.read_single_plate", new_callable=AsyncMock
        ) as mock_read:
            mock_read.return_value = mock_result

            result = await service.read_single_plate(
                plate_image=mock_image,
                min_confidence=0.7,
            )

            mock_read.assert_called_once_with(
                ocr_model=mock_model,
                plate_image=mock_image,
                min_confidence=0.7,
            )
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_read_plates_uses_model_override(self) -> None:
        """read_plates should use model parameter over self.model."""
        default_model = MagicMock(name="default")
        override_model = MagicMock(name="override")
        service = OCRService(model=default_model)

        with patch("backend.services.ocr_service.read_plates", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = []

            await service.read_plates(
                plate_detections=[],
                model=override_model,
            )

            call_kwargs = mock_read.call_args.kwargs
            assert call_kwargs["ocr_model"] is override_model


class TestYOLOWorldService:
    """Tests for YOLOWorldService wrapper class."""

    def test_initialization_without_model(self) -> None:
        """Service should initialize without a model."""
        service = YOLOWorldService()
        assert service.model is None
        assert service.model_path == "yolov8s-worldv2.pt"

    def test_initialization_with_model(self) -> None:
        """Service should store model if provided."""
        mock_model = MagicMock()
        service = YOLOWorldService(model=mock_model)
        assert service.model is mock_model

    def test_initialization_with_custom_model_path(self) -> None:
        """Service should use custom model path."""
        service = YOLOWorldService(model_path="custom_model.pt")
        assert service.model_path == "custom_model.pt"

    @pytest.mark.asyncio
    async def test_load_model_creates_model(self) -> None:
        """load_model should load model from path if not already loaded."""
        service = YOLOWorldService(model_path="test_model.pt")

        mock_model = MagicMock()
        with patch(
            "backend.services.yolo_world_loader.load_yolo_world_model",
            new_callable=AsyncMock,
        ) as mock_load:
            mock_load.return_value = mock_model

            result = await service.load_model()

            mock_load.assert_called_once_with("test_model.pt")
            assert result is mock_model
            assert service.model is mock_model

    @pytest.mark.asyncio
    async def test_load_model_returns_existing(self) -> None:
        """load_model should return existing model if already loaded."""
        mock_model = MagicMock()
        service = YOLOWorldService(model=mock_model)

        with patch(
            "backend.services.yolo_world_loader.load_yolo_world_model",
            new_callable=AsyncMock,
        ) as mock_load:
            result = await service.load_model()

            mock_load.assert_not_called()
            assert result is mock_model

    @pytest.mark.asyncio
    async def test_detect_with_prompts_delegates_to_function(self) -> None:
        """detect_with_prompts should delegate to yolo_world_loader."""
        mock_model = MagicMock()
        service = YOLOWorldService(model=mock_model)

        mock_image = MagicMock()
        mock_prompts = ["person", "car"]
        mock_result = [{"class_name": "person", "confidence": 0.9}]

        with patch(
            "backend.services.yolo_world_loader.detect_with_prompts",
            new_callable=AsyncMock,
        ) as mock_detect:
            mock_detect.return_value = mock_result

            result = await service.detect_with_prompts(
                image=mock_image,
                prompts=mock_prompts,
                confidence_threshold=0.3,
            )

            mock_detect.assert_called_once_with(
                model=mock_model,
                image=mock_image,
                prompts=mock_prompts,
                confidence_threshold=0.3,
                iou_threshold=0.45,
            )
            assert result == mock_result

    def test_get_security_prompts(self) -> None:
        """get_security_prompts should return default security prompts."""
        service = YOLOWorldService()

        # Call the method and verify it returns a list
        prompts = service.get_security_prompts()
        assert isinstance(prompts, list)
        # Should contain security-related items
        assert "person" in prompts or "package" in prompts

    def test_get_all_security_prompts(self) -> None:
        """get_all_security_prompts should return combined prompts."""
        service = YOLOWorldService()

        with patch("backend.services.yolo_world_loader.get_all_security_prompts") as mock_get:
            mock_get.return_value = ["person", "car", "dog"]

            prompts = service.get_all_security_prompts()

            mock_get.assert_called_once()
            assert prompts == ["person", "car", "dog"]

    def test_get_threat_prompts(self) -> None:
        """get_threat_prompts should return threat-related prompts."""
        service = YOLOWorldService()

        with patch("backend.services.yolo_world_loader.get_threat_prompts") as mock_get:
            mock_get.return_value = ["knife", "crowbar"]

            prompts = service.get_threat_prompts()

            mock_get.assert_called_once()
            assert prompts == ["knife", "crowbar"]

    def test_get_delivery_prompts(self) -> None:
        """get_delivery_prompts should return delivery-related prompts."""
        service = YOLOWorldService()

        with patch("backend.services.yolo_world_loader.get_delivery_prompts") as mock_get:
            mock_get.return_value = ["package", "box"]

            prompts = service.get_delivery_prompts()

            mock_get.assert_called_once()
            assert prompts == ["package", "box"]


class TestAIServicesImports:
    """Tests for AI service module exports."""

    def test_services_importable_from_package(self) -> None:
        """AI services should be importable from backend.services."""
        from backend.services import (
            FaceDetectorService,
            OCRService,
            PlateDetectorService,
            YOLOWorldService,
        )

        assert FaceDetectorService is not None
        assert PlateDetectorService is not None
        assert OCRService is not None
        assert YOLOWorldService is not None

    def test_services_in_all(self) -> None:
        """AI services should be in __all__."""
        from backend.services import __all__

        assert "FaceDetectorService" in __all__
        assert "PlateDetectorService" in __all__
        assert "OCRService" in __all__
        assert "YOLOWorldService" in __all__
