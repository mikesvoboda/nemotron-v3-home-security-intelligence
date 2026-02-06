"""Integration tests for Florence-2 YOLO cross-validation pipeline.

These tests verify the full pipeline integration of YOLO-Florence cross-validation,
ensuring that misclassifications are caught and validation context is properly
passed to the Nemotron prompt.

NEM-5478: Florence-2 YOLO Cross-Validation feature.

TDD Note: These tests should FAIL until the cross-validation feature is implemented.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    reset_enrichment_pipeline,
)
from backend.services.vision_extractor import (
    BatchExtractionResult,
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


@pytest.fixture(autouse=True)
def reset_global_services():
    """Reset global service instances before and after each test."""
    reset_enrichment_pipeline()
    reset_vision_extractor()
    yield
    reset_enrichment_pipeline()
    reset_vision_extractor()


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

    mock_florence = MagicMock()
    mock_florence_processor = MagicMock()

    def mock_load(model_name: str):
        if model_name == "florence-2":
            return MockAsyncContextManager(
                {"model": mock_florence, "processor": mock_florence_processor}
            )
        else:
            raise KeyError(f"Unknown model: {model_name}")

    manager.load = mock_load
    return manager


# =============================================================================
# Bus Misclassification Regression Tests
# =============================================================================


class TestBusNotMisclassifiedAsPoliceCarIntegration:
    """Integration tests for bus/police car misclassification prevention.

    This is the primary regression test for NEM-5478. The pipeline should
    prevent Florence from misclassifying a bus as a police car when YOLO
    has detected a bus with high confidence.
    """

    @pytest.mark.asyncio
    async def test_bus_not_misclassified_as_police_car_full_pipeline(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test full pipeline prevents bus -> police car misclassification.

        Scenario:
        - YOLO detects a bus with 0.88 confidence
        - Florence hallucinates "police car" as the vehicle type
        - Cross-validation should detect the conflict
        - Final result should use YOLO's "bus" classification
        - Validation note should be included for Nemotron context
        """
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock Florence returning incorrect police car classification."""
            if task == "<CAPTION>":
                return "A white police car with emergency lights"
            elif "type" in text_input.lower():
                return "police car"
            elif "color" in text_input.lower():
                return "white"
            elif "commercial" in text_input.lower():
                return "yes"
            elif "logo" in text_input.lower():
                return "Police"
            return ""

        extractor._query_florence = mock_query

        # Create detection with YOLO detecting BUS
        detections = [
            DetectionInput(
                id=1,
                class_name="bus",  # YOLO says BUS
                confidence=0.88,
                bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
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
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Verify vision extraction ran
            assert result.has_vision_extraction
            assert result.vision_extraction is not None

            # Get the vehicle attributes for our detection
            vehicle_attrs = result.vision_extraction.vehicle_attributes.get("1")
            assert vehicle_attrs is not None, "Vehicle attributes should be extracted"

            # CRITICAL: Vehicle type should be "bus", NOT "police car"
            assert vehicle_attrs.vehicle_type == "bus", (
                f"Vehicle type should be 'bus' (from YOLO), not '{vehicle_attrs.vehicle_type}'. "
                "Cross-validation should have caught the Florence hallucination."
            )

            # Validation note should indicate the conflict was detected
            assert vehicle_attrs.validation_note is not None, (
                "Validation note should be present when cross-validation detects a conflict"
            )
            assert (
                "conflict" in vehicle_attrs.validation_note.lower()
                or "mismatch" in vehicle_attrs.validation_note.lower()
            ), f"Validation note should mention conflict: {vehicle_attrs.validation_note}"

    @pytest.mark.asyncio
    async def test_bus_correctly_identified_when_florence_agrees(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test bus is correctly identified when YOLO and Florence agree."""
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock Florence correctly identifying bus."""
            if task == "<CAPTION>":
                return "A yellow school bus"
            elif "type" in text_input.lower():
                return "school bus"  # Matches YOLO's bus detection
            elif "color" in text_input.lower():
                return "yellow"
            elif "commercial" in text_input.lower():
                return "yes"
            elif "logo" in text_input.lower():
                return "School District"
            return ""

        extractor._query_florence = mock_query

        detections = [
            DetectionInput(
                id=1,
                class_name="bus",
                confidence=0.92,
                bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
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
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.has_vision_extraction
            vehicle_attrs = result.vision_extraction.vehicle_attributes.get("1")
            assert vehicle_attrs is not None

            # Florence's "school bus" is semantically equivalent to YOLO's "bus"
            # So Florence's more specific description should be used
            assert vehicle_attrs.vehicle_type in ("school bus", "bus"), (
                f"Vehicle type should be 'school bus' or 'bus', got '{vehicle_attrs.vehicle_type}'"
            )

            # No conflict should be flagged since they semantically match
            if vehicle_attrs.validation_note:
                assert "conflict" not in vehicle_attrs.validation_note.lower(), (
                    "Should not flag conflict when YOLO and Florence semantically agree"
                )


# =============================================================================
# Prompt Context Tests
# =============================================================================


class TestPromptIncludesValidationNotesIntegration:
    """Integration tests for validation notes in Nemotron prompt context.

    The enrichment pipeline should include validation notes in the context
    string generated for the Nemotron prompt, so the LLM understands when
    cross-validation corrections were made.
    """

    @pytest.mark.asyncio
    async def test_prompt_includes_validation_notes_on_conflict(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test Nemotron prompt context includes validation notes when conflict detected."""
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A police car with flashing lights"  # Hallucination
            elif "type" in text_input.lower():
                return "police car"
            elif "color" in text_input.lower():
                return "white"
            elif "commercial" in text_input.lower():
                return "no"
            return ""

        extractor._query_florence = mock_query

        detections = [
            DetectionInput(
                id=1,
                class_name="bus",  # YOLO says bus
                confidence=0.91,
                bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
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
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # Generate context string for Nemotron
            context = result.to_context_string()

            # Context should include validation information
            assert "bus" in context.lower(), (
                "Context should mention the corrected vehicle type 'bus'"
            )

            # Should include validation note about the correction
            assert (
                "validation" in context.lower()
                or "yolo" in context.lower()
                or "cross-validation" in context.lower()
            ), f"Context should include validation notes. Got: {context[:500]}..."

    @pytest.mark.asyncio
    async def test_prompt_includes_yolo_confidence(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test Nemotron prompt context includes YOLO confidence when relevant."""
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A red truck"
            elif "type" in text_input.lower():
                return "pickup truck"
            elif "color" in text_input.lower():
                return "red"
            elif "commercial" in text_input.lower():
                return "no"
            return ""

        extractor._query_florence = mock_query

        detections = [
            DetectionInput(
                id=1,
                class_name="truck",
                confidence=0.85,
                bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
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
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            context = result.to_context_string()

            # Context should provide useful vehicle information
            assert "truck" in context.lower() or "pickup" in context.lower(), (
                "Context should mention the vehicle type"
            )


# =============================================================================
# Multiple Vehicle Detection Tests
# =============================================================================


class TestMultipleVehicleCrossValidation:
    """Integration tests for cross-validation with multiple vehicles.

    The pipeline should correctly handle cross-validation for multiple
    vehicles in the same frame, each with its own YOLO detection.
    """

    @pytest.mark.asyncio
    async def test_multiple_vehicles_independent_validation(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test each vehicle gets independent cross-validation."""
        extractor = VisionExtractor()

        # Track which detection is being processed
        call_count = {"count": 0}

        async def mock_query(image, task, text_input=""):  # noqa: PLR0911
            # Different responses for different calls
            call_count["count"] += 1
            call_idx = call_count["count"]

            if task == "<CAPTION>":
                # First vehicle: correct, second vehicle: hallucination
                if call_idx <= 4:  # First vehicle queries
                    return "A white sedan"
                else:
                    return "A police car"  # Hallucination for bus
            elif "type" in text_input.lower():
                if call_idx <= 4:
                    return "sedan"
                else:
                    return "police car"  # Wrong
            elif "color" in text_input.lower():
                return "white"
            elif "commercial" in text_input.lower():
                return "no"
            return ""

        extractor._query_florence = mock_query

        detections = [
            DetectionInput(
                id=1,
                class_name="car",  # YOLO: car
                confidence=0.90,
                bbox=BoundingBox(x1=50, y1=100, x2=150, y2=200),
            ),
            DetectionInput(
                id=2,
                class_name="bus",  # YOLO: bus
                confidence=0.85,
                bbox=BoundingBox(x1=200, y1=100, x2=400, y2=300),
            ),
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
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
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.has_vision_extraction

            # First vehicle: car -> sedan (semantic match, use Florence)
            car_attrs = result.vision_extraction.vehicle_attributes.get("1")
            assert car_attrs is not None
            assert car_attrs.vehicle_type == "sedan", (
                "Car/sedan semantic match should use Florence's 'sedan'"
            )

            # Second vehicle: bus -> police car conflict, use YOLO's 'bus'
            bus_attrs = result.vision_extraction.vehicle_attributes.get("2")
            assert bus_attrs is not None
            assert bus_attrs.vehicle_type == "bus", (
                f"Bus detection should use YOLO's 'bus', not '{bus_attrs.vehicle_type}'"
            )


# =============================================================================
# Person-Vehicle Mismatch Tests
# =============================================================================


class TestPersonVehicleMismatchIntegration:
    """Integration tests for person-vehicle mismatch detection.

    When YOLO detects a person but Florence describes a vehicle (or vice versa),
    this is a critical error that should be flagged and handled.
    """

    @pytest.mark.asyncio
    async def test_person_described_as_vehicle_flagged(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test YOLO 'person' + Florence 'vehicle' generates error."""
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock Florence completely misidentifying a person as a truck."""
            if task == "<CAPTION>":
                return "A white truck parked in the driveway"  # Wrong!
            elif "wearing" in text_input.lower():
                return "N/A - this is a vehicle"  # Wrong!
            elif "carrying" in text_input.lower():
                return "N/A"
            elif "service worker" in text_input.lower():
                return "no"
            elif "doing" in text_input.lower():
                return "parked"  # Wrong!
            return ""

        extractor._query_florence = mock_query

        detections = [
            DetectionInput(
                id=1,
                class_name="person",  # YOLO correctly detected person
                confidence=0.88,
                bbox=BoundingBox(x1=100, y1=100, x2=200, y2=400),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
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
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.has_vision_extraction

            # Should have person attributes since YOLO detected person
            person_attrs = result.vision_extraction.person_attributes.get("1")
            assert person_attrs is not None, (
                "Person attributes should exist since YOLO detected 'person'"
            )

            # The cross-validation error should be flagged
            # Either in the attributes or in the pipeline errors
            has_error_flag = False

            if hasattr(person_attrs, "cross_validation_error"):
                has_error_flag = person_attrs.cross_validation_error is not None

            if hasattr(person_attrs, "validation_note") and person_attrs.validation_note:
                has_error_flag = has_error_flag or "error" in person_attrs.validation_note.lower()

            # Or check pipeline errors
            if result.errors:
                for error in result.errors:
                    if "mismatch" in error.lower() or "person" in error.lower():
                        has_error_flag = True
                        break

            assert has_error_flag, (
                "Person-vehicle mismatch should be flagged as an error. "
                f"Person attrs: {person_attrs}, Errors: {result.errors}"
            )


# =============================================================================
# Edge Cases and Robustness Tests
# =============================================================================


class TestCrossValidationEdgeCases:
    """Integration tests for cross-validation edge cases."""

    @pytest.mark.asyncio
    async def test_missing_yolo_confidence_uses_default(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test cross-validation handles missing YOLO confidence gracefully."""
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A blue sedan"
            elif "type" in text_input.lower():
                return "sedan"
            elif "color" in text_input.lower():
                return "blue"
            elif "commercial" in text_input.lower():
                return "no"
            return ""

        extractor._query_florence = mock_query

        # Detection without confidence (should use default)
        detections = [
            DetectionInput(
                id=1,
                class_name="car",
                confidence=0.0,  # Missing/zero confidence
                bbox=BoundingBox(x1=100, y1=100, x2=200, y2=200),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
                min_confidence=0.0,  # Allow zero-confidence detections through
            )

            # Should not crash
            result = await pipeline.enrich_batch(
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.has_vision_extraction
            vehicle_attrs = result.vision_extraction.vehicle_attributes.get("1")
            assert vehicle_attrs is not None

    @pytest.mark.asyncio
    async def test_florence_returns_empty_type_uses_yolo(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test cross-validation uses YOLO when Florence returns empty type."""
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A vehicle in the parking lot"
            elif "type" in text_input.lower():
                return ""  # Florence couldn't determine type
            elif "color" in text_input.lower():
                return "silver"
            elif "commercial" in text_input.lower():
                return "no"
            return ""

        extractor._query_florence = mock_query

        detections = [
            DetectionInput(
                id=1,
                class_name="truck",
                confidence=0.80,
                bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
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
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.has_vision_extraction
            vehicle_attrs = result.vision_extraction.vehicle_attributes.get("1")
            assert vehicle_attrs is not None

            # When Florence returns empty, should fall back to YOLO class
            assert vehicle_attrs.vehicle_type == "truck", (
                f"Should use YOLO 'truck' when Florence returns empty, got '{vehicle_attrs.vehicle_type}'"
            )

    @pytest.mark.asyncio
    async def test_unknown_yolo_class_passes_through(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ):
        """Test unknown YOLO classes are handled gracefully."""
        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "An airplane on the tarmac"
            elif "type" in text_input.lower():
                return "airplane"
            elif "color" in text_input.lower():
                return "white"
            elif "commercial" in text_input.lower():
                return "yes"
            return ""

        extractor._query_florence = mock_query

        # YOLO detecting something unusual
        detections = [
            DetectionInput(
                id=1,
                class_name="airplane",  # Not in standard vehicle classes
                confidence=0.75,
                bbox=BoundingBox(x1=100, y1=100, x2=500, y2=300),
            )
        ]

        with patch(
            "backend.services.enrichment_pipeline.get_vision_extractor",
            return_value=extractor,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
            )

            # Should not crash on unknown YOLO class
            result = await pipeline.enrich_batch(
                detections=detections,
                images={None: test_image},
                camera_id="test_camera",
            )

            # May or may not have vehicle attributes depending on implementation
            # But should not crash
            assert isinstance(result.vision_extraction, BatchExtractionResult)
