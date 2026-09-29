"""Unit tests for AI service wrapper classes (NEM-2030).

This module tests the AI service wrappers that provide dependency injection
interfaces for face detection, plate detection, and OCR. R8 S2 removed
YOLOWorldService from this module — its loader was retired, so the wrapper
had nothing left to wrap and TestYOLOWorldService went with it.

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


class TestAIServicesImports:
    """Tests for AI service module exports."""

    def test_services_importable_from_package(self) -> None:
        """AI services should be importable from backend.services."""
        from backend.services import (
            FaceDetectorService,
            OCRService,
            PlateDetectorService,
        )

        assert FaceDetectorService is not None
        assert PlateDetectorService is not None
        assert OCRService is not None

    def test_services_in_all(self) -> None:
        """AI services should be in __all__, and the retired wrapper must not be."""
        from backend.services import __all__

        assert "FaceDetectorService" in __all__
        assert "PlateDetectorService" in __all__
        assert "OCRService" in __all__
        # R8 S2: the package must not re-export the deleted service
        # (test_r8_s2b_nemotron_deletion.py pins the same rule repo-wide).
        assert "YOLOWorldService" not in __all__
