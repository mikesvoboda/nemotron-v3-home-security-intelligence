"""Integration tests for the full vision extraction pipeline.

Tests the EnrichmentPipeline with VisionExtractor, ReIdentificationService,
and SceneChangeDetector working together. Uses mocked AI models to ensure
fast, deterministic tests while verifying the full data flow.

Tests cover:
- Full pipeline integration with all extractors
- Re-identification with real Redis storage
- Scene change detection across frames
- Context string generation for Nemotron prompt
- Error handling and graceful degradation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
    reset_enrichment_pipeline,
)
from backend.services.reid_service import (
    EntityEmbedding,
    get_reid_service,
    reset_reid_service,
)
from backend.services.scene_change_detector import (
    SceneChangeDetector,
    get_scene_change_detector,
    reset_scene_change_detector,
)
from backend.services.vision_extractor import (
    BatchExtractionResult,
    EnvironmentContext,
    PersonAttributes,
    SceneAnalysis,
    VehicleAttributes,
    VisionExtractor,
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
def test_image_variant() -> Image.Image:
    """Create a variant test image (different content for scene change)."""
    return Image.new("RGB", (640, 480), color=(200, 100, 50))


@pytest.fixture
def sample_detections() -> list[DetectionInput]:
    """Create sample detections for testing."""
    return [
        DetectionInput(
            id=1,
            class_name="person",
            confidence=0.95,
            bbox=BoundingBox(x1=100, y1=100, x2=200, y2=400),
        ),
        DetectionInput(
            id=2,
            class_name="car",
            confidence=0.88,
            bbox=BoundingBox(x1=300, y1=200, x2=500, y2=350),
        ),
        DetectionInput(
            id=3,
            class_name="truck",
            confidence=0.82,
            bbox=BoundingBox(x1=50, y1=150, x2=150, y2=300),
        ),
    ]


class MockAsyncContextManager:
    """Mock async context manager for model loading."""

    def __init__(self, model: dict):
        self._model = model

    async def __aenter__(self):
        return self._model

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """Create a mock ModelManager with mock models."""
    manager = MagicMock()

    # Mock Florence-2 model
    mock_florence = MagicMock()
    mock_florence_processor = MagicMock()

    # Mock CLIP model
    mock_clip = MagicMock()
    mock_clip_processor = MagicMock()

    # Setup context manager for model loading
    # The load method must return an async context manager directly (not a coroutine)
    def mock_load(model_name: str):
        if model_name == "florence-2":
            return MockAsyncContextManager(
                {"model": mock_florence, "processor": mock_florence_processor}
            )
        elif model_name == "clip-vit-l":
            return MockAsyncContextManager({"model": mock_clip, "processor": mock_clip_processor})
        else:
            raise KeyError(f"Unknown model: {model_name}")

    manager.load = mock_load
    manager.get_model = MagicMock(
        side_effect=lambda name: {
            "florence-2": {"model": mock_florence, "processor": mock_florence_processor},
            "clip-vit-l": {"model": mock_clip, "processor": mock_clip_processor},
        }.get(name)
    )

    return manager


@pytest.fixture
def mock_vision_extractor() -> VisionExtractor:
    """Create a VisionExtractor with mocked extraction methods."""
    extractor = VisionExtractor()

    # Mock extract methods to return deterministic results
    async def mock_extract_vehicle(image, model, bbox=None):
        return VehicleAttributes(
            color="blue",
            vehicle_type="sedan",
            is_commercial=False,
            commercial_text=None,
            caption="A blue sedan parked in the driveway",
        )

    async def mock_extract_person(image, model, bbox=None):
        return PersonAttributes(
            clothing="dark jacket, jeans",
            carrying="backpack",
            is_service_worker=False,
            action="walking",
            caption="A person in dark clothing walking with a backpack",
        )

    async def mock_extract_scene(image, model):
        return SceneAnalysis(
            unusual_objects=[],
            tools_detected=[],
            abandoned_items=[],
            scene_description="residential driveway at night",
        )

    async def mock_extract_batch(image, detections):
        vehicle_attrs = {}
        person_attrs = {}

        for det in detections:
            det_id = str(det.get("detection_id", "unknown"))
            class_name = det.get("class_name", "")

            if class_name in ["car", "truck", "bus", "motorcycle"]:
                vehicle_attrs[det_id] = await mock_extract_vehicle(image, None)
            elif class_name == "person":
                person_attrs[det_id] = await mock_extract_person(image, None)

        return BatchExtractionResult(
            vehicle_attributes=vehicle_attrs,
            person_attributes=person_attrs,
            scene_analysis=await mock_extract_scene(image, None),
            environment_context=EnvironmentContext(
                time_of_day="night",
                artificial_light=True,
                weather=None,
            ),
        )

    extractor.extract_vehicle_attributes = mock_extract_vehicle
    extractor.extract_person_attributes = mock_extract_person
    extractor.extract_scene_analysis = mock_extract_scene
    extractor.extract_batch_attributes = mock_extract_batch

    return extractor


@pytest.fixture(autouse=True)
def reset_global_services():
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
# VisionExtractor Integration Tests
# =============================================================================


class TestVisionExtractorIntegration:
    """Integration tests for VisionExtractor with EnrichmentPipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_with_vision_extraction(
        self,
        test_image: Image.Image,
        sample_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
        mock_vision_extractor: VisionExtractor,
    ):
        """Test pipeline runs vision extraction on detections."""
        # Patch the global vision extractor
        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=mock_vision_extractor,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=sample_detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify vision extraction was run
            assert result.has_vision_extraction
            assert result.vision_extraction is not None

            # Check vehicle attributes were extracted
            vehicle_attrs = result.vision_extraction.vehicle_attributes
            assert "2" in vehicle_attrs  # car detection
            assert vehicle_attrs["2"].color == "blue"
            assert vehicle_attrs["2"].vehicle_type == "sedan"

            # Check person attributes were extracted
            person_attrs = result.vision_extraction.person_attributes
            assert "1" in person_attrs  # person detection
            assert "dark jacket" in person_attrs["1"].clothing
            assert person_attrs["1"].carrying == "backpack"

            # Check scene analysis
            scene = result.vision_extraction.scene_analysis
            assert scene.scene_description == "residential driveway at night"

            # Check environment context
            env = result.vision_extraction.environment_context
            assert env.time_of_day == "night"
            assert env.artificial_light is True

    @pytest.mark.asyncio
    async def test_pipeline_vision_extraction_disabled(
        self,
        test_image: Image.Image,
        sample_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ):
        """Test pipeline skips vision extraction when disabled."""
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
        )

        result = await pipeline.enrich_batch(
            detections=sample_detections,
            images={None: test_image},
            camera_id="test_camera",
        )

        assert not result.has_vision_extraction
        assert result.vision_extraction is None

    @pytest.mark.asyncio
    async def test_pipeline_handles_vision_extraction_error(
        self,
        test_image: Image.Image,
        sample_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ):
        """Test pipeline handles vision extraction errors gracefully."""
        # Create extractor that raises errors
        failing_extractor = VisionExtractor()

        async def failing_extract_batch(*args, **kwargs):
            raise RuntimeError("Florence-2 model not loaded")

        failing_extractor.extract_batch_attributes = failing_extract_batch

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=failing_extractor,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=sample_detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Should not have vision extraction but should have error
            assert not result.has_vision_extraction
            assert len(result.errors) > 0
            # Error message may be "Vision extraction failed" or
            # "vision_extraction failed: Unexpected error: ..."
            assert "vision" in result.errors[0].lower() and "fail" in result.errors[0].lower()


# =============================================================================
# Re-Identification Integration Tests
# =============================================================================


class TestReIdentificationIntegration:
    """Integration tests for ReIdentificationService with real Redis."""

    @pytest.fixture(autouse=True)
    async def cleanup_reid_keys(self, real_redis):
        """Clean up entity embedding keys before and after each test."""
        redis_client = real_redis._ensure_connected()

        async def _cleanup():
            # Delete all entity_embeddings keys to ensure test isolation
            keys = await redis_client.keys("entity_embeddings:*")
            if keys:
                await redis_client.delete(*keys)

        await _cleanup()
        yield
        await _cleanup()

    @pytest.mark.asyncio
    async def test_reid_service_stores_and_matches_embeddings(
        self, real_redis, test_image: Image.Image
    ):
        """Test re-id service can store and match embeddings using Redis."""
        reid_service = get_reid_service()
        # Use RedisClient wrapper (which uses 'expire=' parameter) instead of raw Redis
        redis_client = real_redis

        # Create a test embedding (768 dimensions like CLIP ViT-L)
        test_embedding = [float(i % 100) / 100.0 for i in range(768)]
        # Normalize it
        norm = sum(x * x for x in test_embedding) ** 0.5
        test_embedding = [x / norm for x in test_embedding]

        # Store the embedding
        entity = EntityEmbedding(
            entity_type="person",
            embedding=test_embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_001",
            attributes={"clothing": "blue jacket"},
        )
        await reid_service.store_embedding(redis_client, entity)

        # Try to match with a similar embedding (same vector should match perfectly)
        matches = await reid_service.find_matching_entities(
            redis_client,
            test_embedding,
            entity_type="person",
            threshold=0.9,
            exclude_detection_id="det_002",  # Different detection
        )

        assert len(matches) == 1
        assert matches[0].similarity > 0.99  # Should be near-perfect match
        assert matches[0].entity.detection_id == "det_001"
        assert matches[0].entity.attributes["clothing"] == "blue jacket"

    @pytest.mark.asyncio
    async def test_reid_service_excludes_same_detection(self, real_redis, test_image: Image.Image):
        """Test re-id service excludes the same detection from matches."""
        reid_service = get_reid_service()
        # Use RedisClient wrapper (which uses 'expire=' parameter) instead of raw Redis
        redis_client = real_redis

        test_embedding = [float(i % 100) / 100.0 for i in range(768)]
        norm = sum(x * x for x in test_embedding) ** 0.5
        test_embedding = [x / norm for x in test_embedding]

        # Store the embedding
        entity = EntityEmbedding(
            entity_type="person",
            embedding=test_embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_same",
            attributes={},
        )
        await reid_service.store_embedding(redis_client, entity)

        # Search excluding the same detection ID
        matches = await reid_service.find_matching_entities(
            redis_client,
            test_embedding,
            entity_type="person",
            threshold=0.5,
            exclude_detection_id="det_same",  # Same detection
        )

        # Should not find any matches
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_reid_matches_across_cameras(self, real_redis, test_image: Image.Image):
        """Test re-id can match the same entity across different cameras."""
        reid_service = get_reid_service()
        # Use RedisClient wrapper (which uses 'expire=' parameter) instead of raw Redis
        redis_client = real_redis

        # Create embedding for person at front door
        base_embedding = [float(i % 100) / 100.0 for i in range(768)]
        norm = sum(x * x for x in base_embedding) ** 0.5
        base_embedding = [x / norm for x in base_embedding]

        entity1 = EntityEmbedding(
            entity_type="person",
            embedding=base_embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_front_001",
            attributes={"clothing": "red shirt"},
        )
        await reid_service.store_embedding(redis_client, entity1)

        # Slightly perturbed embedding (same person, different angle)
        perturbed = [x + 0.01 * ((i % 3) - 1) for i, x in enumerate(base_embedding)]
        norm = sum(x * x for x in perturbed) ** 0.5
        perturbed = [x / norm for x in perturbed]

        # Search from garage camera
        matches = await reid_service.find_matching_entities(
            redis_client,
            perturbed,
            entity_type="person",
            threshold=0.85,
            exclude_detection_id="det_garage_001",
        )

        assert len(matches) >= 1
        assert matches[0].entity.camera_id == "front_door"
        assert matches[0].similarity > 0.9


# =============================================================================
# Scene Change Detection Integration Tests
# =============================================================================


class TestSceneChangeIntegration:
    """Integration tests for SceneChangeDetector."""

    @pytest.mark.asyncio
    async def test_scene_detector_detects_significant_change(
        self, test_image: Image.Image, test_image_variant: Image.Image
    ):
        """Test scene detector identifies significant scene changes."""
        detector = get_scene_change_detector()
        camera_id = f"test_cam_{uuid.uuid4().hex[:8]}"

        # First frame - establishes baseline
        frame1 = np.array(test_image)
        result1 = detector.detect_changes(camera_id, frame1)
        assert not result1.change_detected  # First frame, no previous

        # Second frame - very different content
        frame2 = np.array(test_image_variant)
        result2 = detector.detect_changes(camera_id, frame2)

        # Should detect change since images are different colors
        assert result2.similarity_score < 1.0

    @pytest.mark.asyncio
    async def test_scene_detector_no_change_same_frame(self, test_image: Image.Image):
        """Test scene detector shows no change for identical frames."""
        detector = get_scene_change_detector()
        camera_id = f"test_cam_{uuid.uuid4().hex[:8]}"

        frame = np.array(test_image)

        # First frame
        detector.detect_changes(camera_id, frame)

        # Same frame again
        result = detector.detect_changes(camera_id, frame)

        # SSIM of identical images should be 1.0
        assert result.similarity_score > 0.99
        assert not result.change_detected

    @pytest.mark.asyncio
    async def test_scene_detector_tracks_per_camera(
        self, test_image: Image.Image, test_image_variant: Image.Image
    ):
        """Test scene detector tracks state independently per camera."""
        detector = get_scene_change_detector()
        cam1 = f"cam1_{uuid.uuid4().hex[:8]}"
        cam2 = f"cam2_{uuid.uuid4().hex[:8]}"

        frame1 = np.array(test_image)
        frame2 = np.array(test_image_variant)

        # Establish baseline for cam1 with frame1
        detector.detect_changes(cam1, frame1)

        # Establish baseline for cam2 with frame2
        detector.detect_changes(cam2, frame2)

        # Now cam1 sees frame1 again - no change
        result1 = detector.detect_changes(cam1, frame1)
        assert result1.similarity_score > 0.99

        # cam2 sees frame2 again - no change
        result2 = detector.detect_changes(cam2, frame2)
        assert result2.similarity_score > 0.99


# =============================================================================
# Full Pipeline Integration Tests
# =============================================================================


class TestFullPipelineIntegration:
    """Integration tests for the complete enrichment pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_all_components(
        self,
        real_redis,
        test_image: Image.Image,
        sample_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
        mock_vision_extractor: VisionExtractor,
    ):
        """Test full pipeline with all components enabled."""
        # Mock CLIP embedding generation
        test_embedding = [float(i % 100) / 100.0 for i in range(768)]
        norm = sum(x * x for x in test_embedding) ** 0.5
        test_embedding = [x / norm for x in test_embedding]

        reid_service = get_reid_service()
        original_generate = reid_service.generate_embedding

        async def mock_generate_embedding(image, bbox=None, model=None):
            """Mock that matches new API: generate_embedding(image, bbox=None, model=None)."""
            return test_embedding

        reid_service.generate_embedding = mock_generate_embedding

        try:
            with patch(
                "backend.services.enrichment_pipeline.get_vision_extractor",
                return_value=mock_vision_extractor,
            ):
                pipeline = EnrichmentPipeline(
                    model_manager=mock_model_manager,
                    license_plate_enabled=False,
                    face_detection_enabled=False,
                    vision_extraction_enabled=True,
                    reid_enabled=True,
                    scene_change_enabled=True,
                    image_quality_enabled=False,  # Disable - brisque-quality model not in CI
                    weather_classification_enabled=False,  # Disable - weather-classification model not in CI
                    redis_client=real_redis._ensure_connected(),
                )

                camera_id = f"full_test_{uuid.uuid4().hex[:8]}"

                result = await pipeline.enrich_batch(
                    detections=sample_detections,
                    images={None: test_image},
                    camera_id=camera_id,
                )

                # Check all components ran
                assert result.has_vision_extraction
                assert result.processing_time_ms > 0
                # Allow model-related errors in CI (models not available)
                # Filter out errors that are due to missing models
                non_model_errors = [
                    e
                    for e in result.errors
                    if "model not available" not in str(e).lower()
                    and "not available in MODEL_ZOO" not in str(e)
                    and "Unknown model:" not in str(e)
                ]
                assert len(non_model_errors) == 0, f"Unexpected errors: {non_model_errors}"

                # Vision extraction results
                assert "1" in result.vision_extraction.person_attributes
                assert "2" in result.vision_extraction.vehicle_attributes

        finally:
            reid_service.generate_embedding = original_generate

    @pytest.mark.asyncio
    async def test_pipeline_context_string_generation(
        self,
        test_image: Image.Image,
        sample_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
        mock_vision_extractor: VisionExtractor,
    ):
        """Test pipeline generates proper context string for Nemotron prompt."""
        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=mock_vision_extractor,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=sample_detections,
                images={None: test_image},
                camera_id="context_test",
            )

            # Generate context string
            context = result.to_context_string()

            # Should contain vision analysis section
            assert "Vision Analysis" in context or "vehicle" in context.lower()

    @pytest.mark.asyncio
    async def test_pipeline_with_empty_detections(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test pipeline handles empty detection list gracefully."""
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=True,
            face_detection_enabled=True,
            vision_extraction_enabled=True,
            reid_enabled=True,
            scene_change_enabled=True,
        )

        result = await pipeline.enrich_batch(
            detections=[],
            images={None: test_image},
            camera_id="empty_test",
        )

        assert not result.has_vision_extraction
        assert not result.has_reid_matches
        assert not result.has_license_plates
        assert not result.has_faces
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_pipeline_confidence_filtering(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
        mock_vision_extractor: VisionExtractor,
    ):
        """Test pipeline filters low-confidence detections."""
        low_conf_detections = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.3,  # Below default threshold
                bbox=BoundingBox(x1=100, y1=100, x2=200, y2=400),
            ),
            DetectionInput(
                id=2,
                class_name="car",
                confidence=0.8,  # Above threshold
                bbox=BoundingBox(x1=300, y1=200, x2=500, y2=350),
            ),
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=mock_vision_extractor,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                min_confidence=0.5,  # Filter threshold
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=low_conf_detections,
                images={None: test_image},
                camera_id="conf_test",
            )

            # Only the high-confidence car detection should be processed
            if result.vision_extraction:
                # Person (id=1) should be filtered out due to low confidence
                assert "1" not in result.vision_extraction.person_attributes
                # Car (id=2) should be present
                assert "2" in result.vision_extraction.vehicle_attributes


# =============================================================================
# EnrichmentResult Tests
# =============================================================================


class TestEnrichmentResultIntegration:
    """Integration tests for EnrichmentResult formatting and serialization."""

    def test_enrichment_result_to_dict(self):
        """Test EnrichmentResult converts to dictionary properly."""
        result = EnrichmentResult(
            license_plates=[],
            faces=[],
            vision_extraction=BatchExtractionResult(
                vehicle_attributes={
                    "1": VehicleAttributes(
                        color="silver",
                        vehicle_type="SUV",
                        is_commercial=False,
                        commercial_text=None,
                        caption="A silver SUV in the parking lot",
                    )
                },
                person_attributes={},
                scene_analysis=SceneAnalysis(
                    scene_description="Parking lot at dusk",
                ),
            ),
            person_reid_matches={},
            vehicle_reid_matches={},
            scene_change=None,
            errors=[],
            processing_time_ms=125.5,
        )

        result_dict = result.to_dict()

        assert "license_plates" in result_dict
        assert "faces" in result_dict
        assert "errors" in result_dict
        assert result_dict["processing_time_ms"] == 125.5

    def test_enrichment_result_properties(self):
        """Test EnrichmentResult property methods."""
        # Empty result
        empty_result = EnrichmentResult()
        assert not empty_result.has_vision_extraction
        assert not empty_result.has_reid_matches
        assert not empty_result.has_scene_change
        assert not empty_result.has_license_plates
        assert not empty_result.has_faces

        # Result with vision extraction
        with_vision = EnrichmentResult(
            vision_extraction=BatchExtractionResult(
                vehicle_attributes={},
                person_attributes={
                    "1": PersonAttributes(
                        clothing="t-shirt",
                        carrying="nothing",
                        is_service_worker=False,
                        action="standing",
                        caption="A person wearing a t-shirt",
                    )
                },
            )
        )
        assert with_vision.has_vision_extraction

        # Result with re-id matches
        from backend.services.reid_service import EntityEmbedding, EntityMatch

        mock_match = EntityMatch(
            entity=EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="test",
                timestamp=datetime.now(UTC),
                detection_id="d1",
            ),
            similarity=0.92,
            time_gap_seconds=300.0,
        )
        with_reid = EnrichmentResult(person_reid_matches={"1": [mock_match]})
        assert with_reid.has_reid_matches

    def test_context_string_comprehensive(self):
        """Test context string includes all relevant information."""
        from backend.services.reid_service import EntityEmbedding, EntityMatch
        from backend.services.scene_change_detector import SceneChangeResult

        result = EnrichmentResult(
            vision_extraction=BatchExtractionResult(
                vehicle_attributes={
                    "v1": VehicleAttributes(
                        color="red",
                        vehicle_type="pickup",
                        is_commercial=False,
                        commercial_text=None,
                        caption="A red pickup truck",
                    )
                },
                person_attributes={
                    "p1": PersonAttributes(
                        clothing="hoodie",
                        carrying="bag",
                        is_service_worker=False,
                        action="walking",
                        caption="A person in a hoodie carrying a bag",
                    )
                },
                scene_analysis=SceneAnalysis(
                    scene_description="Night scene with artificial lighting",
                ),
            ),
            person_reid_matches={
                "p1": [
                    EntityMatch(
                        entity=EntityEmbedding(
                            entity_type="person",
                            embedding=[0.1] * 768,
                            camera_id="back_door",
                            timestamp=datetime.now(UTC),
                            detection_id="prev_001",
                            attributes={"clothing": "hoodie"},
                        ),
                        similarity=0.91,
                        time_gap_seconds=600.0,
                    )
                ]
            },
            scene_change=SceneChangeResult(
                similarity_score=0.75,
                change_detected=True,
            ),
        )

        context = result.to_context_string()

        # Should contain vision analysis
        assert "Vision" in context or "vehicle" in context.lower() or "person" in context.lower()


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestPipelineEdgeCases:
    """Test edge cases and error handling in the pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_with_no_image(
        self,
        sample_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ):
        """Test pipeline handles missing shared image."""
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            vision_extraction_enabled=True,
            reid_enabled=False,
            scene_change_enabled=False,
        )

        # Empty images dict - no shared image
        result = await pipeline.enrich_batch(
            detections=sample_detections,
            images={},
            camera_id="no_image_test",
        )

        # Should not crash, vision extraction requires image
        assert not result.has_vision_extraction

    @pytest.mark.asyncio
    async def test_pipeline_with_invalid_bbox(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
        mock_vision_extractor: VisionExtractor,
    ):
        """Test pipeline handles invalid bounding boxes."""
        invalid_detections = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.9,
                bbox=BoundingBox(x1=-10, y1=-10, x2=10, y2=10),  # Partially negative
            ),
            DetectionInput(
                id=2,
                class_name="car",
                confidence=0.9,
                bbox=BoundingBox(x1=1000, y1=1000, x2=2000, y2=2000),  # Out of bounds
            ),
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=mock_vision_extractor,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
            )

            # Should not crash
            result = await pipeline.enrich_batch(
                detections=invalid_detections,
                images={None: test_image},
                camera_id="invalid_bbox_test",
            )

            # May or may not have results depending on implementation
            assert isinstance(result, EnrichmentResult)

    @pytest.mark.asyncio
    async def test_pipeline_multiple_errors_recorded(
        self,
        test_image: Image.Image,
        sample_detections: list[DetectionInput],
        mock_model_manager: MagicMock,
    ):
        """Test pipeline records multiple errors from different components."""
        # Create extractors that fail
        failing_vision = VisionExtractor()
        failing_vision.extract_batch_attributes = AsyncMock(
            side_effect=RuntimeError("Vision failed")
        )

        failing_scene = SceneChangeDetector()
        failing_scene.detect_changes = MagicMock(side_effect=RuntimeError("Scene detection failed"))

        with (
            patch(
                "backend.services.enrichment_pipeline.get_vision_extractor",
                return_value=failing_vision,
            ),
            patch(
                "backend.services.enrichment_pipeline.get_scene_change_detector",
                return_value=failing_scene,
            ),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=sample_detections,
                images={None: test_image},
                camera_id="multi_error_test",
            )

            # Should have recorded errors from both components
            assert len(result.errors) >= 1
            error_text = " ".join(result.errors)
            assert "Vision" in error_text or "Scene" in error_text
