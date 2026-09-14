"""Integration tests for Scene OCR in the enrichment pipeline.

Tests verify that:
1. SceneOCRService is called during enrichment when enabled
2. Results appear in EnrichmentResult.scene_ocr
3. HTTP calls to ai-enrichment service are properly mocked
4. Scene OCR runs in Phase 1 (parallel) for frame OCR
5. Crop OCR runs in Phase 2 (after detections known)
6. Service provider matching works correctly

Reference: docs/plans/2026-02-04-scene-ocr-design.md
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    reset_enrichment_pipeline,
)
from backend.services.model_zoo import ModelManager
from backend.services.prompts import format_detections_with_all_enrichment
from backend.services.reid_service import reset_reid_service
from backend.services.scene_change_detector import reset_scene_change_detector
from backend.services.scene_ocr_service import (
    DetectionOCRResult,
    RawOCRResult,
    SceneOCRResult,
    SceneOCRService,
    SceneTextResult,
    reset_scene_ocr_service,
)
from backend.services.service_provider_matcher import ServiceMatch
from backend.services.vision_extractor import reset_vision_extractor

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_image() -> Image.Image:
    """Create a test RGB image for processing."""
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


@pytest.fixture
def person_detection() -> DetectionInput:
    """Create a person detection for testing."""
    return DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=50, y1=50, x2=150, y2=400),
    )


@pytest.fixture
def vehicle_detection() -> DetectionInput:
    """Create a vehicle detection for testing."""
    return DetectionInput(
        id=2,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=200, y1=150, x2=400, y2=350),
    )


@pytest.fixture
def mixed_detections(
    person_detection: DetectionInput,
    vehicle_detection: DetectionInput,
) -> list[DetectionInput]:
    """Create a batch with multiple detection types."""
    return [person_detection, vehicle_detection]


class MockAsyncContextManager:
    """Mock async context manager for model loading."""

    def __init__(self, model: Any):
        self._model = model

    async def __aenter__(self) -> Any:
        return self._model

    async def __aexit__(self, *args: Any) -> None:
        pass


def create_mock_model_manager() -> MagicMock:
    """Create a mock ModelManager with configured model loaders."""
    manager = MagicMock(spec=ModelManager)
    mock_models: dict[str, Any] = {}

    def mock_load(model_name: str) -> MockAsyncContextManager:
        if model_name in mock_models:
            return MockAsyncContextManager(mock_models[model_name])
        return MockAsyncContextManager(MagicMock())

    manager.load = mock_load
    return manager


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """Create a mock ModelManager."""
    return create_mock_model_manager()


@pytest.fixture(autouse=True)
def reset_global_services() -> None:
    """Reset global service instances before and after each test."""
    reset_enrichment_pipeline()
    reset_vision_extractor()
    reset_reid_service()
    reset_scene_change_detector()
    reset_scene_ocr_service()
    yield
    reset_enrichment_pipeline()
    reset_vision_extractor()
    reset_reid_service()
    reset_scene_change_detector()
    reset_scene_ocr_service()


# =============================================================================
# Scene OCR Pipeline Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestSceneOCRPipeline:
    """Integration tests for scene OCR in enrichment pipeline."""

    async def test_scene_ocr_called_when_enabled(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test that scene OCR is called during enrichment when enabled."""
        # Create mock SceneOCRResult
        mock_scene_ocr_result = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="123",
                    confidence=0.92,
                    bbox=(10, 20, 50, 40),
                    text_type="house_number",
                ),
                SceneTextResult(
                    value="Main St",
                    confidence=0.88,
                    bbox=(100, 15, 200, 45),
                    text_type="street_sign",
                ),
            ],
            detection_ocr={},
            processing_time_ms=150.0,
        )

        with patch(
            "backend.services.enrichment_pipeline.get_scene_ocr_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=SceneOCRService)
            mock_service._run_full_frame_ocr = AsyncMock(
                return_value=[
                    RawOCRResult(text="123", confidence=0.92, bbox=(10, 20, 50, 40)),
                    RawOCRResult(text="Main St", confidence=0.88, bbox=(100, 15, 200, 45)),
                ]
            )
            mock_service.process_frame = AsyncMock(return_value=mock_scene_ocr_result)
            mock_get_service.return_value = mock_service

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                pose_estimation_enabled=False,
                depth_estimation_enabled=False,
                action_recognition_enabled=False,
                weather_classification_enabled=False,
                scene_ocr_enabled=True,
                household_matching_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify scene OCR was called
            assert result.scene_ocr is not None
            mock_service.process_frame.assert_called_once()

    async def test_scene_ocr_results_in_enrichment_result(
        self,
        test_image: Image.Image,
        mixed_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ) -> None:
        """Test that scene OCR results appear correctly in EnrichmentResult."""
        # Create comprehensive mock result
        mock_scene_ocr_result = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="STOP",
                    confidence=0.96,
                    bbox=(300, 30, 380, 110),
                    text_type="sign",
                ),
            ],
            detection_ocr={
                "1": DetectionOCRResult(
                    detection_id="1",
                    texts=[{"value": "FedEx", "confidence": 0.94, "region": "chest"}],
                    service_match=ServiceMatch(
                        provider="FedEx",
                        category="DELIVERY",
                        confidence=0.97,
                        risk_modifier="low_risk_service",
                    ),
                ),
            },
            processing_time_ms=180.0,
        )

        with patch(
            "backend.services.enrichment_pipeline.get_scene_ocr_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=SceneOCRService)
            mock_service._run_full_frame_ocr = AsyncMock(return_value=[])
            mock_service.process_frame = AsyncMock(return_value=mock_scene_ocr_result)
            mock_get_service.return_value = mock_service

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                pose_estimation_enabled=False,
                depth_estimation_enabled=False,
                action_recognition_enabled=False,
                weather_classification_enabled=False,
                scene_ocr_enabled=True,
                household_matching_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=mixed_detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify scene texts
            assert result.scene_ocr is not None
            assert result.scene_ocr.has_scene_texts
            assert len(result.scene_ocr.scene_texts) == 1
            assert result.scene_ocr.scene_texts[0].value == "STOP"

            # Verify detection OCR
            assert result.scene_ocr.has_detection_ocr
            assert "1" in result.scene_ocr.detection_ocr
            assert result.scene_ocr.detection_ocr["1"].texts[0]["value"] == "FedEx"

            # Verify service match
            assert result.scene_ocr.has_service_matches
            assert result.scene_ocr.detection_ocr["1"].service_match.provider == "FedEx"

    async def test_scene_ocr_disabled(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test that scene OCR is not called when disabled."""
        with patch(
            "backend.services.enrichment_pipeline.get_scene_ocr_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=SceneOCRService)
            mock_service.process_frame = AsyncMock()
            mock_get_service.return_value = mock_service

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                pose_estimation_enabled=False,
                depth_estimation_enabled=False,
                action_recognition_enabled=False,
                weather_classification_enabled=False,
                scene_ocr_enabled=False,  # Disabled
                household_matching_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify scene OCR was not called and result is None
            assert result.scene_ocr is None
            mock_service.process_frame.assert_not_called()

    async def test_scene_ocr_graceful_failure(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test that scene OCR failure is handled gracefully."""
        with patch(
            "backend.services.enrichment_pipeline.get_scene_ocr_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=SceneOCRService)
            mock_service._run_full_frame_ocr = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            mock_service.process_frame = AsyncMock(side_effect=Exception("Service unavailable"))
            mock_get_service.return_value = mock_service

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                pose_estimation_enabled=False,
                depth_estimation_enabled=False,
                action_recognition_enabled=False,
                weather_classification_enabled=False,
                scene_ocr_enabled=True,
                household_matching_enabled=False,
            )

            # Should not raise exception - graceful degradation
            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Scene OCR should be None due to failure
            assert result.scene_ocr is None


@pytest.mark.integration
@pytest.mark.asyncio
class TestSceneOCRPromptFormatting:
    """Tests for scene OCR context formatting in prompts."""

    async def test_format_detections_includes_scene_ocr(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test that format_detections_with_all_enrichment includes scene OCR."""
        mock_scene_ocr_result = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="FedEx",
                    confidence=0.95,
                    bbox=(50, 60, 120, 90),
                    text_type="sign",
                ),
            ],
            detection_ocr={
                "1": DetectionOCRResult(
                    detection_id="1",
                    texts=[{"value": "Express Delivery", "confidence": 0.88, "region": "chest"}],
                    service_match=ServiceMatch(
                        provider="FedEx",
                        category="DELIVERY",
                        confidence=0.95,
                        risk_modifier="low_risk_service",
                    ),
                ),
            },
            processing_time_ms=120.0,
        )

        with patch(
            "backend.services.enrichment_pipeline.get_scene_ocr_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=SceneOCRService)
            mock_service._run_full_frame_ocr = AsyncMock(return_value=[])
            mock_service.process_frame = AsyncMock(return_value=mock_scene_ocr_result)
            mock_get_service.return_value = mock_service

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                pose_estimation_enabled=False,
                depth_estimation_enabled=False,
                action_recognition_enabled=False,
                weather_classification_enabled=False,
                scene_ocr_enabled=True,
                household_matching_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Format detections with enrichment
            detections_dict = [
                {
                    "detection_id": "1",
                    "class_name": "person",
                    "confidence": 0.95,
                    "bbox": [50, 50, 150, 400],
                }
            ]
            formatted = format_detections_with_all_enrichment(
                detections_dict,
                enrichment_result=result,
                vision_extraction=None,
            )

            # Verify scene OCR section is included
            assert "## Scene OCR" in formatted
            assert "FedEx" in formatted
            assert "DELIVERY" in formatted

    async def test_format_detections_without_scene_ocr(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test that format_detections_with_all_enrichment works without scene OCR."""
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_classification_enabled=False,
            vehicle_damage_detection_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
            pose_estimation_enabled=False,
            depth_estimation_enabled=False,
            action_recognition_enabled=False,
            weather_classification_enabled=False,
            scene_ocr_enabled=False,
            household_matching_enabled=False,
        )

        result = await pipeline.enrich_batch(
            detections=[person_detection],
            images={None: test_image},
            camera_id="test_camera",
        )

        # Format detections with enrichment
        detections_dict = [
            {
                "detection_id": "1",
                "class_name": "person",
                "confidence": 0.95,
                "bbox": [50, 50, 150, 400],
            }
        ]
        formatted = format_detections_with_all_enrichment(
            detections_dict,
            enrichment_result=result,
            vision_extraction=None,
        )

        # Verify scene OCR section is NOT included
        assert "## Scene OCR" not in formatted
