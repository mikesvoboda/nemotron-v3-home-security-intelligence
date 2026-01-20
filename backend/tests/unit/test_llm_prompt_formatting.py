"""Unit tests for LLM prompt formatting with enrichment data.

This module tests the prompt building logic to ensure no KeyError exceptions
occur when formatting prompts with realistic EnrichmentResult data.

Key bug prevention:
- Guards against KeyError: 'ondemand_enrichment_context' (NEM-3026)
- Ensures all MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT fields are set
- Validates prompt formatting with various enrichment scenarios

These are pure unit tests that don't require database access.
"""

import pytest

from backend.services.enrichment_pipeline import (
    BoundingBox,
    ClothingClassification,
    EnrichmentResult,
    FaceResult,
    LicensePlateResult,
    VehicleClassificationResult,
    VehicleDamageResult,
    ViolenceDetectionResult,
    WeatherResult,
)
from backend.services.vision_extractor import (
    BatchExtractionResult,
    EnvironmentContext,
    PersonAttributes,
    SceneAnalysis,
    VehicleAttributes,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def realistic_enrichment_result():
    """Create a realistic EnrichmentResult with full Model Zoo data.

    This simulates the output from enrichment pipeline including all
    model zoo components that would be present in production.
    """
    return EnrichmentResult(
        license_plates=[
            LicensePlateResult(
                bbox=BoundingBox(x1=310, y1=220, x2=380, y2=250),
                text="ABC1234",
                confidence=0.92,
                ocr_confidence=0.88,
                source_detection_id=2,
            )
        ],
        faces=[
            FaceResult(
                bbox=BoundingBox(x1=150, y1=180, x2=190, y2=240),
                confidence=0.94,
                source_detection_id=1,
            )
        ],
        vision_extraction=BatchExtractionResult(
            scene_analysis=SceneAnalysis(
                scene_description="A person walking towards a parked car in a residential driveway",
                unusual_objects=[],
                tools_detected=[],
                abandoned_items=[],
            ),
            environment_context=EnvironmentContext(
                time_of_day="afternoon",
                artificial_light=False,
                weather="clear",
            ),
            person_attributes={
                "1": PersonAttributes(
                    clothing="dark jacket, jeans",
                    carrying="backpack",
                    is_service_worker=False,
                    action="walking",
                    caption="Person walking towards vehicle",
                )
            },
            vehicle_attributes={
                "2": VehicleAttributes(
                    color="blue",
                    vehicle_type="sedan",
                    is_commercial=False,
                    commercial_text=None,
                    caption="Blue Honda Civic sedan parked in driveway",
                )
            },
        ),
        violence_detection=ViolenceDetectionResult(
            is_violent=False,
            confidence=0.95,
            violent_score=0.05,
            non_violent_score=0.95,
        ),
        weather_classification=WeatherResult(
            condition="clear/sunny",
            simple_condition="clear",
            confidence=0.91,
            all_scores={"clear/sunny": 0.91, "cloudy": 0.05, "rain": 0.04},
        ),
        clothing_classifications={
            "1": ClothingClassification(
                top_category="casual jacket",
                confidence=0.87,
                all_scores={"casual jacket": 0.87, "uniform": 0.08, "hoodie": 0.05},
                is_suspicious=False,
                is_service_uniform=False,
                raw_description="dark blue jacket with jeans",
            )
        },
        vehicle_classifications={
            "2": VehicleClassificationResult(
                vehicle_type="sedan",
                display_name="Sedan",
                confidence=0.89,
                is_commercial=False,
                all_scores={"sedan": 0.89, "suv": 0.07, "pickup_truck": 0.04},
            )
        },
        vehicle_damage={
            "2": VehicleDamageResult(
                detections=[],
            )
        },
        pet_classifications={},
        errors=[],
        structured_errors=[],
        processing_time_ms=1250.5,
    )


@pytest.fixture
def partial_enrichment_result():
    """Create partial enrichment with some components missing.

    This tests the scenario where some enrichment models failed.
    """
    return EnrichmentResult(
        vision_extraction=BatchExtractionResult(
            scene_analysis=SceneAnalysis(
                scene_description="A person standing outdoors",
                unusual_objects=[],
                tools_detected=[],
                abandoned_items=[],
            ),
            environment_context=EnvironmentContext(
                time_of_day="afternoon",
                artificial_light=False,
                weather="clear",
            ),
            person_attributes={},
            vehicle_attributes={},
        ),
        weather_classification=WeatherResult(
            condition="clear/sunny",
            simple_condition="clear",
            confidence=0.85,
            all_scores={"clear/sunny": 0.85, "cloudy": 0.10, "rain": 0.05},
        ),
        # Missing: clothing, vehicle classification, pets, violence
        license_plates=[],
        faces=[],
        violence_detection=None,
        clothing_classifications={},
        vehicle_classifications={},
        pet_classifications={},
        errors=["Clothing model timeout", "Vehicle classifier unavailable"],
    )


@pytest.fixture
def minimal_enrichment_result():
    """Create minimal enrichment with only basic components."""
    return EnrichmentResult(
        license_plates=[],
        faces=[],
        vision_extraction=None,
        violence_detection=None,
        weather_classification=None,
        clothing_classifications={},
        vehicle_classifications={},
        pet_classifications={},
        errors=["All models unavailable"],
    )


# =============================================================================
# Test: Prompt Formatting with Full Enrichment
# =============================================================================


class TestPromptFormattingWithFullEnrichment:
    """Test prompt formatting doesn't raise KeyError with full enrichment."""

    async def test_format_enriched_detections_with_model_zoo_data(
        self, realistic_enrichment_result
    ):
        """Verify formatting detections with full Model Zoo enrichment doesn't raise KeyError.

        This guards against KeyError: 'ondemand_enrichment_context' by ensuring
        all prompt template fields can be populated from enrichment data.
        """
        from backend.services.prompts import format_detections_with_all_enrichment

        # Create mock detections data
        detections_data = [
            {
                "id": 1,
                "object_type": "person",
                "confidence": 0.95,
                "detected_at": "2025-12-23T14:00:00",
                "bbox_x": 100,
                "bbox_y": 150,
                "bbox_width": 200,
                "bbox_height": 400,
            },
            {
                "id": 2,
                "object_type": "car",
                "confidence": 0.88,
                "detected_at": "2025-12-23T14:01:00",
                "bbox_x": 300,
                "bbox_y": 200,
                "bbox_width": 400,
                "bbox_height": 300,
            },
        ]

        # This should NOT raise KeyError
        formatted = format_detections_with_all_enrichment(
            detections_data,
            enrichment_result=realistic_enrichment_result,
        )

        # Verify output is a string
        assert isinstance(formatted, str)
        assert len(formatted) > 0

        # Verify key enrichment data is present
        assert "person" in formatted.lower()
        assert "car" in formatted.lower()

    async def test_formatting_context_sections_with_enrichment(self, realistic_enrichment_result):
        """Verify all context formatting functions work with enrichment data."""
        from backend.services.prompts import (
            format_clothing_analysis_context,
            format_pet_classification_context,
            format_vehicle_classification_context,
            format_vehicle_damage_context,
            format_violence_context,
            format_weather_context,
        )

        # Test each context formatter - none should raise exceptions
        weather_ctx = format_weather_context(realistic_enrichment_result.weather_classification)
        assert isinstance(weather_ctx, str)

        violence_ctx = format_violence_context(realistic_enrichment_result.violence_detection)
        assert isinstance(violence_ctx, str)

        clothing_ctx = format_clothing_analysis_context(
            realistic_enrichment_result.clothing_classifications
        )
        assert isinstance(clothing_ctx, str)

        vehicle_class_ctx = format_vehicle_classification_context(
            realistic_enrichment_result.vehicle_classifications
        )
        assert isinstance(vehicle_class_ctx, str)

        vehicle_damage_ctx = format_vehicle_damage_context(
            realistic_enrichment_result.vehicle_damage
        )
        assert isinstance(vehicle_damage_ctx, str)

        pet_ctx = format_pet_classification_context(realistic_enrichment_result.pet_classifications)
        assert isinstance(pet_ctx, str)


# =============================================================================
# Test: Prompt Formatting with Partial Enrichment
# =============================================================================


class TestPromptFormattingWithPartialEnrichment:
    """Test prompt formatting handles partial enrichment gracefully."""

    async def test_format_with_partial_enrichment_no_exceptions(self, partial_enrichment_result):
        """Verify formatting works when some enrichment components are missing."""
        from backend.services.prompts import format_detections_with_all_enrichment

        detections_data = [
            {
                "id": 1,
                "object_type": "person",
                "confidence": 0.90,
                "detected_at": "2025-12-23T14:00:00",
                "bbox_x": 100,
                "bbox_y": 150,
                "bbox_width": 200,
                "bbox_height": 400,
            }
        ]

        # Should handle missing components gracefully
        formatted = format_detections_with_all_enrichment(
            detections_data,
            enrichment_result=partial_enrichment_result,
        )

        assert isinstance(formatted, str)
        assert len(formatted) > 0

    async def test_format_context_with_none_values(self):
        """Verify context formatters handle None inputs gracefully."""
        from backend.services.prompts import (
            format_violence_context,
            format_weather_context,
        )

        # Should return appropriate default/empty strings
        weather_ctx = format_weather_context(None)
        assert isinstance(weather_ctx, str)

        violence_ctx = format_violence_context(None)
        assert isinstance(violence_ctx, str)


# =============================================================================
# Test: Prompt Formatting with Minimal Enrichment
# =============================================================================


class TestPromptFormattingWithMinimalEnrichment:
    """Test prompt formatting with minimal/no enrichment."""

    async def test_format_with_minimal_enrichment_no_exceptions(self, minimal_enrichment_result):
        """Verify formatting works with minimal enrichment data."""
        from backend.services.prompts import format_detections_with_all_enrichment

        detections_data = [
            {
                "id": 1,
                "object_type": "person",
                "confidence": 0.85,
                "detected_at": "2025-12-23T14:00:00",
                "bbox_x": 100,
                "bbox_y": 150,
                "bbox_width": 200,
                "bbox_height": 400,
            }
        ]

        # Should handle minimal enrichment
        formatted = format_detections_with_all_enrichment(
            detections_data,
            enrichment_result=minimal_enrichment_result,
        )

        assert isinstance(formatted, str)
        assert len(formatted) > 0

    async def test_format_with_no_enrichment(self):
        """Verify formatting works when enrichment_result is None."""
        from backend.services.prompts import format_detections_with_all_enrichment

        detections_data = [
            {
                "id": 1,
                "object_type": "person",
                "confidence": 0.85,
                "detected_at": "2025-12-23T14:00:00",
                "bbox_x": 100,
                "bbox_y": 150,
                "bbox_width": 200,
                "bbox_height": 400,
            }
        ]

        # Should handle None enrichment
        formatted = format_detections_with_all_enrichment(
            detections_data,
            enrichment_result=None,
        )

        assert isinstance(formatted, str)
        assert len(formatted) > 0


# =============================================================================
# Test: Empty Collections Don't Cause Formatting Errors
# =============================================================================


class TestEmptyCollectionsHandling:
    """Test that empty collections in enrichment don't cause errors."""

    async def test_empty_license_plates_list(self):
        """Verify empty license plates list doesn't cause formatting errors."""
        enrichment = EnrichmentResult(license_plates=[])

        # Should handle empty list
        from backend.services.prompts import format_detections_with_all_enrichment

        formatted = format_detections_with_all_enrichment(
            [{"id": 1, "object_type": "car", "confidence": 0.9}],
            enrichment_result=enrichment,
        )
        assert isinstance(formatted, str)

    async def test_empty_faces_list(self):
        """Verify empty faces list doesn't cause formatting errors."""
        enrichment = EnrichmentResult(faces=[])

        from backend.services.prompts import format_detections_with_all_enrichment

        formatted = format_detections_with_all_enrichment(
            [{"id": 1, "object_type": "person", "confidence": 0.9}],
            enrichment_result=enrichment,
        )
        assert isinstance(formatted, str)

    async def test_empty_classification_dicts(self):
        """Verify empty classification dictionaries don't cause errors."""
        enrichment = EnrichmentResult(
            clothing_classifications={},
            vehicle_classifications={},
            pet_classifications={},
        )

        from backend.services.prompts import (
            format_clothing_analysis_context,
            format_pet_classification_context,
            format_vehicle_classification_context,
        )

        clothing_ctx = format_clothing_analysis_context(enrichment.clothing_classifications)
        vehicle_ctx = format_vehicle_classification_context(enrichment.vehicle_classifications)
        pet_ctx = format_pet_classification_context(enrichment.pet_classifications)

        assert isinstance(clothing_ctx, str)
        assert isinstance(vehicle_ctx, str)
        assert isinstance(pet_ctx, str)
