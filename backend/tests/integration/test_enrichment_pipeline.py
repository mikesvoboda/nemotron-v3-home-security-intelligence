"""Integration tests for EnrichmentPipeline service orchestration.

Tests the enrichment pipeline's orchestration logic with mocked external AI services.
Since AI services run in separate containers (Florence, CLIP, etc.), integration tests
mock the HTTP clients and verify correct service calls are made for different detection types.

Tests cover:
- Detection type routing (vehicle -> vehicle classifier, person -> CLIP)
- Florence caption generation for all detection types
- Error handling when services return errors
- Timeout handling
- Batch processing with mixed detection types
- Graceful degradation when services are unavailable
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
    EnrichmentResult,
    reset_enrichment_pipeline,
)
from backend.services.fashion_clip_loader import ClothingClassification
from backend.services.image_quality_loader import ImageQualityResult
from backend.services.model_zoo import ModelManager
from backend.services.pet_classifier_loader import PetClassificationResult
from backend.services.reid_service import reset_reid_service
from backend.services.scene_change_detector import reset_scene_change_detector
from backend.services.vehicle_classifier_loader import VehicleClassificationResult
from backend.services.vehicle_damage_loader import DamageDetection, VehicleDamageResult
from backend.services.violence_loader import ViolenceDetectionResult
from backend.services.vision_extractor import (
    BatchExtractionResult,
    EnvironmentContext,
    PersonAttributes,
    SceneAnalysis,
    VehicleAttributes,
    reset_vision_extractor,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_image() -> Image.Image:
    """Create a test RGB image for processing."""
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


@pytest.fixture
def vehicle_detection() -> DetectionInput:
    """Create a vehicle detection for testing."""
    return DetectionInput(
        id=1,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=100, y1=150, x2=300, y2=350),
    )


@pytest.fixture
def person_detection() -> DetectionInput:
    """Create a person detection for testing."""
    return DetectionInput(
        id=2,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=50, y1=50, x2=150, y2=400),
    )


@pytest.fixture
def pet_detection() -> DetectionInput:
    """Create a pet (dog) detection for testing."""
    return DetectionInput(
        id=3,
        class_name="dog",
        confidence=0.88,
        bbox=BoundingBox(x1=200, y1=300, x2=280, y2=400),
    )


@pytest.fixture
def cat_detection() -> DetectionInput:
    """Create a cat detection for testing."""
    return DetectionInput(
        id=4,
        class_name="cat",
        confidence=0.91,
        bbox=BoundingBox(x1=350, y1=320, x2=420, y2=380),
    )


@pytest.fixture
def mixed_detections(
    vehicle_detection: DetectionInput,
    person_detection: DetectionInput,
    pet_detection: DetectionInput,
) -> list[DetectionInput]:
    """Create a batch with multiple detection types."""
    return [vehicle_detection, person_detection, pet_detection]


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

    # Mock model data for each model type
    mock_models: dict[str, Any] = {
        "florence-2-large": {"model": MagicMock(), "processor": MagicMock()},
        "clip-vit-l": {"model": MagicMock(), "processor": MagicMock()},
        "fashion-clip": {"model": MagicMock(), "processor": MagicMock()},
        "vehicle-segment-classification": {
            "model": MagicMock(),
            "transform": MagicMock(),
            "classes": ["car", "truck", "pickup_truck", "work_van"],
        },
        "vehicle-damage-detection": MagicMock(),
        "pet-classifier": {"model": MagicMock(), "processor": MagicMock()},
        "brisque-quality": MagicMock(),
        "violence-detection": {"model": MagicMock(), "processor": MagicMock()},
        "segformer-b2-clothes": (MagicMock(), MagicMock()),
        "yolo11-license-plate": MagicMock(),
        "yolo11-face": MagicMock(),
        "paddleocr": MagicMock(),
    }

    def mock_load(model_name: str) -> MockAsyncContextManager:
        if model_name in mock_models:
            return MockAsyncContextManager(mock_models[model_name])
        raise KeyError(f"Unknown model: {model_name}")

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
    yield
    reset_enrichment_pipeline()
    reset_vision_extractor()
    reset_reid_service()
    reset_scene_change_detector()


# =============================================================================
# Vehicle Enrichment Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestVehicleEnrichment:
    """Integration tests for vehicle detection enrichment."""

    async def test_vehicle_enrichment_calls_florence_and_classifier(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vehicle detection triggers Florence caption + vehicle classifier."""
        # Mock vision extractor to return vehicle attributes
        mock_vision_result = BatchExtractionResult(
            vehicle_attributes={
                "1": VehicleAttributes(
                    color="silver",
                    vehicle_type="sedan",
                    is_commercial=False,
                    commercial_text=None,
                    caption="A silver sedan parked on the street",
                )
            },
            person_attributes={},
            scene_analysis=SceneAnalysis(scene_description="Suburban street"),
            environment_context=EnvironmentContext(
                time_of_day="day", artificial_light=False, weather="clear"
            ),
        )

        mock_vehicle_classification = VehicleClassificationResult(
            vehicle_type="car",
            confidence=0.89,
            display_name="car/sedan",
            is_commercial=False,
            all_scores={"car": 0.89, "pickup_truck": 0.08, "work_van": 0.03},
        )

        with (
            patch(
                "backend.services.enrichment_pipeline.get_vision_extractor"
            ) as mock_get_extractor,
            patch(
                "backend.services.enrichment_pipeline.classify_vehicle",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_batch_attributes = AsyncMock(return_value=mock_vision_result)
            mock_get_extractor.return_value = mock_extractor
            mock_classify.return_value = mock_vehicle_classification

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify vision extraction was called
            assert result.has_vision_extraction
            assert "1" in result.vision_extraction.vehicle_attributes
            assert result.vision_extraction.vehicle_attributes["1"].color == "silver"

            # Verify vehicle classifier was called
            mock_classify.assert_called_once()
            assert "1" in result.vehicle_classifications
            assert result.vehicle_classifications["1"].vehicle_type == "car"

    async def test_vehicle_damage_detection_runs_on_vehicles(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vehicle damage detection runs for vehicle detections."""
        # VehicleDamageResult only takes detections parameter, other fields are properties
        mock_damage_result = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="scratch",
                    confidence=0.85,
                    bbox=(100.0, 150.0, 200.0, 180.0),
                ),
                DamageDetection(
                    damage_type="dent",
                    confidence=0.72,
                    bbox=(220.0, 160.0, 280.0, 200.0),
                ),
            ]
        )

        with patch(
            "backend.services.enrichment_pipeline.detect_vehicle_damage",
            new_callable=AsyncMock,
        ) as mock_detect_damage:
            mock_detect_damage.return_value = mock_damage_result

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
                vehicle_damage_detection_enabled=True,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify damage detection was called
            mock_detect_damage.assert_called_once()
            assert "1" in result.vehicle_damage
            assert result.vehicle_damage["1"].has_damage is True
            assert "scratch" in result.vehicle_damage["1"].damage_types


# =============================================================================
# Person Enrichment Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestPersonEnrichment:
    """Integration tests for person detection enrichment."""

    async def test_person_enrichment_calls_florence_and_reid(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test person detection triggers Florence caption + CLIP re-id."""
        mock_vision_result = BatchExtractionResult(
            vehicle_attributes={},
            person_attributes={
                "2": PersonAttributes(
                    clothing="dark jacket, jeans",
                    carrying="backpack",
                    is_service_worker=False,
                    action="walking",
                    caption="Person in dark clothing walking with backpack",
                )
            },
            scene_analysis=SceneAnalysis(scene_description="Front porch area"),
            environment_context=EnvironmentContext(
                time_of_day="night", artificial_light=True, weather=None
            ),
        )

        # Mock embedding and redis client
        test_embedding = [0.1] * 768  # Normalized CLIP embedding
        mock_redis = AsyncMock()

        with (
            patch(
                "backend.services.enrichment_pipeline.get_vision_extractor"
            ) as mock_get_extractor,
            patch("backend.services.enrichment_pipeline.get_reid_service") as mock_get_reid,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_batch_attributes = AsyncMock(return_value=mock_vision_result)
            mock_get_extractor.return_value = mock_extractor

            mock_reid_service = MagicMock()
            mock_reid_service.generate_embedding = AsyncMock(return_value=test_embedding)
            mock_reid_service.find_matching_entities = AsyncMock(return_value=[])
            mock_reid_service.store_embedding = AsyncMock()
            mock_get_reid.return_value = mock_reid_service

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=True,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                redis_client=mock_redis,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify vision extraction ran
            assert result.has_vision_extraction
            assert "2" in result.vision_extraction.person_attributes

            # Verify re-id service was called
            mock_reid_service.generate_embedding.assert_called()
            mock_reid_service.store_embedding.assert_called()

    async def test_clothing_classification_on_person(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test person with visible clothing triggers FashionCLIP."""
        mock_clothing = ClothingClassification(
            top_category="person wearing dark hoodie",
            confidence=0.82,
            all_scores={
                "person wearing dark hoodie": 0.82,
                "casual clothing": 0.10,
                "person wearing gloves": 0.05,
            },
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Alert: dark hoodie",
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_clothing",
            new_callable=AsyncMock,
        ) as mock_classify:
            mock_classify.return_value = mock_clothing

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify clothing classification was called
            mock_classify.assert_called_once()
            assert result.has_clothing_classifications
            assert "2" in result.clothing_classifications
            assert result.clothing_classifications["2"].is_suspicious is True

    async def test_violence_detection_with_two_persons(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test violence detection triggers when 2+ persons are detected."""
        two_persons = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.95,
                bbox=BoundingBox(x1=50, y1=50, x2=150, y2=400),
            ),
            DetectionInput(
                id=2,
                class_name="person",
                confidence=0.92,
                bbox=BoundingBox(x1=250, y1=60, x2=350, y2=420),
            ),
        ]

        # ViolenceDetectionResult takes is_violent, confidence, violent_score, non_violent_score
        mock_violence_result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.85,
            violent_score=0.15,
            non_violent_score=0.85,
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_violence",
            new_callable=AsyncMock,
        ) as mock_classify:
            mock_classify.return_value = mock_violence_result

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=True,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=two_persons,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Violence detection should be called with 2+ persons
            mock_classify.assert_called_once()
            assert result.violence_detection is not None
            assert result.violence_detection.is_violent is False


# =============================================================================
# Pet Enrichment Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetEnrichment:
    """Integration tests for pet detection enrichment."""

    async def test_pet_enrichment_calls_pet_classifier(
        self,
        test_image: Image.Image,
        pet_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pet detection triggers pet classifier."""
        mock_pet_result = PetClassificationResult(
            animal_type="dog",
            confidence=0.94,
            cat_score=0.06,
            dog_score=0.94,
            is_household_pet=True,
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_pet",
            new_callable=AsyncMock,
        ) as mock_classify:
            mock_classify.return_value = mock_pet_result

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
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=[pet_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify pet classifier was called
            mock_classify.assert_called_once()
            assert result.has_pet_classifications
            assert "3" in result.pet_classifications
            assert result.pet_classifications["3"].animal_type == "dog"

    async def test_cat_classification(
        self,
        test_image: Image.Image,
        cat_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test cat detection is correctly classified."""
        mock_cat_result = PetClassificationResult(
            animal_type="cat",
            confidence=0.96,
            cat_score=0.96,
            dog_score=0.04,
            is_household_pet=True,
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_pet",
            new_callable=AsyncMock,
        ) as mock_classify:
            mock_classify.return_value = mock_cat_result

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
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=[cat_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.pet_classifications["4"].animal_type == "cat"
            assert result.pet_classifications["4"].confidence > 0.9


# =============================================================================
# Mixed Detection Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestMixedDetections:
    """Integration tests for batches with multiple detection types."""

    async def test_mixed_detections_enriched_correctly(
        self,
        test_image: Image.Image,
        mixed_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ) -> None:
        """Test batch with multiple detection types routes correctly."""
        # Setup mock returns for each detection type
        mock_vision_result = BatchExtractionResult(
            vehicle_attributes={
                "1": VehicleAttributes(
                    color="blue",
                    vehicle_type="car",
                    is_commercial=False,
                    commercial_text=None,
                    caption="Blue car",
                )
            },
            person_attributes={
                "2": PersonAttributes(
                    clothing="white shirt",
                    carrying=None,
                    is_service_worker=False,
                    action="standing",
                    caption="Person standing",
                )
            },
            scene_analysis=SceneAnalysis(),
            environment_context=EnvironmentContext(
                time_of_day="day", artificial_light=False, weather="sunny"
            ),
        )

        mock_vehicle_class = VehicleClassificationResult(
            vehicle_type="car",
            confidence=0.88,
            display_name="car/sedan",
            is_commercial=False,
            all_scores={"car": 0.88},
        )

        mock_clothing = ClothingClassification(
            top_category="casual clothing",
            confidence=0.75,
            all_scores={"casual clothing": 0.75},
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="Casual clothing",
        )

        mock_pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.92,
            cat_score=0.08,
            dog_score=0.92,
            is_household_pet=True,
        )

        with (
            patch(
                "backend.services.enrichment_pipeline.get_vision_extractor"
            ) as mock_get_extractor,
            patch(
                "backend.services.enrichment_pipeline.classify_vehicle",
                new_callable=AsyncMock,
            ) as mock_classify_vehicle,
            patch(
                "backend.services.enrichment_pipeline.classify_clothing",
                new_callable=AsyncMock,
            ) as mock_classify_clothing,
            patch(
                "backend.services.enrichment_pipeline.classify_pet",
                new_callable=AsyncMock,
            ) as mock_classify_pet,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_batch_attributes = AsyncMock(return_value=mock_vision_result)
            mock_get_extractor.return_value = mock_extractor

            mock_classify_vehicle.return_value = mock_vehicle_class
            mock_classify_clothing.return_value = mock_clothing
            mock_classify_pet.return_value = mock_pet

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=mixed_detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify all classifiers were called
            mock_classify_vehicle.assert_called_once()  # 1 vehicle
            mock_classify_clothing.assert_called_once()  # 1 person
            mock_classify_pet.assert_called_once()  # 1 pet

            # Verify results contain all types
            assert result.has_vision_extraction
            assert len(result.vehicle_classifications) == 1
            assert len(result.clothing_classifications) == 1
            assert len(result.pet_classifications) == 1


# =============================================================================
# Error Handling and Graceful Degradation Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorHandling:
    """Integration tests for error handling and graceful degradation."""

    async def test_service_unavailable_graceful_degradation(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pipeline continues when a service is unavailable.

        Note: The enrichment pipeline catches exceptions at the individual detection
        level and logs warnings without adding to the result.errors list. This test
        verifies the pipeline completes gracefully and returns empty results for
        the failing service.
        """
        with (
            patch(
                "backend.services.enrichment_pipeline.classify_vehicle",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            # Simulate service unavailable (KeyError from model manager)
            mock_classify.side_effect = KeyError(
                "vehicle-segment-classification model not available"
            )

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
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Pipeline should complete despite the error
            assert isinstance(result, EnrichmentResult)
            # Service failure should result in empty classifications (graceful degradation)
            assert len(result.vehicle_classifications) == 0
            # Processing should complete
            assert result.processing_time_ms >= 0

    async def test_timeout_handling(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pipeline handles service timeouts gracefully.

        Note: The enrichment pipeline catches timeout exceptions at the individual
        detection level and logs warnings without adding to result.errors. This
        test verifies the pipeline continues and returns empty results for the
        timed-out service.
        """
        with patch(
            "backend.services.enrichment_pipeline.classify_clothing",
            new_callable=AsyncMock,
        ) as mock_classify:
            mock_classify.side_effect = TimeoutError("Request timed out")

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            # Pipeline should complete despite timeout
            assert isinstance(result, EnrichmentResult)
            # No clothing classifications due to timeout
            assert len(result.clothing_classifications) == 0
            # Processing completes (graceful degradation)
            assert result.processing_time_ms >= 0

    async def test_multiple_service_failures(
        self,
        test_image: Image.Image,
        mixed_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pipeline handles multiple service failures gracefully."""
        with (
            patch(
                "backend.services.enrichment_pipeline.get_vision_extractor"
            ) as mock_get_extractor,
            patch(
                "backend.services.enrichment_pipeline.classify_vehicle",
                new_callable=AsyncMock,
            ) as mock_vehicle,
            patch(
                "backend.services.enrichment_pipeline.classify_clothing",
                new_callable=AsyncMock,
            ) as mock_clothing,
            patch(
                "backend.services.enrichment_pipeline.classify_pet",
                new_callable=AsyncMock,
            ) as mock_pet,
        ):
            # All services fail
            mock_extractor = MagicMock()
            mock_extractor.extract_batch_attributes = AsyncMock(
                side_effect=RuntimeError("Florence service down")
            )
            mock_get_extractor.return_value = mock_extractor
            mock_vehicle.side_effect = RuntimeError("Vehicle classifier failed")
            mock_clothing.side_effect = RuntimeError("FashionCLIP failed")
            mock_pet.side_effect = RuntimeError("Pet classifier failed")

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=mixed_detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Pipeline should still complete
            assert isinstance(result, EnrichmentResult)
            # Multiple errors should be recorded
            assert len(result.errors) >= 1
            # Processing time should still be tracked
            assert result.processing_time_ms >= 0


# =============================================================================
# Empty and Edge Case Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestEdgeCases:
    """Integration tests for edge cases."""

    async def test_empty_detections_returns_empty_enrichment(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test no detections results in empty enrichment."""
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=True,
            face_detection_enabled=True,
            vision_extraction_enabled=True,
            reid_enabled=True,
            scene_change_enabled=True,
            violence_detection_enabled=True,
            clothing_classification_enabled=True,
            clothing_segmentation_enabled=True,
            vehicle_classification_enabled=True,
            vehicle_damage_detection_enabled=True,
            image_quality_enabled=True,
            pet_classification_enabled=True,
        )

        result = await pipeline.enrich_batch(
            detections=[],
            images={None: test_image},
            camera_id="test_camera",
        )

        # Should return empty result
        assert not result.has_vision_extraction
        assert not result.has_license_plates
        assert not result.has_faces
        assert not result.has_reid_matches
        assert len(result.vehicle_classifications) == 0
        assert len(result.clothing_classifications) == 0
        assert len(result.pet_classifications) == 0
        assert len(result.errors) == 0

    async def test_low_confidence_detections_filtered(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test low confidence detections are filtered out."""
        low_conf_detections = [
            DetectionInput(
                id=1,
                class_name="car",
                confidence=0.3,  # Below default threshold of 0.5
                bbox=BoundingBox(x1=100, y1=100, x2=200, y2=200),
            ),
            DetectionInput(
                id=2,
                class_name="person",
                confidence=0.2,  # Below threshold
                bbox=BoundingBox(x1=250, y1=100, x2=350, y2=400),
            ),
        ]

        with patch(
            "backend.services.enrichment_pipeline.classify_vehicle",
            new_callable=AsyncMock,
        ) as mock_vehicle:
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                min_confidence=0.5,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=low_conf_detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Vehicle classifier should not be called (filtered by confidence)
            mock_vehicle.assert_not_called()
            assert len(result.vehicle_classifications) == 0

    async def test_no_shared_image_skips_extractors(
        self,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pipeline handles missing shared image."""
        with patch(
            "backend.services.enrichment_pipeline.classify_vehicle",
            new_callable=AsyncMock,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            # Empty images dict
            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={},
                camera_id="test_camera",
            )

            # Should complete but skip image-dependent operations
            assert isinstance(result, EnrichmentResult)
            # Vehicle classifier still tries to run but will skip without image
            # The classifier won't be called because cropping requires image


# =============================================================================
# Context String and Result Formatting Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestResultFormatting:
    """Integration tests for result formatting and context string generation."""

    async def test_context_string_includes_all_enrichments(
        self,
        test_image: Image.Image,
        mixed_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ) -> None:
        """Test context string includes all enrichment data."""
        mock_vision_result = BatchExtractionResult(
            vehicle_attributes={
                "1": VehicleAttributes(
                    color="red",
                    vehicle_type="pickup",
                    is_commercial=False,
                    commercial_text=None,
                    caption="Red pickup truck",
                )
            },
            person_attributes={
                "2": PersonAttributes(
                    clothing="blue uniform",
                    carrying="clipboard",
                    is_service_worker=True,
                    action="walking",
                    caption="Service worker with clipboard",
                )
            },
            scene_analysis=SceneAnalysis(scene_description="Residential area"),
        )

        mock_clothing = ClothingClassification(
            top_category="high-visibility vest or safety vest",
            confidence=0.88,
            all_scores={"high-visibility vest or safety vest": 0.88},
            is_suspicious=False,
            is_service_uniform=True,
            raw_description="Service worker: high-visibility vest",
        )

        mock_pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.95,
            cat_score=0.05,
            dog_score=0.95,
            is_household_pet=True,
        )

        with (
            patch(
                "backend.services.enrichment_pipeline.get_vision_extractor"
            ) as mock_get_extractor,
            patch(
                "backend.services.enrichment_pipeline.classify_clothing",
                new_callable=AsyncMock,
            ) as mock_classify_clothing,
            patch(
                "backend.services.enrichment_pipeline.classify_pet",
                new_callable=AsyncMock,
            ) as mock_classify_pet,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_batch_attributes = AsyncMock(return_value=mock_vision_result)
            mock_get_extractor.return_value = mock_extractor
            mock_classify_clothing.return_value = mock_clothing
            mock_classify_pet.return_value = mock_pet

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=mixed_detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Generate context string
            context = result.to_context_string()

            # Should contain clothing classification section
            assert "Clothing" in context or "clothing" in context.lower()
            # Should contain pet classification section
            assert "Pet" in context or "Animal" in context


# =============================================================================
# EnrichmentResult Synchronous Tests
# =============================================================================


@pytest.mark.integration
class TestEnrichmentResultSync:
    """Synchronous tests for EnrichmentResult formatting and serialization."""

    def test_enrichment_result_to_dict(self) -> None:
        """Test EnrichmentResult.to_dict() serialization."""
        result = EnrichmentResult(
            license_plates=[],
            faces=[],
            vehicle_classifications={
                "1": VehicleClassificationResult(
                    vehicle_type="pickup_truck",
                    confidence=0.87,
                    display_name="pickup truck",
                    is_commercial=False,
                    all_scores={"pickup_truck": 0.87},
                )
            },
            clothing_classifications={
                "2": ClothingClassification(
                    top_category="casual clothing",
                    confidence=0.72,
                    all_scores={"casual clothing": 0.72},
                    is_suspicious=False,
                    is_service_uniform=False,
                    raw_description="Casual clothing",
                )
            },
            pet_classifications={
                "3": PetClassificationResult(
                    animal_type="dog",
                    confidence=0.91,
                    cat_score=0.09,
                    dog_score=0.91,
                    is_household_pet=True,
                )
            },
            errors=[],
            processing_time_ms=150.5,
        )

        result_dict = result.to_dict()

        assert "license_plates" in result_dict
        assert "faces" in result_dict
        assert "vehicle_classifications" in result_dict
        assert "errors" in result_dict
        assert result_dict["processing_time_ms"] == 150.5

    def test_risk_modifiers_calculation(self) -> None:
        """Test risk modifier calculation from enrichment results."""
        # Create result with suspicious clothing
        result_suspicious = EnrichmentResult(
            clothing_classifications={
                "1": ClothingClassification(
                    top_category="person wearing ski mask or balaclava",
                    confidence=0.9,
                    all_scores={},
                    is_suspicious=True,
                    is_service_uniform=False,
                    raw_description="Alert: ski mask or balaclava",
                )
            }
        )

        modifiers = result_suspicious.get_risk_modifiers()
        assert "suspicious_attire" in modifiers
        assert modifiers["suspicious_attire"] > 0  # Increases risk

        # Create result with service uniform
        result_service = EnrichmentResult(
            clothing_classifications={
                "1": ClothingClassification(
                    top_category="Amazon delivery vest",
                    confidence=0.85,
                    all_scores={},
                    is_suspicious=False,
                    is_service_uniform=True,
                    raw_description="Service worker: Amazon delivery vest",
                )
            }
        )

        modifiers = result_service.get_risk_modifiers()
        assert "service_uniform" in modifiers
        assert modifiers["service_uniform"] < 0  # Decreases risk


# =============================================================================
# Image Quality Assessment Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestImageQualityAssessment:
    """Integration tests for image quality assessment."""

    async def test_image_quality_assessment_runs(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test image quality assessment runs on images."""
        # ImageQualityResult takes quality_score, brisque_score, is_blurry, is_noisy, is_low_quality
        # is_good_quality is a computed property
        mock_quality = ImageQualityResult(
            quality_score=42.5,
            brisque_score=25.0,  # Lower brisque = better quality
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )

        with patch(
            "backend.services.enrichment_pipeline.assess_image_quality",
            new_callable=AsyncMock,
        ) as mock_assess:
            mock_assess.return_value = mock_quality

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
                image_quality_enabled=True,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            mock_assess.assert_called_once()
            assert result.has_image_quality
            assert result.image_quality.quality_score == 42.5
            assert result.image_quality.is_good_quality is True
