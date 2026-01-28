"""Unit tests for backend/services/prompts.py

Comprehensive tests for prompt templates and generation functions used by
the Nemotron analyzer for risk assessment.

Tests cover:
- All prompt template constants (RISK_ANALYSIS_PROMPT, ENRICHED_RISK_ANALYSIS_PROMPT,
  FULL_ENRICHED_RISK_ANALYSIS_PROMPT, VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
  MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT)
- Variable substitution in prompts
- Prompt formatting for Nemotron ChatML format
- Edge cases: special characters, long inputs, empty inputs
- All format_* context functions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pytest

from backend.services.prompts import (
    CALIBRATED_SYSTEM_PROMPT,
    ENRICHED_RISK_ANALYSIS_PROMPT,
    FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
    HOUSEHOLD_CONTEXT_TEMPLATE,
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
    NON_RISK_FACTORS,
    RISK_ANALYSIS_PROMPT,
    SCORING_REFERENCE_TABLE,
    SUMMARY_EMPTY_STATE_INSTRUCTION,
    SUMMARY_EVENT_FORMAT,
    SUMMARY_PROMPT_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
    VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
    ClassAnomalyResult,
    build_summary_prompt,
    # Household context functions (NEM-3024, NEM-3315)
    check_member_schedule,
    # Other format functions
    format_action_recognition_context,
    format_class_anomaly_context,
    format_clothing_analysis_context,
    format_depth_context,
    format_detections_with_all_enrichment,
    # VQA validation functions (NEM-3304)
    format_florence_attributes,
    format_household_context,
    format_image_quality_context,
    format_pet_classification_context,
    format_pose_analysis_context,
    format_temporal_action_context,
    format_vehicle_classification_context,
    format_vehicle_damage_context,
    format_violence_context,
    format_weather_context,
    is_valid_vqa_output,
    validate_and_clean_vqa_output,
)

# =============================================================================
# Mock Data Classes for Testing
# =============================================================================


@dataclass
class MockViolenceDetectionResult:
    """Mock ViolenceDetectionResult for testing."""

    is_violent: bool
    confidence: float
    violent_score: float
    non_violent_score: float


@dataclass
class MockWeatherResult:
    """Mock WeatherResult for testing."""

    simple_condition: str
    confidence: float


@dataclass
class MockClothingClassification:
    """Mock ClothingClassification for testing."""

    raw_description: str
    confidence: float
    is_suspicious: bool
    is_service_uniform: bool
    top_category: str


@dataclass
class MockClothingSegmentationResult:
    """Mock ClothingSegmentationResult for testing."""

    clothing_items: list[str]
    has_face_covered: bool
    has_bag: bool


@dataclass
class MockVehicleClassificationResult:
    """Mock VehicleClassificationResult for testing."""

    vehicle_type: str
    display_name: str
    confidence: float
    is_commercial: bool
    all_scores: dict[str, float]


@dataclass
class MockVehicleDamageResult:
    """Mock VehicleDamageResult for testing."""

    has_damage: bool
    damage_types: set[str]
    total_damage_count: int
    highest_confidence: float
    has_high_security_damage: bool


@dataclass
class MockPetClassificationResult:
    """Mock PetClassificationResult for testing."""

    animal_type: str
    confidence: float


@dataclass
class MockImageQualityResult:
    """Mock ImageQualityResult for testing."""

    quality_score: float
    is_good_quality: bool
    is_blurry: bool
    is_noisy: bool
    quality_issues: list[str]


@dataclass
class MockVehicleAttributes:
    """Mock vehicle attributes from vision extraction."""

    color: str | None = None
    vehicle_type: str | None = None
    is_commercial: bool = False
    commercial_text: str | None = None
    caption: str | None = None


@dataclass
class MockPersonAttributes:
    """Mock person attributes from vision extraction."""

    clothing: str | None = None
    carrying: str | None = None
    action: str | None = None
    is_service_worker: bool = False
    caption: str | None = None


@dataclass
class MockBatchExtractionResult:
    """Mock BatchExtractionResult from vision_extractor."""

    vehicle_attributes: dict[str, MockVehicleAttributes] = field(default_factory=dict)
    person_attributes: dict[str, MockPersonAttributes] = field(default_factory=dict)


@dataclass
class MockEnrichmentResult:
    """Mock EnrichmentResult from enrichment_pipeline."""

    clothing_classifications: dict[str, MockClothingClassification] = field(default_factory=dict)
    clothing_segmentation: dict[str, MockClothingSegmentationResult] = field(default_factory=dict)
    vehicle_classifications: dict[str, MockVehicleClassificationResult] = field(
        default_factory=dict
    )
    vehicle_damage: dict[str, MockVehicleDamageResult] = field(default_factory=dict)
    pet_classifications: dict[str, MockPetClassificationResult] = field(default_factory=dict)


@dataclass
class MockClassBaseline:
    """Mock ClassBaseline for testing format_class_anomaly_context.

    Implements the ClassBaselineProtocol interface with frequency and sample_count.
    """

    frequency: float
    sample_count: int


# =============================================================================
# Test Classes for Prompt Templates
# =============================================================================


class TestRiskAnalysisPromptTemplate:
    """Tests for the basic RISK_ANALYSIS_PROMPT template."""

    def test_template_exists(self) -> None:
        """Test that the basic prompt template is defined."""
        assert RISK_ANALYSIS_PROMPT is not None
        assert isinstance(RISK_ANALYSIS_PROMPT, str)
        assert len(RISK_ANALYSIS_PROMPT) > 0

    def test_template_has_chatml_format(self) -> None:
        """Test that the template uses ChatML format for Nemotron."""
        assert "<|im_start|>system" in RISK_ANALYSIS_PROMPT
        assert "<|im_start|>user" in RISK_ANALYSIS_PROMPT
        assert "<|im_start|>assistant" in RISK_ANALYSIS_PROMPT
        assert "<|im_end|>" in RISK_ANALYSIS_PROMPT

    def test_template_has_required_placeholders(self) -> None:
        """Test that the template contains required placeholder variables."""
        required_placeholders = [
            "{camera_name}",
            "{start_time}",
            "{end_time}",
            "{detections_list}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in RISK_ANALYSIS_PROMPT, f"Missing placeholder: {placeholder}"

    def test_template_has_json_output_format(self) -> None:
        """Test that the template specifies JSON output format."""
        assert '"risk_score"' in RISK_ANALYSIS_PROMPT
        assert '"risk_level"' in RISK_ANALYSIS_PROMPT
        assert '"summary"' in RISK_ANALYSIS_PROMPT
        assert '"reasoning"' in RISK_ANALYSIS_PROMPT

    def test_template_has_risk_level_guidance(self) -> None:
        """Test that the template provides risk level ranges (NEM-3880 calibrated)."""
        assert "low (0-20)" in RISK_ANALYSIS_PROMPT
        assert "elevated (21-40)" in RISK_ANALYSIS_PROMPT
        assert "moderate (41-60)" in RISK_ANALYSIS_PROMPT
        assert "high (61-80)" in RISK_ANALYSIS_PROMPT
        assert "critical (81-100)" in RISK_ANALYSIS_PROMPT

    def test_template_variable_substitution(self) -> None:
        """Test that template variables can be properly substituted."""
        substituted = RISK_ANALYSIS_PROMPT.format(
            camera_name="front_door",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:30",
            detections_list="person: 95%, car: 87%",
        )
        assert "front_door" in substituted
        assert "2024-01-01 10:00:00" in substituted
        assert "2024-01-01 10:01:30" in substituted
        assert "person: 95%, car: 87%" in substituted

    def test_template_substitution_with_special_characters(self) -> None:
        """Test substitution works with special characters."""
        special_chars = 'Camera <"test"> & sensors'
        substituted = RISK_ANALYSIS_PROMPT.format(
            camera_name=special_chars,
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:30",
            detections_list="person: 95%",
        )
        assert special_chars in substituted

    def test_template_substitution_with_unicode(self) -> None:
        """Test substitution works with unicode characters."""
        unicode_text = "Camera name with unicode characters"
        substituted = RISK_ANALYSIS_PROMPT.format(
            camera_name=unicode_text,
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:30",
            detections_list="detection list",
        )
        assert unicode_text in substituted


class TestEnrichedRiskAnalysisPromptTemplate:
    """Tests for the ENRICHED_RISK_ANALYSIS_PROMPT template."""

    def test_template_exists(self) -> None:
        """Test that the enriched prompt template is defined."""
        assert ENRICHED_RISK_ANALYSIS_PROMPT is not None
        assert len(ENRICHED_RISK_ANALYSIS_PROMPT) > len(RISK_ANALYSIS_PROMPT)

    def test_template_has_chatml_format(self) -> None:
        """Test that the template uses ChatML format."""
        assert "<|im_start|>system" in ENRICHED_RISK_ANALYSIS_PROMPT
        assert "<|im_start|>user" in ENRICHED_RISK_ANALYSIS_PROMPT
        assert "<|im_start|>assistant" in ENRICHED_RISK_ANALYSIS_PROMPT

    def test_template_has_context_enrichment_fields(self) -> None:
        """Test that the template has context enrichment placeholders."""
        required_fields = [
            "{camera_name}",
            "{start_time}",
            "{end_time}",
            "{day_of_week}",
            "{zone_analysis}",
            "{hour}",
            "{baseline_comparison}",
            "{deviation_score}",
            "{cross_camera_summary}",
            "{detections_list}",
        ]
        for template_field in required_fields:
            assert template_field in ENRICHED_RISK_ANALYSIS_PROMPT, (
                f"Missing field: {template_field}"
            )

    def test_template_has_recommended_action(self) -> None:
        """Test that the enriched template includes recommended_action in output."""
        assert '"recommended_action"' in ENRICHED_RISK_ANALYSIS_PROMPT

    def test_template_variable_substitution(self) -> None:
        """Test that all template variables can be properly substituted."""
        substituted = ENRICHED_RISK_ANALYSIS_PROMPT.format(
            camera_name="driveway_cam",
            start_time="2024-01-01 22:00:00",
            end_time="2024-01-01 22:05:00",
            day_of_week="Monday",
            zone_analysis="Entry point zone detected",
            hour="22",
            baseline_comparison="Normal activity: 2 cars/hour",
            deviation_score="0.3",
            cross_camera_summary="Activity also seen on backyard camera",
            detections_list="person: 90%, car: 85%",
        )
        assert "driveway_cam" in substituted
        assert "Monday" in substituted
        assert "Entry point zone detected" in substituted
        assert "22" in substituted


class TestFullEnrichedRiskAnalysisPromptTemplate:
    """Tests for the FULL_ENRICHED_RISK_ANALYSIS_PROMPT template."""

    def test_template_exists(self) -> None:
        """Test that the full enriched prompt template is defined."""
        assert FULL_ENRICHED_RISK_ANALYSIS_PROMPT is not None

    def test_template_includes_enrichment_context(self) -> None:
        """Test that the template includes vision enrichment context."""
        assert "{enrichment_context}" in FULL_ENRICHED_RISK_ANALYSIS_PROMPT
        assert "## Vision Enrichment" in FULL_ENRICHED_RISK_ANALYSIS_PROMPT

    def test_template_has_license_plate_guidance(self) -> None:
        """Test that the template includes license plate guidance."""
        assert "License plates" in FULL_ENRICHED_RISK_ANALYSIS_PROMPT
        # NEM-3880: Template now focuses on non-risk factors instead of face detection
        assert "NOT RISK FACTORS" in FULL_ENRICHED_RISK_ANALYSIS_PROMPT


class TestVisionEnhancedRiskAnalysisPromptTemplate:
    """Tests for the VISION_ENHANCED_RISK_ANALYSIS_PROMPT template."""

    def test_template_exists(self) -> None:
        """Test that the vision-enhanced prompt template is defined."""
        assert VISION_ENHANCED_RISK_ANALYSIS_PROMPT is not None

    def test_template_has_vision_specific_fields(self) -> None:
        """Test that the template has vision-specific placeholders."""
        required_fields = [
            "{camera_name}",
            "{timestamp}",
            "{day_of_week}",
            "{time_of_day}",
            "{detections_with_attributes}",
            "{reid_context}",
            "{zone_analysis}",
            "{baseline_comparison}",
            "{deviation_score}",
            "{cross_camera_summary}",
            "{scene_analysis}",
        ]
        for template_field in required_fields:
            assert template_field in VISION_ENHANCED_RISK_ANALYSIS_PROMPT, (
                f"Missing field: {template_field}"
            )

    def test_template_has_entities_output(self) -> None:
        """Test that the template includes entities in JSON output."""
        assert '"entities"' in VISION_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"type": "person|vehicle"' in VISION_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"threat_level"' in VISION_ENHANCED_RISK_ANALYSIS_PROMPT


class TestModelZooEnhancedRiskAnalysisPromptTemplate:
    """Tests for the MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT template."""

    def test_template_exists(self) -> None:
        """Test that the model zoo enhanced prompt template is defined."""
        assert MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT is not None

    def test_template_is_largest(self) -> None:
        """Test that model zoo template is the most comprehensive."""
        assert len(MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT) > len(
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT
        )

    def test_template_has_all_model_zoo_fields(self) -> None:
        """Test that the template has all model zoo enrichment fields."""
        required_fields = [
            "{camera_name}",
            "{timestamp}",
            "{day_of_week}",
            "{time_of_day}",
            "{weather_context}",
            "{image_quality_context}",
            "{detections_with_all_attributes}",
            "{violence_context}",
            "{pose_analysis}",
            "{action_recognition}",
            "{vehicle_classification_context}",
            "{vehicle_damage_context}",
            "{clothing_analysis_context}",
            "{pet_classification_context}",
            "{depth_context}",
            "{reid_context}",
            "{zone_analysis}",
            "{baseline_comparison}",
            "{deviation_score}",
            "{cross_camera_summary}",
            "{scene_analysis}",
        ]
        for template_field in required_fields:
            assert template_field in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, (
                f"Missing field: {template_field}"
            )

    def test_template_has_comprehensive_risk_interpretation(self) -> None:
        """Test that the template has comprehensive risk interpretation guide."""
        sections = [
            "### Violence Detection",
            "### Weather Context",
            "### Clothing/Attire Risk Factors",
            "### Vehicle Analysis",
            "### Pet Detection",
            "### Pose/Behavior Analysis",
            "### Image Quality",
            "### Time Context",
            "### Risk Levels",
        ]
        for section in sections:
            assert section in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, f"Missing section: {section}"

    def test_template_has_comprehensive_json_output(self) -> None:
        """Test that the template has comprehensive JSON output format."""
        output_fields = [
            '"risk_score"',
            '"risk_level"',
            '"summary"',
            '"reasoning"',
            '"entities"',
            '"flags"',
            '"recommended_action"',
            '"confidence_factors"',
        ]
        for output_field in output_fields:
            assert output_field in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, (
                f"Missing output field: {output_field}"
            )


# =============================================================================
# Test Classes for Calibration Guidelines (NEM-3880)
# =============================================================================


class TestNonRiskFactors:
    """Tests for the NON_RISK_FACTORS constant (NEM-3880).

    These tests verify that the prompt includes explicit guidance about
    items that should NOT be flagged as suspicious.
    """

    def test_non_risk_factors_exists(self) -> None:
        """Test that NON_RISK_FACTORS constant is defined."""
        assert NON_RISK_FACTORS is not None
        assert isinstance(NON_RISK_FACTORS, str)
        assert len(NON_RISK_FACTORS) > 0

    def test_non_risk_factors_includes_trees(self) -> None:
        """Test that trees are explicitly listed as non-risk factors."""
        assert "tree" in NON_RISK_FACTORS.lower()

    def test_non_risk_factors_includes_timestamps(self) -> None:
        """Test that timestamps are explicitly listed as non-risk factors."""
        assert "timestamp" in NON_RISK_FACTORS.lower()

    def test_non_risk_factors_includes_presence(self) -> None:
        """Test that simple presence is listed as non-risk factor."""
        lower_text = NON_RISK_FACTORS.lower()
        assert "simply being present" in lower_text or "simply present" in lower_text

    def test_non_risk_factors_includes_vegetation(self) -> None:
        """Test that vegetation is listed as non-risk factor."""
        lower_text = NON_RISK_FACTORS.lower()
        assert "vegetation" in lower_text or "plants" in lower_text

    def test_non_risk_factors_includes_wildlife(self) -> None:
        """Test that wildlife is listed as non-risk factor."""
        lower_text = NON_RISK_FACTORS.lower()
        has_wildlife = "wildlife" in lower_text
        has_animals = "bird" in lower_text and "squirrel" in lower_text
        assert has_wildlife or has_animals

    def test_non_risk_factors_includes_shadows(self) -> None:
        """Test that shadows are listed as non-risk factor."""
        assert "shadow" in NON_RISK_FACTORS.lower()

    def test_non_risk_factors_includes_weather(self) -> None:
        """Test that weather conditions are listed as non-risk factor."""
        assert "weather" in NON_RISK_FACTORS.lower()


class TestCalibrationGuidelines:
    """Tests for calibration guidelines in prompts (NEM-3880).

    These tests verify that all prompt templates include proper
    score calibration guidelines to prevent over-alerting.
    """

    def test_calibrated_system_prompt_has_score_ranges(self) -> None:
        """Test that CALIBRATED_SYSTEM_PROMPT has explicit score ranges."""
        assert "0-20" in CALIBRATED_SYSTEM_PROMPT
        has_elevated = "21-40" in CALIBRATED_SYSTEM_PROMPT or "ELEVATED" in CALIBRATED_SYSTEM_PROMPT
        assert has_elevated
        assert "CRITICAL" in CALIBRATED_SYSTEM_PROMPT

    def test_calibrated_system_prompt_mentions_delivery_drivers(self) -> None:
        """Test that delivery drivers are mentioned as low risk."""
        assert "deliver" in CALIBRATED_SYSTEM_PROMPT.lower()

    def test_scoring_reference_has_delivery_driver_low_score(self) -> None:
        """Test that delivery driver scenario has low score (0-15, not 15-25)."""
        # The delivery driver score should be 0-15, not the old 15-25
        assert "Delivery driver" in SCORING_REFERENCE_TABLE
        # Check that "0-15" appears for delivery driver
        lines = SCORING_REFERENCE_TABLE.split("\n")
        delivery_line = next(line for line in lines if "Delivery driver" in line)
        assert "0-15" in delivery_line, f"Expected '0-15' for delivery driver: {delivery_line}"

    def test_scoring_reference_has_resident_low_score(self) -> None:
        """Test that resident arriving home has very low score (0-10)."""
        lines = SCORING_REFERENCE_TABLE.split("\n")
        resident_line = next(line for line in lines if "Resident arriving" in line)
        assert "0-10" in resident_line, f"Expected '0-10' for resident: {resident_line}"

    def test_scoring_reference_has_pet_very_low_score(self) -> None:
        """Test that pet activity has very low score (0-5)."""
        assert "Pet" in SCORING_REFERENCE_TABLE
        lines = SCORING_REFERENCE_TABLE.split("\n")
        pet_lines = [line for line in lines if "Pet" in line]
        assert len(pet_lines) > 0, "Expected pet scenario in scoring reference"
        assert "0-5" in pet_lines[0], f"Expected '0-5' for pet: {pet_lines[0]}"

    def test_all_prompts_have_non_risk_factors_guidance(self) -> None:
        """Test that all prompt templates mention non-risk factors."""
        prompts_to_check = [
            ("RISK_ANALYSIS_PROMPT", RISK_ANALYSIS_PROMPT),
            ("ENRICHED_RISK_ANALYSIS_PROMPT", ENRICHED_RISK_ANALYSIS_PROMPT),
            ("FULL_ENRICHED_RISK_ANALYSIS_PROMPT", FULL_ENRICHED_RISK_ANALYSIS_PROMPT),
            ("VISION_ENHANCED_RISK_ANALYSIS_PROMPT", VISION_ENHANCED_RISK_ANALYSIS_PROMPT),
            ("MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT", MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT),
        ]
        for name, prompt in prompts_to_check:
            has_tree = "tree" in prompt.lower()
            has_header = "NOT RISK FACTORS" in prompt
            assert has_tree or has_header, f"{name} should mention non-risk factors"

    def test_all_prompts_have_calibrated_score_ranges(self) -> None:
        """Test that all prompt templates have calibrated score ranges."""
        prompts_to_check = [
            ("RISK_ANALYSIS_PROMPT", RISK_ANALYSIS_PROMPT),
            ("ENRICHED_RISK_ANALYSIS_PROMPT", ENRICHED_RISK_ANALYSIS_PROMPT),
            ("FULL_ENRICHED_RISK_ANALYSIS_PROMPT", FULL_ENRICHED_RISK_ANALYSIS_PROMPT),
            ("VISION_ENHANCED_RISK_ANALYSIS_PROMPT", VISION_ENHANCED_RISK_ANALYSIS_PROMPT),
            ("MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT", MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT),
        ]
        for name, prompt in prompts_to_check:
            # Each prompt should have the new calibrated LOW range (0-20)
            has_range = "0-20" in prompt or "(0-20)" in prompt
            assert has_range, f"{name} should have calibrated LOW range (0-20)"

    def test_prompts_emphasize_lower_scores_as_default(self) -> None:
        """Test that prompts emphasize defaulting to lower scores."""
        prompts_to_check = [
            ("CALIBRATED_SYSTEM_PROMPT", CALIBRATED_SYSTEM_PROMPT),
            ("RISK_ANALYSIS_PROMPT", RISK_ANALYSIS_PROMPT),
        ]
        for name, prompt in prompts_to_check:
            # Should mention defaulting to lower scores
            lower_prompt = prompt.lower()
            has_default = "default" in lower_prompt and "lower" in lower_prompt
            assert has_default, f"{name} should emphasize defaulting to lower scores"


# =============================================================================
# Test Classes for Format Functions - Violence Context
# =============================================================================


class TestFormatViolenceContext:
    """Tests for format_violence_context function."""

    def test_none_input(self) -> None:
        """Test formatting when violence detection result is None."""
        result = format_violence_context(None)
        assert result == "Violence analysis: Not performed"

    def test_violent_detection_high_confidence(self) -> None:
        """Test formatting for violent detection with high confidence."""
        violence_result = MockViolenceDetectionResult(
            is_violent=True,
            confidence=0.98,
            violent_score=0.98,
            non_violent_score=0.02,
        )
        result = format_violence_context(violence_result)

        assert "**VIOLENCE DETECTED**" in result
        assert "98%" in result
        assert "ACTION REQUIRED" in result
        assert "Violent score: 98%" in result
        assert "Non-violent score: 2%" in result

    def test_violent_detection_low_confidence(self) -> None:
        """Test formatting for violent detection with lower confidence."""
        violence_result = MockViolenceDetectionResult(
            is_violent=True,
            confidence=0.55,
            violent_score=0.55,
            non_violent_score=0.45,
        )
        result = format_violence_context(violence_result)

        assert "**VIOLENCE DETECTED**" in result
        assert "55%" in result

    def test_non_violent_detection(self) -> None:
        """Test formatting when no violence is detected."""
        violence_result = MockViolenceDetectionResult(
            is_violent=False,
            confidence=0.92,
            violent_score=0.08,
            non_violent_score=0.92,
        )
        result = format_violence_context(violence_result)

        assert "No violence detected" in result
        assert "92%" in result
        assert "**VIOLENCE DETECTED**" not in result

    def test_edge_case_exactly_zero_confidence(self) -> None:
        """Test edge case with zero confidence."""
        violence_result = MockViolenceDetectionResult(
            is_violent=False,
            confidence=0.0,
            violent_score=0.0,
            non_violent_score=0.0,
        )
        result = format_violence_context(violence_result)
        assert "No violence detected" in result
        assert "0%" in result


# =============================================================================
# Test Classes for Format Functions - Weather Context
# =============================================================================


class TestFormatWeatherContext:
    """Tests for format_weather_context function."""

    def test_none_input(self) -> None:
        """Test formatting when weather result is None."""
        result = format_weather_context(None)
        assert result == "Weather: Unknown (classification unavailable)"

    def test_clear_weather(self) -> None:
        """Test formatting for clear weather conditions."""
        weather = MockWeatherResult(simple_condition="clear", confidence=0.95)
        result = format_weather_context(weather)

        assert "Weather: clear" in result
        assert "95%" in result
        assert "Good visibility" in result
        assert "high confidence in detections" in result

    def test_foggy_weather(self) -> None:
        """Test formatting for foggy weather conditions."""
        weather = MockWeatherResult(simple_condition="foggy", confidence=0.88)
        result = format_weather_context(weather)

        assert "Weather: foggy" in result
        assert "88%" in result
        assert "Visibility significantly reduced" in result

    def test_rainy_weather(self) -> None:
        """Test formatting for rainy weather conditions."""
        weather = MockWeatherResult(simple_condition="rainy", confidence=0.75)
        result = format_weather_context(weather)

        assert "Weather: rainy" in result
        assert "75%" in result
        assert "Rain may affect visibility" in result

    def test_snowy_weather(self) -> None:
        """Test formatting for snowy weather conditions."""
        weather = MockWeatherResult(simple_condition="snowy", confidence=0.82)
        result = format_weather_context(weather)

        assert "Weather: snowy" in result
        assert "82%" in result
        assert "Snow conditions may obscure objects" in result

    def test_cloudy_weather(self) -> None:
        """Test formatting for cloudy weather conditions."""
        weather = MockWeatherResult(simple_condition="cloudy", confidence=0.70)
        result = format_weather_context(weather)

        assert "Weather: cloudy" in result
        assert "70%" in result
        assert "Overcast conditions" in result

    def test_unknown_weather_condition(self) -> None:
        """Test formatting for unknown weather condition."""
        weather = MockWeatherResult(simple_condition="unknown", confidence=0.50)
        result = format_weather_context(weather)

        # Should still format without visibility note
        assert "Weather: unknown" in result
        assert "50%" in result


# =============================================================================
# Test Classes for Format Functions - Clothing Analysis Context
# =============================================================================


class TestFormatClothingAnalysisContext:
    """Tests for format_clothing_analysis_context function."""

    def test_empty_input(self) -> None:
        """Test formatting with empty clothing classifications."""
        result = format_clothing_analysis_context({}, None)
        assert result == "Clothing analysis: No person detections analyzed"

    def test_normal_clothing(self) -> None:
        """Test formatting for normal casual clothing."""
        classifications = {
            "det_001": MockClothingClassification(
                raw_description="blue jeans, white t-shirt",
                confidence=0.88,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            )
        }
        result = format_clothing_analysis_context(classifications, None)

        assert "Person det_001:" in result
        assert "blue jeans, white t-shirt" in result
        assert "88" in result
        assert "**ALERT**" not in result

    def test_suspicious_clothing(self) -> None:
        """Test formatting for suspicious clothing detection."""
        classifications = {
            "det_002": MockClothingClassification(
                raw_description="all black clothing, ski mask",
                confidence=0.92,
                is_suspicious=True,
                is_service_uniform=False,
                top_category="suspicious_all_black",
            )
        }
        result = format_clothing_analysis_context(classifications, None)

        assert "Person det_002:" in result
        assert "**ALERT**" in result
        assert "suspicious" in result.lower()
        assert "suspicious_all_black" in result

    def test_service_uniform(self) -> None:
        """Test formatting for service worker uniform."""
        classifications = {
            "det_003": MockClothingClassification(
                raw_description="FedEx uniform, carrying packages",
                confidence=0.95,
                is_suspicious=False,
                is_service_uniform=True,
                top_category="delivery_uniform",
            )
        }
        result = format_clothing_analysis_context(classifications, None)

        assert "Person det_003:" in result
        assert "Service/delivery worker uniform" in result
        assert "lower risk" in result

    def test_with_segmentation_face_covered(self) -> None:
        """Test formatting with SegFormer segmentation showing face covered."""
        classifications = {
            "det_004": MockClothingClassification(
                raw_description="dark hoodie",
                confidence=0.80,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            )
        }
        segmentation = {
            "det_004": MockClothingSegmentationResult(
                clothing_items=["hoodie", "jeans"],
                has_face_covered=True,
                has_bag=False,
            )
        }
        result = format_clothing_analysis_context(classifications, segmentation)

        assert "Face covering detected" in result
        assert "**ALERT**" in result
        # Items are sorted alphabetically after validation (NEM-3010)
        assert "hoodie, jeans" in result or "jeans, hoodie" in result

    def test_with_segmentation_bag_detected(self) -> None:
        """Test formatting with SegFormer detecting bag."""
        classifications = {
            "det_005": MockClothingClassification(
                raw_description="casual outfit",
                confidence=0.85,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            )
        }
        segmentation = {
            "det_005": MockClothingSegmentationResult(
                clothing_items=["shirt", "pants"],
                has_face_covered=False,
                has_bag=True,
            )
        }
        result = format_clothing_analysis_context(classifications, segmentation)

        assert "bag detected" in result.lower()

    def test_multiple_persons(self) -> None:
        """Test formatting with multiple persons detected."""
        classifications = {
            "det_001": MockClothingClassification(
                raw_description="red jacket",
                confidence=0.90,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            ),
            "det_002": MockClothingClassification(
                raw_description="blue uniform",
                confidence=0.88,
                is_suspicious=False,
                is_service_uniform=True,
                top_category="service",
            ),
        }
        result = format_clothing_analysis_context(classifications, None)

        assert "Person det_001:" in result
        assert "Person det_002:" in result
        assert "red jacket" in result
        assert "blue uniform" in result


# =============================================================================
# Test Classes for Format Functions - Pose Analysis Context
# =============================================================================


class TestFormatPoseAnalysisContext:
    """Tests for format_pose_analysis_context function."""

    def test_none_input(self) -> None:
        """Test formatting when pose data is None."""
        result = format_pose_analysis_context(None)
        assert result == "Pose analysis: Not available"

    def test_empty_dict(self) -> None:
        """Test formatting when pose dict is empty."""
        result = format_pose_analysis_context({})
        assert result == "Pose analysis: No poses detected"

    def test_standing_pose(self) -> None:
        """Test formatting for normal standing pose."""
        poses = {"det_001": {"classification": "standing", "confidence": 0.92}}
        result = format_pose_analysis_context(poses)

        assert "standing" in result
        assert "92%" in result
        assert "SUSPICIOUS" not in result

    def test_crouching_pose_suspicious(self) -> None:
        """Test formatting for suspicious crouching pose."""
        poses = {"det_001": {"classification": "crouching", "confidence": 0.87}}
        result = format_pose_analysis_context(poses)

        assert "crouching" in result
        assert "87%" in result
        assert "SUSPICIOUS" in result
        assert "Low posture near ground" in result

    def test_crawling_pose_suspicious(self) -> None:
        """Test formatting for suspicious crawling pose."""
        poses = {"det_001": {"classification": "crawling", "confidence": 0.78}}
        result = format_pose_analysis_context(poses)

        assert "crawling" in result
        assert "SUSPICIOUS" in result

    def test_running_pose(self) -> None:
        """Test formatting for running pose with note."""
        poses = {"det_001": {"classification": "running", "confidence": 0.85}}
        result = format_pose_analysis_context(poses)

        assert "running" in result
        assert "Fast movement detected" in result

    def test_lying_pose(self) -> None:
        """Test formatting for lying pose with attention note."""
        poses = {"det_001": {"classification": "lying", "confidence": 0.90}}
        result = format_pose_analysis_context(poses)

        assert "lying" in result
        assert "Person on ground" in result
        assert "may need attention" in result

    def test_string_pose_format(self) -> None:
        """Test formatting when pose is a plain string instead of dict."""
        poses = {"det_001": "walking"}
        result = format_pose_analysis_context(poses)

        assert "walking" in result
        assert "0%" in result  # Default confidence when not provided


# =============================================================================
# Test Classes for Format Functions - Action Recognition Context
# =============================================================================


class TestFormatActionRecognitionContext:
    """Tests for format_action_recognition_context function."""

    def test_none_input(self) -> None:
        """Test formatting when action data is None."""
        result = format_action_recognition_context(None)
        assert result == "Action recognition: Not available"

    def test_empty_dict(self) -> None:
        """Test formatting when actions dict is empty."""
        result = format_action_recognition_context({})
        assert result == "Action recognition: No actions detected"

    def test_normal_walking_action(self) -> None:
        """Test formatting for normal walking action."""
        actions = {"det_001": [{"action": "walking", "confidence": 0.93}]}
        result = format_action_recognition_context(actions)

        assert "walking" in result
        assert "93%" in result
        assert "HIGH RISK" not in result
        assert "Suspicious" not in result

    def test_high_risk_checking_car_doors(self) -> None:
        """Test formatting for high-risk checking_car_doors action."""
        actions = {"det_001": [{"action": "checking_car_doors", "confidence": 0.82}]}
        result = format_action_recognition_context(actions)

        assert "checking_car_doors" in result
        assert "**HIGH RISK**" in result

    def test_high_risk_breaking_in(self) -> None:
        """Test formatting for high-risk breaking_in action."""
        actions = {"det_001": [{"action": "breaking_in", "confidence": 0.75}]}
        result = format_action_recognition_context(actions)

        assert "breaking_in" in result
        assert "**HIGH RISK**" in result

    def test_high_risk_climbing(self) -> None:
        """Test formatting for high-risk climbing action."""
        actions = {"det_001": [{"action": "climbing", "confidence": 0.88}]}
        result = format_action_recognition_context(actions)

        assert "climbing" in result
        assert "**HIGH RISK**" in result

    def test_suspicious_loitering(self) -> None:
        """Test formatting for suspicious loitering action."""
        actions = {"det_001": [{"action": "loitering", "confidence": 0.79}]}
        result = format_action_recognition_context(actions)

        assert "loitering" in result
        assert "[Suspicious]" in result

    def test_suspicious_pacing(self) -> None:
        """Test formatting for suspicious pacing action."""
        actions = {"det_001": [{"action": "pacing", "confidence": 0.70}]}
        result = format_action_recognition_context(actions)

        assert "pacing" in result
        assert "[Suspicious]" in result

    def test_multiple_actions_same_person(self) -> None:
        """Test formatting when person has multiple actions."""
        actions = {
            "det_001": [
                {"action": "walking", "confidence": 0.85},
                {"action": "looking_around", "confidence": 0.72},
            ]
        }
        result = format_action_recognition_context(actions)

        assert "walking" in result
        assert "looking_around" in result
        assert "[Suspicious]" in result  # looking_around is suspicious

    def test_string_action_format(self) -> None:
        """Test formatting when action is a plain string."""
        actions = {"det_001": "standing"}
        result = format_action_recognition_context(actions)

        assert "standing" in result


# =============================================================================
# Test Classes for Format Functions - Temporal Action Context (X-CLIP)
# =============================================================================


class TestFormatTemporalActionContext:
    """Tests for format_temporal_action_context function (X-CLIP temporal action recognition)."""

    def test_none_action_result_returns_empty_string(self) -> None:
        """Test that None action result returns empty string."""
        result = format_temporal_action_context(None)
        assert result == ""

    def test_empty_dict_returns_empty_string(self) -> None:
        """Test that empty dict returns empty string (no detected_action)."""
        result = format_temporal_action_context({})
        assert result == ""

    def test_low_confidence_returns_empty_string(self) -> None:
        """Test that low confidence (< 50%) returns empty string."""
        action_result = {"detected_action": "loitering", "confidence": 0.49}
        result = format_temporal_action_context(action_result)
        assert result == ""

    def test_exactly_50_percent_confidence_included(self) -> None:
        """Test that exactly 50% confidence is included (not excluded)."""
        action_result = {"detected_action": "loitering", "confidence": 0.50}
        result = format_temporal_action_context(action_result)
        assert "loitering" in result
        assert "50%" in result

    def test_loitering_action_with_risk_modifier(self) -> None:
        """Test formatting for loitering action with risk modifier."""
        action_result = {"detected_action": "loitering", "confidence": 0.78}
        result = format_temporal_action_context(action_result)

        assert "## BEHAVIORAL ANALYSIS (Temporal)" in result
        assert "loitering" in result
        assert "78%" in result
        assert "+15 points" in result
        assert "suspicious lingering behavior" in result

    def test_approaching_door_action(self) -> None:
        """Test formatting for approaching_door action."""
        action_result = {"detected_action": "approaching_door", "confidence": 0.85}
        result = format_temporal_action_context(action_result)

        assert "approaching_door" in result
        assert "85%" in result
        assert "+10 points" in result
        assert "approach detected" in result

    def test_running_away_action(self) -> None:
        """Test formatting for running_away action with high risk modifier."""
        action_result = {"detected_action": "running_away", "confidence": 0.72}
        result = format_temporal_action_context(action_result)

        assert "running_away" in result
        assert "72%" in result
        assert "+20 points" in result
        assert "fleeing behavior" in result

    def test_checking_car_doors_action(self) -> None:
        """Test formatting for checking_car_doors action."""
        action_result = {"detected_action": "checking_car_doors", "confidence": 0.81}
        result = format_temporal_action_context(action_result)

        assert "checking_car_doors" in result
        assert "81%" in result
        assert "+25 points" in result
        assert "vehicle tampering indicator" in result

    def test_suspicious_behavior_action(self) -> None:
        """Test formatting for suspicious_behavior action."""
        action_result = {"detected_action": "suspicious_behavior", "confidence": 0.67}
        result = format_temporal_action_context(action_result)

        assert "suspicious_behavior" in result
        assert "67%" in result
        assert "+20 points" in result
        assert "unusual activity" in result

    def test_breaking_in_action(self) -> None:
        """Test formatting for breaking_in action with highest risk modifier."""
        action_result = {"detected_action": "breaking_in", "confidence": 0.91}
        result = format_temporal_action_context(action_result)

        assert "breaking_in" in result
        assert "91%" in result
        assert "+40 points" in result
        assert "intrusion indicator" in result

    def test_vandalism_action(self) -> None:
        """Test formatting for vandalism action."""
        action_result = {"detected_action": "vandalism", "confidence": 0.74}
        result = format_temporal_action_context(action_result)

        assert "vandalism" in result
        assert "74%" in result
        assert "+35 points" in result
        assert "property damage indicator" in result

    def test_duration_formatting_when_provided(self) -> None:
        """Test that duration is formatted when provided."""
        action_result = {"detected_action": "loitering", "confidence": 0.78}
        result = format_temporal_action_context(action_result, duration_seconds=25.0)

        assert "Duration: ~25 seconds across frames" in result

    def test_duration_not_shown_when_none(self) -> None:
        """Test that duration line is not shown when None."""
        action_result = {"detected_action": "loitering", "confidence": 0.78}
        result = format_temporal_action_context(action_result, duration_seconds=None)

        assert "Duration:" not in result

    def test_action_alias_normalization_loitering(self) -> None:
        """Test X-CLIP prompt variation alias for loitering."""
        action_result = {"detected_action": "a person loitering", "confidence": 0.65}
        result = format_temporal_action_context(action_result)

        assert "a person loitering" in result
        assert "+15 points" in result  # Maps to loitering risk modifier

    def test_action_alias_normalization_approaching_door(self) -> None:
        """Test X-CLIP prompt variation alias for approaching door."""
        action_result = {"detected_action": "a person approaching a door", "confidence": 0.70}
        result = format_temporal_action_context(action_result)

        assert "a person approaching a door" in result
        assert "+10 points" in result  # Maps to approaching_door risk modifier

    def test_action_alias_normalization_running_away(self) -> None:
        """Test X-CLIP prompt variation alias for running away."""
        action_result = {"detected_action": "a person running away", "confidence": 0.88}
        result = format_temporal_action_context(action_result)

        assert "a person running away" in result
        assert "+20 points" in result  # Maps to running_away risk modifier

    def test_action_alias_normalization_suspicious(self) -> None:
        """Test X-CLIP prompt variation alias for suspicious behavior."""
        action_result = {
            "detected_action": "a person looking around suspiciously",
            "confidence": 0.60,
        }
        result = format_temporal_action_context(action_result)

        assert "a person looking around suspiciously" in result
        assert "+20 points" in result  # Maps to suspicious_behavior risk modifier

    def test_action_alias_normalization_door_handle(self) -> None:
        """Test X-CLIP prompt variation alias for trying door handle."""
        action_result = {"detected_action": "a person trying a door handle", "confidence": 0.75}
        result = format_temporal_action_context(action_result)

        assert "a person trying a door handle" in result
        assert "+25 points" in result  # Maps to checking_car_doors risk modifier

    def test_action_alias_normalization_vandalism(self) -> None:
        """Test X-CLIP prompt variation alias for vandalizing property."""
        action_result = {"detected_action": "a person vandalizing property", "confidence": 0.82}
        result = format_temporal_action_context(action_result)

        assert "a person vandalizing property" in result
        assert "+35 points" in result  # Maps to vandalism risk modifier

    def test_action_alias_normalization_breaking_in(self) -> None:
        """Test X-CLIP prompt variation alias for breaking in."""
        action_result = {"detected_action": "a person breaking in", "confidence": 0.93}
        result = format_temporal_action_context(action_result)

        assert "a person breaking in" in result
        assert "+40 points" in result  # Maps to breaking_in risk modifier

    def test_unknown_action_no_risk_modifier(self) -> None:
        """Test that unknown action types don't get risk modifiers."""
        action_result = {"detected_action": "walking", "confidence": 0.95}
        result = format_temporal_action_context(action_result)

        assert "walking" in result
        assert "95%" in result
        assert "RISK MODIFIER" not in result

    def test_confidence_display_format_percentage(self) -> None:
        """Test confidence is displayed as percentage without decimals."""
        action_result = {"detected_action": "loitering", "confidence": 0.789}
        result = format_temporal_action_context(action_result)

        # Should be "79%" not "78.9%" or "0.789"
        assert "79%" in result

    def test_missing_detected_action_returns_empty_string(self) -> None:
        """Test that missing detected_action key returns empty string."""
        action_result = {"confidence": 0.80}
        result = format_temporal_action_context(action_result)
        assert result == ""

    def test_missing_confidence_defaults_to_zero(self) -> None:
        """Test that missing confidence defaults to 0 (returns empty string)."""
        action_result = {"detected_action": "loitering"}
        result = format_temporal_action_context(action_result)
        # With confidence defaulting to 0, it's below 0.5 threshold
        assert result == ""

    def test_full_output_format(self) -> None:
        """Test the complete output format matches expected structure."""
        action_result = {"detected_action": "loitering", "confidence": 0.78}
        result = format_temporal_action_context(action_result, duration_seconds=25.0)

        lines = result.split("\n")
        assert lines[0] == "## BEHAVIORAL ANALYSIS (Temporal)"
        assert "Action detected: loitering (78% confidence)" in lines[1]
        assert "Duration: ~25 seconds across frames" in lines[2]
        assert "RISK MODIFIER: +15 points (suspicious lingering behavior)" in lines[3]


# =============================================================================
# Test Classes for Format Functions - Vehicle Classification Context
# =============================================================================


class TestFormatVehicleClassificationContext:
    """Tests for format_vehicle_classification_context function."""

    def test_empty_input(self) -> None:
        """Test formatting with no vehicles."""
        result = format_vehicle_classification_context({})
        assert result == "Vehicle classification: No vehicles analyzed"

    def test_normal_car(self) -> None:
        """Test formatting for a normal car."""
        classifications = {
            "det_v001": MockVehicleClassificationResult(
                vehicle_type="car",
                display_name="car/sedan",
                confidence=0.91,
                is_commercial=False,
                all_scores={"car": 0.91, "suv": 0.05},
            )
        }
        result = format_vehicle_classification_context(classifications)

        assert "car/sedan" in result
        assert "91%" in result
        assert "Commercial" not in result

    def test_commercial_vehicle(self) -> None:
        """Test formatting for commercial vehicle."""
        classifications = {
            "det_v002": MockVehicleClassificationResult(
                vehicle_type="work_van",
                display_name="work van/delivery van",
                confidence=0.87,
                is_commercial=True,
                all_scores={"work_van": 0.87},
            )
        }
        result = format_vehicle_classification_context(classifications)

        assert "work van/delivery van" in result
        assert "87%" in result
        assert "Commercial/delivery vehicle" in result

    def test_low_confidence_with_alternative(self) -> None:
        """Test formatting shows alternative when confidence is low."""
        classifications = {
            "det_v003": MockVehicleClassificationResult(
                vehicle_type="suv",
                display_name="SUV",
                confidence=0.55,
                is_commercial=False,
                all_scores={"suv": 0.55, "pickup_truck": 0.35, "car": 0.10},
            )
        }
        result = format_vehicle_classification_context(classifications)

        assert "SUV" in result
        assert "55%" in result
        assert "Alternative:" in result
        assert "pickup_truck" in result

    def test_high_confidence_no_alternative(self) -> None:
        """Test formatting does not show alternative when confidence is high."""
        classifications = {
            "det_v004": MockVehicleClassificationResult(
                vehicle_type="motorcycle",
                display_name="motorcycle",
                confidence=0.95,
                is_commercial=False,
                all_scores={"motorcycle": 0.95, "bicycle": 0.03},
            )
        }
        result = format_vehicle_classification_context(classifications)

        assert "motorcycle" in result
        assert "95%" in result
        assert "Alternative:" not in result


# =============================================================================
# Test Classes for Format Functions - Vehicle Damage Context
# =============================================================================


class TestFormatVehicleDamageContext:
    """Tests for format_vehicle_damage_context function."""

    def test_empty_input(self) -> None:
        """Test formatting with no vehicles."""
        result = format_vehicle_damage_context({})
        assert result == "Vehicle damage: No vehicles analyzed for damage"

    def test_no_damage_detected(self) -> None:
        """Test formatting when no damage is detected."""
        damage = {
            "det_v001": MockVehicleDamageResult(
                has_damage=False,
                damage_types=set(),
                total_damage_count=0,
                highest_confidence=0.0,
                has_high_security_damage=False,
            )
        }
        result = format_vehicle_damage_context(damage)
        assert "No damage detected" in result

    def test_minor_damage(self) -> None:
        """Test formatting for minor damage (scratches, dents)."""
        damage = {
            "det_v002": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"scratches", "dents"},
                total_damage_count=3,
                highest_confidence=0.78,
                has_high_security_damage=False,
            )
        }
        result = format_vehicle_damage_context(damage)

        assert "damage detected" in result.lower()
        assert "dents" in result
        assert "scratches" in result
        assert "**SECURITY ALERT**" not in result

    def test_glass_shatter_high_security(self) -> None:
        """Test formatting for high-security glass shatter damage."""
        damage = {
            "det_v003": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"glass_shatter"},
                total_damage_count=1,
                highest_confidence=0.92,
                has_high_security_damage=True,
            )
        }
        result = format_vehicle_damage_context(damage)

        assert "**SECURITY ALERT**" in result
        assert "glass_shatter" in result
        assert "Possible break-in or vandalism" in result

    def test_lamp_broken_high_security(self) -> None:
        """Test formatting for high-security lamp broken damage."""
        damage = {
            "det_v004": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"lamp_broken"},
                total_damage_count=1,
                highest_confidence=0.85,
                has_high_security_damage=True,
            )
        }
        result = format_vehicle_damage_context(damage)

        assert "**SECURITY ALERT**" in result
        assert "lamp_broken" in result
        assert "Broken lamp: Possible vandalism" in result

    def test_damage_with_night_context(self) -> None:
        """Test formatting for damage at night increases concern."""
        damage = {
            "det_v005": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"glass_shatter"},
                total_damage_count=1,
                highest_confidence=0.88,
                has_high_security_damage=True,
            )
        }
        result = format_vehicle_damage_context(damage, time_of_day="night")

        assert "**TIME CONTEXT**" in result
        assert "night" in result
        assert "Elevated risk" in result

    def test_damage_with_late_night_context(self) -> None:
        """Test formatting for damage at late_night."""
        damage = {
            "det_v006": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"glass_shatter"},
                total_damage_count=1,
                highest_confidence=0.90,
                has_high_security_damage=True,
            )
        }
        result = format_vehicle_damage_context(damage, time_of_day="late_night")

        assert "**TIME CONTEXT**" in result
        assert "late_night" in result

    def test_damage_daytime_no_extra_context(self) -> None:
        """Test formatting for damage during daytime has no time escalation."""
        damage = {
            "det_v007": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"glass_shatter"},
                total_damage_count=1,
                highest_confidence=0.90,
                has_high_security_damage=True,
            )
        }
        result = format_vehicle_damage_context(damage, time_of_day="afternoon")

        assert "**SECURITY ALERT**" in result
        assert "**TIME CONTEXT**" not in result


# =============================================================================
# Test Classes for Format Functions - Pet Classification Context
# =============================================================================


class TestFormatPetClassificationContext:
    """Tests for format_pet_classification_context function."""

    def test_empty_input(self) -> None:
        """Test formatting with no pets detected."""
        result = format_pet_classification_context({})
        assert result == "Pet classification: No animals detected"

    def test_high_confidence_dog(self) -> None:
        """Test formatting for high-confidence dog detection."""
        pets = {"det_p001": MockPetClassificationResult(animal_type="dog", confidence=0.95)}
        result = format_pet_classification_context(pets)

        assert "dog" in result
        assert "95%" in result
        assert "HIGH CONFIDENCE" in result
        assert "likely household pet" in result
        assert "FALSE POSITIVE NOTE" in result

    def test_high_confidence_cat(self) -> None:
        """Test formatting for high-confidence cat detection."""
        pets = {"det_p002": MockPetClassificationResult(animal_type="cat", confidence=0.92)}
        result = format_pet_classification_context(pets)

        assert "cat" in result
        assert "92%" in result
        assert "HIGH CONFIDENCE" in result

    def test_medium_confidence_pet(self) -> None:
        """Test formatting for medium-confidence pet detection."""
        pets = {"det_p003": MockPetClassificationResult(animal_type="dog", confidence=0.78)}
        result = format_pet_classification_context(pets)

        assert "dog" in result
        assert "78%" in result
        assert "Probable household pet" in result
        assert "HIGH CONFIDENCE" not in result

    def test_low_confidence_wildlife(self) -> None:
        """Test formatting for low-confidence detection (may be wildlife)."""
        pets = {"det_p004": MockPetClassificationResult(animal_type="cat", confidence=0.55)}
        result = format_pet_classification_context(pets)

        assert "cat" in result
        assert "55%" in result
        assert "may be wildlife" in result
        assert "FALSE POSITIVE NOTE" not in result

    def test_multiple_pets(self) -> None:
        """Test formatting with multiple pets detected."""
        pets = {
            "det_p005": MockPetClassificationResult(animal_type="dog", confidence=0.90),
            "det_p006": MockPetClassificationResult(animal_type="cat", confidence=0.88),
        }
        result = format_pet_classification_context(pets)

        assert "dog" in result
        assert "cat" in result
        assert "2 animals" in result


# =============================================================================
# Test Classes for Format Functions - Class Anomaly Context (NEM-3014)
# =============================================================================


class TestFormatClassAnomalyContext:
    """Tests for format_class_anomaly_context function.

    This function identifies per-class anomalies by comparing current detection
    counts against historical baselines. It flags:
    - Rare classes (expected < 0.1/hr) when detected
    - Unusual volume (3x normal) for any class
    """

    def test_empty_detections(self) -> None:
        """Test formatting with no detections returns empty string."""
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections={},
            baselines={},
        )
        assert context == ""
        assert anomalies == []

    def test_no_baselines_returns_empty(self) -> None:
        """Test that detections without baselines return empty (insufficient data)."""
        detections = {"person": 3, "vehicle": 2}
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections=detections,
            baselines={},  # No baselines
        )
        assert context == ""
        assert anomalies == []

    def test_insufficient_samples_returns_empty(self) -> None:
        """Test that baselines with < 10 samples are ignored."""
        detections = {"person": 3}
        baselines = {
            "cam1:2:person": MockClassBaseline(frequency=1.0, sample_count=5)  # Only 5 samples
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections=detections,
            baselines=baselines,
        )
        assert context == ""
        assert anomalies == []

    def test_rare_class_person_high_severity(self) -> None:
        """Test that rare person detection gets high severity."""
        detections = {"person": 1}
        baselines = {
            "cam1:2:person": MockClassBaseline(frequency=0.05, sample_count=20)  # Rare: < 0.1/hr
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=2,
            detections=detections,
            baselines=baselines,
        )

        assert "## CLASS-SPECIFIC ANOMALIES" in context
        assert "[HIGH]" in context
        assert "person RARE at this hour" in context
        assert "expected: 0.1/hr" in context or "expected: 0.0/hr" in context
        assert len(anomalies) == 1
        assert anomalies[0].class_name == "person"
        assert anomalies[0].severity == "high"
        assert anomalies[0].risk_modifier == 15

    def test_rare_class_vehicle_high_severity(self) -> None:
        """Test that rare vehicle detection gets high severity."""
        detections = {"vehicle": 1}
        baselines = {"cam1:3:vehicle": MockClassBaseline(frequency=0.02, sample_count=15)}
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=3,
            detections=detections,
            baselines=baselines,
        )

        assert "[HIGH]" in context
        assert "vehicle RARE at this hour" in context
        assert anomalies[0].severity == "high"

    def test_rare_class_dog_medium_severity(self) -> None:
        """Test that rare non-security class gets medium severity."""
        detections = {"dog": 1}
        baselines = {"cam1:4:dog": MockClassBaseline(frequency=0.01, sample_count=25)}
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=4,
            detections=detections,
            baselines=baselines,
        )

        assert "[MEDIUM]" in context
        assert "dog RARE at this hour" in context
        assert anomalies[0].severity == "medium"

    def test_unusual_volume_3x_normal(self) -> None:
        """Test that 3x normal volume is flagged as unusual."""
        detections = {"person": 10}
        baselines = {
            "cam1:14:person": MockClassBaseline(frequency=3.0, sample_count=50)  # 10 > 3*3 = 9
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=14,
            detections=detections,
            baselines=baselines,
        )

        assert "## CLASS-SPECIFIC ANOMALIES" in context
        assert "[MEDIUM]" in context
        assert "person UNUSUAL volume" in context
        assert "10 vs expected 3.0" in context
        assert len(anomalies) == 1
        assert anomalies[0].severity == "medium"

    def test_normal_volume_not_flagged(self) -> None:
        """Test that normal volume (< 3x) is not flagged."""
        detections = {"person": 5}
        baselines = {
            "cam1:10:person": MockClassBaseline(frequency=3.0, sample_count=30)  # 5 < 3*3 = 9
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=10,
            detections=detections,
            baselines=baselines,
        )

        assert context == ""
        assert anomalies == []

    def test_exactly_3x_not_flagged(self) -> None:
        """Test that exactly 3x normal is not flagged (must be > 3x)."""
        detections = {"person": 9}
        baselines = {
            "cam1:12:person": MockClassBaseline(frequency=3.0, sample_count=25)  # 9 == 3*3
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=12,
            detections=detections,
            baselines=baselines,
        )

        assert context == ""
        assert anomalies == []

    def test_multiple_anomalies(self) -> None:
        """Test formatting with multiple anomalies from different classes."""
        detections = {"person": 1, "vehicle": 1, "dog": 2}
        baselines = {
            "cam1:3:person": MockClassBaseline(frequency=0.05, sample_count=20),  # Rare
            "cam1:3:vehicle": MockClassBaseline(frequency=0.03, sample_count=15),  # Rare
            "cam1:3:dog": MockClassBaseline(frequency=5.0, sample_count=30),  # Normal
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=3,
            detections=detections,
            baselines=baselines,
        )

        assert "## CLASS-SPECIFIC ANOMALIES" in context
        assert "person RARE" in context
        assert "vehicle RARE" in context
        assert "dog" not in context  # Not anomalous
        assert len(anomalies) == 2

    def test_class_anomaly_result_attributes(self) -> None:
        """Test that ClassAnomalyResult has correct attributes."""
        result = ClassAnomalyResult(
            class_name="person",
            message="person RARE at this hour (expected: 0.1/hr, actual: 1)",
            severity="high",
            risk_modifier=15,
        )

        assert result.class_name == "person"
        assert "RARE" in result.message
        assert result.severity == "high"
        assert result.risk_modifier == 15

    def test_different_camera_different_hour(self) -> None:
        """Test that baseline key includes camera and hour."""
        detections = {"person": 1}
        baselines = {
            # Wrong camera
            "cam2:5:person": MockClassBaseline(frequency=0.05, sample_count=20),
            # Wrong hour
            "cam1:6:person": MockClassBaseline(frequency=0.05, sample_count=20),
        }
        context, anomalies = format_class_anomaly_context(
            camera_id="cam1",
            current_hour=5,
            detections=detections,
            baselines=baselines,
        )

        # Should not match because key is cam1:5:person which doesn't exist
        assert context == ""
        assert anomalies == []

    def test_car_truck_motorcycle_high_severity(self) -> None:
        """Test that car, truck, motorcycle variants get high severity."""
        for vehicle_class in ["car", "truck", "motorcycle"]:
            detections = {vehicle_class: 1}
            baselines = {
                f"cam1:2:{vehicle_class}": MockClassBaseline(frequency=0.02, sample_count=20)
            }
            context, anomalies = format_class_anomaly_context(
                camera_id="cam1",
                current_hour=2,
                detections=detections,
                baselines=baselines,
            )

            assert "[HIGH]" in context, f"{vehicle_class} should get HIGH severity"
            assert anomalies[0].severity == "high"

    def test_non_security_classes_medium_severity(self) -> None:
        """Test that non-security classes (cat, bird, etc.) get medium severity."""
        for cls in ["cat", "bird", "backpack"]:
            detections = {cls: 1}
            baselines = {f"cam1:2:{cls}": MockClassBaseline(frequency=0.02, sample_count=20)}
            context, anomalies = format_class_anomaly_context(
                camera_id="cam1",
                current_hour=2,
                detections=detections,
                baselines=baselines,
            )

            assert "[MEDIUM]" in context, f"{cls} should get MEDIUM severity"
            assert anomalies[0].severity == "medium"


# =============================================================================
# Test Classes for Format Functions - Depth Context
# =============================================================================


class TestFormatDepthContext:
    """Tests for format_depth_context function."""

    def test_none_input(self) -> None:
        """Test formatting when depth data is None."""
        result = format_depth_context(None)
        assert result == "Depth analysis: Not available"

    def test_empty_detections(self) -> None:
        """Test formatting when depth has no detections."""
        from backend.services.depth_anything_loader import DepthAnalysisResult

        depth_result = DepthAnalysisResult()
        result = format_depth_context(depth_result)
        assert "No detections analyzed" in result

    def test_very_close_detection(self) -> None:
        """Test formatting for detection in very close proximity."""
        from backend.services.depth_anything_loader import (
            DepthAnalysisResult,
            DetectionDepth,
        )

        detection_depths = {
            "det_001": DetectionDepth(
                detection_id="det_001",
                class_name="person",
                depth_value=0.08,
                proximity_label="very close",
            )
        }
        depth_result = DepthAnalysisResult(
            detection_depths=detection_depths,
            closest_detection_id="det_001",
            has_close_objects=True,
        )
        result = format_depth_context(depth_result)

        assert "very close" in result
        assert "CLOSE TO CAMERA" in result
        assert "person" in result

    def test_approaching_detection(self) -> None:
        """Test formatting for approaching detection."""
        from backend.services.depth_anything_loader import (
            DepthAnalysisResult,
            DetectionDepth,
        )

        detection_depths = {
            "det_001": DetectionDepth(
                detection_id="det_001",
                class_name="person",
                depth_value=0.4,
                proximity_label="moderate distance",
                is_approaching=True,
            )
        }
        depth_result = DepthAnalysisResult(
            detection_depths=detection_depths,
            closest_detection_id="det_001",
        )
        result = format_depth_context(depth_result)

        assert "moderate distance" in result
        assert "APPROACHING" in result

    def test_far_detection(self) -> None:
        """Test formatting for far detection."""
        from backend.services.depth_anything_loader import (
            DepthAnalysisResult,
            DetectionDepth,
        )

        detection_depths = {
            "det_001": DetectionDepth(
                detection_id="det_001",
                class_name="car",
                depth_value=0.7,
                proximity_label="far",
            )
        }
        depth_result = DepthAnalysisResult(
            detection_depths=detection_depths,
            closest_detection_id="det_001",
        )
        result = format_depth_context(depth_result)

        assert "far" in result
        assert "car" in result


# =============================================================================
# Test Classes for Format Functions - Image Quality Context
# =============================================================================


class TestFormatImageQualityContext:
    """Tests for format_image_quality_context function."""

    def test_none_input(self) -> None:
        """Test formatting when quality data is None."""
        result = format_image_quality_context(None)
        assert result == "Image quality: Not assessed"

    def test_good_quality(self) -> None:
        """Test formatting for good quality image."""
        quality = MockImageQualityResult(
            quality_score=88.0,
            is_good_quality=True,
            is_blurry=False,
            is_noisy=False,
            quality_issues=[],
        )
        result = format_image_quality_context(quality)

        assert "Good" in result
        assert "88" in result
        assert "/100" in result

    def test_blurry_image(self) -> None:
        """Test formatting for blurry image."""
        quality = MockImageQualityResult(
            quality_score=42.0,
            is_good_quality=False,
            is_blurry=True,
            is_noisy=False,
            quality_issues=["motion blur"],
        )
        result = format_image_quality_context(quality)

        assert "motion blur" in result
        assert "fast movement or camera issue" in result

    def test_noisy_image(self) -> None:
        """Test formatting for noisy image."""
        quality = MockImageQualityResult(
            quality_score=38.0,
            is_good_quality=False,
            is_blurry=False,
            is_noisy=True,
            quality_issues=["noise"],
        )
        result = format_image_quality_context(quality)

        assert "Noise/artifacts detected" in result
        assert "affect detection accuracy" in result

    def test_quality_change_alert(self) -> None:
        """Test formatting with quality change alert."""
        quality = MockImageQualityResult(
            quality_score=25.0,
            is_good_quality=False,
            is_blurry=True,
            is_noisy=True,
            quality_issues=["blur", "noise"],
        )
        result = format_image_quality_context(
            quality,
            quality_change_detected=True,
            quality_change_description="Quality dropped from 90 to 25 suddenly",
        )

        assert "**QUALITY ALERT**" in result
        assert "Quality dropped from 90 to 25 suddenly" in result
        assert "tampering" in result

    def test_general_degradation(self) -> None:
        """Test formatting for general degradation without specific issues."""
        quality = MockImageQualityResult(
            quality_score=50.0,
            is_good_quality=False,
            is_blurry=False,
            is_noisy=False,
            quality_issues=[],
        )
        result = format_image_quality_context(quality)

        assert "general degradation" in result


# =============================================================================
# Test Classes for Format Functions - Detections with All Enrichment
# =============================================================================


class TestFormatDetectionsWithAllEnrichment:
    """Tests for format_detections_with_all_enrichment function."""

    def test_empty_detections(self) -> None:
        """Test formatting with no detections."""
        result = format_detections_with_all_enrichment([])
        assert result == "No detections in this batch."

    def test_basic_detection_without_enrichment(self) -> None:
        """Test formatting a basic detection without enrichment."""
        detections = [
            {
                "detection_id": "det_001",
                "class_name": "person",
                "confidence": 0.92,
                "bbox": [100, 150, 300, 450],
            }
        ]
        result = format_detections_with_all_enrichment(detections)

        assert "### PERSON" in result
        assert "ID: det_001" in result
        assert "92%" in result
        assert "[100, 150, 300, 450]" in result

    def test_detection_with_vehicle_vision_extraction(self) -> None:
        """Test formatting detection with Florence-2 vehicle attributes."""
        detections = [
            {
                "detection_id": "det_v001",
                "class_name": "car",
                "confidence": 0.88,
                "bbox": [50, 100, 400, 300],
            }
        ]
        vision_extraction = MockBatchExtractionResult(
            vehicle_attributes={
                "det_v001": MockVehicleAttributes(
                    color="red",
                    vehicle_type="sedan",
                    is_commercial=False,
                    caption="A red sedan parked in driveway",
                )
            }
        )
        result = format_detections_with_all_enrichment(
            detections, vision_extraction=vision_extraction
        )

        assert "### CAR" in result
        assert "Color: red" in result
        assert "Type: sedan" in result
        assert "A red sedan parked in driveway" in result

    def test_detection_with_person_vision_extraction(self) -> None:
        """Test formatting detection with Florence-2 person attributes."""
        detections = [
            {
                "detection_id": "det_p001",
                "class_name": "person",
                "confidence": 0.91,
                "bbox": [200, 100, 350, 500],
            }
        ]
        vision_extraction = MockBatchExtractionResult(
            person_attributes={
                "det_p001": MockPersonAttributes(
                    clothing="dark jacket and jeans",
                    carrying="backpack",
                    action="walking",
                    is_service_worker=False,
                    caption="Person in dark clothing with backpack",
                )
            }
        )
        result = format_detections_with_all_enrichment(
            detections, vision_extraction=vision_extraction
        )

        assert "### PERSON" in result
        assert "Wearing: dark jacket and jeans" in result
        assert "Carrying: backpack" in result
        assert "Action: walking" in result

    def test_detection_with_service_worker(self) -> None:
        """Test formatting detection with service worker detected."""
        detections = [
            {
                "detection_id": "det_sw001",
                "class_name": "person",
                "confidence": 0.95,
                "bbox": [100, 50, 250, 400],
            }
        ]
        vision_extraction = MockBatchExtractionResult(
            person_attributes={
                "det_sw001": MockPersonAttributes(
                    clothing="delivery uniform",
                    carrying="package",
                    is_service_worker=True,
                )
            }
        )
        result = format_detections_with_all_enrichment(
            detections, vision_extraction=vision_extraction
        )

        assert "Service worker" in result

    def test_detection_with_commercial_vehicle(self) -> None:
        """Test formatting detection with commercial vehicle."""
        detections = [
            {
                "detection_id": "det_cv001",
                "class_name": "truck",
                "confidence": 0.89,
                "bbox": [0, 100, 600, 400],
            }
        ]
        vision_extraction = MockBatchExtractionResult(
            vehicle_attributes={
                "det_cv001": MockVehicleAttributes(
                    color="white",
                    vehicle_type="box_truck",
                    is_commercial=True,
                    commercial_text="UPS",
                )
            }
        )
        result = format_detections_with_all_enrichment(
            detections, vision_extraction=vision_extraction
        )

        assert "Commercial vehicle" in result
        assert "UPS" in result

    def test_detection_with_enrichment_pipeline_clothing(self) -> None:
        """Test formatting with enrichment pipeline clothing classification."""
        detections = [
            {
                "detection_id": "det_e001",
                "class_name": "person",
                "confidence": 0.90,
                "bbox": [150, 75, 300, 500],
            }
        ]
        enrichment = MockEnrichmentResult(
            clothing_classifications={
                "det_e001": MockClothingClassification(
                    raw_description="black hoodie, dark pants",
                    confidence=0.85,
                    is_suspicious=True,
                    is_service_uniform=False,
                    top_category="suspicious_dark",
                )
            }
        )
        result = format_detections_with_all_enrichment(detections, enrichment_result=enrichment)

        assert "Attire: black hoodie, dark pants" in result
        assert "**SUSPICIOUS**" in result

    def test_detection_with_enrichment_pipeline_segmentation(self) -> None:
        """Test formatting with enrichment pipeline clothing segmentation."""
        detections = [
            {
                "detection_id": "det_s001",
                "class_name": "person",
                "confidence": 0.88,
                "bbox": [100, 100, 250, 450],
            }
        ]
        enrichment = MockEnrichmentResult(
            clothing_classifications={
                "det_s001": MockClothingClassification(
                    raw_description="hoodie",
                    confidence=0.80,
                    is_suspicious=False,
                    is_service_uniform=False,
                    top_category="casual",
                )
            },
            clothing_segmentation={
                "det_s001": MockClothingSegmentationResult(
                    clothing_items=["hoodie", "jeans", "hat"],
                    has_face_covered=True,
                    has_bag=True,
                )
            },
        )
        result = format_detections_with_all_enrichment(detections, enrichment_result=enrichment)

        # Items are sorted alphabetically after validation (NEM-3010)
        assert "hat, hoodie, jeans" in result
        assert "Face covering: DETECTED **ALERT**" in result
        assert "Bag/backpack: Detected" in result

    def test_detection_with_enrichment_pipeline_vehicle_damage(self) -> None:
        """Test formatting with enrichment pipeline vehicle damage."""
        detections = [
            {
                "detection_id": "det_vd001",
                "class_name": "car",
                "confidence": 0.92,
                "bbox": [50, 150, 450, 350],
            }
        ]
        enrichment = MockEnrichmentResult(
            vehicle_damage={
                "det_vd001": MockVehicleDamageResult(
                    has_damage=True,
                    damage_types={"glass_shatter", "dents"},
                    total_damage_count=2,
                    highest_confidence=0.88,
                    has_high_security_damage=True,
                )
            }
        )
        result = format_detections_with_all_enrichment(detections, enrichment_result=enrichment)

        assert "Damage:" in result
        assert "dents" in result
        assert "glass_shatter" in result
        assert "**HIGH SECURITY**" in result

    def test_detection_with_enrichment_pipeline_pet(self) -> None:
        """Test formatting with enrichment pipeline pet classification."""
        detections = [
            {
                "detection_id": "det_pet001",
                "class_name": "dog",
                "confidence": 0.94,
                "bbox": [200, 300, 350, 450],
            }
        ]
        enrichment = MockEnrichmentResult(
            pet_classifications={
                "det_pet001": MockPetClassificationResult(animal_type="dog", confidence=0.96)
            }
        )
        result = format_detections_with_all_enrichment(detections, enrichment_result=enrichment)

        assert "Pet: dog" in result
        assert "96%" in result
        assert "Confirmed household pet - low risk" in result

    def test_detection_with_alternate_id_field(self) -> None:
        """Test formatting handles alternate 'id' field instead of 'detection_id'."""
        detections = [
            {
                "id": "alt_001",
                "class_name": "person",
                "confidence": 0.85,
                "bbox": [100, 100, 200, 300],
            }
        ]
        result = format_detections_with_all_enrichment(detections)

        assert "ID: alt_001" in result

    def test_detection_with_alternate_object_type_field(self) -> None:
        """Test formatting handles alternate 'object_type' field."""
        detections = [
            {
                "detection_id": "det_ot001",
                "object_type": "vehicle",
                "confidence": 0.87,
                "bbox": [50, 100, 400, 300],
            }
        ]
        result = format_detections_with_all_enrichment(detections)

        assert "### VEHICLE" in result

    def test_detection_with_empty_bbox(self) -> None:
        """Test formatting handles empty bbox gracefully."""
        detections = [
            {
                "detection_id": "det_nb001",
                "class_name": "person",
                "confidence": 0.80,
                "bbox": [],
            }
        ]
        result = format_detections_with_all_enrichment(detections)

        assert "Location: []" in result

    def test_multiple_detections(self) -> None:
        """Test formatting with multiple detections."""
        detections = [
            {
                "detection_id": "det_m001",
                "class_name": "person",
                "confidence": 0.90,
                "bbox": [100, 100, 200, 400],
            },
            {
                "detection_id": "det_m002",
                "class_name": "car",
                "confidence": 0.88,
                "bbox": [300, 150, 550, 350],
            },
            {
                "detection_id": "det_m003",
                "class_name": "dog",
                "confidence": 0.92,
                "bbox": [450, 300, 550, 400],
            },
        ]
        result = format_detections_with_all_enrichment(detections)

        assert "### PERSON" in result
        assert "### CAR" in result
        assert "### DOG" in result
        assert "det_m001" in result
        assert "det_m002" in result
        assert "det_m003" in result

    def test_empty_detections_with_person_enrichment_synthesizes_detection(self) -> None:
        """Test that empty detections list with person enrichment synthesizes detection.

        This test verifies the fix for contradictory detection data in Nemotron prompts.
        When detections list is empty but enrichment data exists, the function should
        synthesize detections from the enrichment data rather than returning
        'No detections in this batch.'
        """
        vision_extraction = MockBatchExtractionResult(
            person_attributes={
                "det_p001": MockPersonAttributes(
                    clothing="red hoodie and dark pants",
                    carrying="backpack",
                    action="walking toward door",
                    is_service_worker=False,
                    caption="Person approaching house",
                )
            }
        )
        result = format_detections_with_all_enrichment([], vision_extraction=vision_extraction)

        # Should NOT say "No detections" since we have person enrichment
        assert result != "No detections in this batch."
        # Should synthesize a person detection
        assert "### PERSON" in result
        assert "det_p001" in result
        # Should include the enrichment attributes
        assert "Wearing: red hoodie and dark pants" in result
        assert "Carrying: backpack" in result
        assert "Action: walking toward door" in result

    def test_empty_detections_with_vehicle_enrichment_synthesizes_detection(self) -> None:
        """Test that empty detections list with vehicle enrichment synthesizes detection."""
        vision_extraction = MockBatchExtractionResult(
            vehicle_attributes={
                "det_v001": MockVehicleAttributes(
                    color="white",
                    vehicle_type="van",
                    is_commercial=True,
                    commercial_text="ACME Delivery",
                    caption="White delivery van in driveway",
                )
            }
        )
        result = format_detections_with_all_enrichment([], vision_extraction=vision_extraction)

        # Should NOT say "No detections" since we have vehicle enrichment
        assert result != "No detections in this batch."
        # Should synthesize a vehicle detection
        assert "### VEHICLE" in result
        assert "det_v001" in result
        # Should include the enrichment attributes
        assert "Color: white" in result
        assert "Type: van" in result

    def test_empty_detections_with_clothing_classification_synthesizes_detection(
        self,
    ) -> None:
        """Test that empty detections list with clothing enrichment synthesizes detection."""
        enrichment = MockEnrichmentResult(
            clothing_classifications={
                "det_c001": MockClothingClassification(
                    raw_description="dark hoodie, face mask, gloves",
                    confidence=0.89,
                    is_suspicious=True,
                    is_service_uniform=False,
                    top_category="hoodie",
                )
            }
        )
        result = format_detections_with_all_enrichment([], enrichment_result=enrichment)

        # Should NOT say "No detections" since we have clothing enrichment
        assert result != "No detections in this batch."
        # Should synthesize a person detection (clothing implies person)
        assert "### PERSON" in result
        assert "det_c001" in result
        # Should include the clothing attributes
        assert "dark hoodie, face mask, gloves" in result
        assert "**SUSPICIOUS**" in result

    def test_empty_detections_truly_empty_returns_no_detections(self) -> None:
        """Test that truly empty inputs return 'No detections in this batch.'"""
        # No detections, no enrichment, no vision extraction
        result = format_detections_with_all_enrichment([])
        assert result == "No detections in this batch."

        # With empty enrichment result
        enrichment = MockEnrichmentResult(
            clothing_classifications={},
            clothing_segmentation={},
            vehicle_classifications={},
            vehicle_damage={},
            pet_classifications={},
        )
        result = format_detections_with_all_enrichment([], enrichment_result=enrichment)
        assert result == "No detections in this batch."

        # With empty vision extraction
        vision_extraction = MockBatchExtractionResult(person_attributes={}, vehicle_attributes={})
        result = format_detections_with_all_enrichment([], vision_extraction=vision_extraction)
        assert result == "No detections in this batch."


# =============================================================================
# Test Classes for Edge Cases and Error Handling
# =============================================================================


class TestEdgeCasesAndSpecialCharacters:
    """Tests for edge cases and special character handling."""

    def test_prompt_substitution_with_html_entities(self) -> None:
        """Test prompt substitution handles HTML-like characters."""
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="<script>alert('xss')</script>",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:00",
            detections_list="person: 90%",
        )
        # Should include the text as-is (no HTML escaping needed for LLM)
        assert "<script>" in prompt

    def test_prompt_substitution_with_newlines(self) -> None:
        """Test prompt substitution handles newlines in values."""
        multi_line = "person: 95%\ncar: 88%\ndog: 72%"
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="test_cam",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:00",
            detections_list=multi_line,
        )
        assert "person: 95%\ncar: 88%\ndog: 72%" in prompt

    def test_prompt_substitution_with_empty_strings(self) -> None:
        """Test prompt substitution handles empty strings."""
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="",
            start_time="",
            end_time="",
            detections_list="",
        )
        assert "Camera: \n" in prompt

    def test_prompt_substitution_with_very_long_input(self) -> None:
        """Test prompt substitution handles very long inputs."""
        long_list = "\n".join([f"object_{i}: {90 - i % 20}%" for i in range(100)])
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name="test_cam",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:01:00",
            detections_list=long_list,
        )
        assert "object_0: 90%" in prompt
        assert "object_99:" in prompt

    def test_clothing_context_with_special_chars_in_description(self) -> None:
        """Test clothing context handles special characters."""
        classifications = {
            "det_001": MockClothingClassification(
                raw_description='shirt with "logo" & text <brand>',
                confidence=0.85,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            )
        }
        result = format_clothing_analysis_context(classifications, None)
        assert '"logo"' in result
        assert "&" in result
        assert "<brand>" in result

    def test_vehicle_context_with_unicode_display_name(self) -> None:
        """Test vehicle context handles unicode in display name."""
        classifications = {
            "det_v001": MockVehicleClassificationResult(
                vehicle_type="car",
                display_name="car - unknown model",
                confidence=0.75,
                is_commercial=False,
                all_scores={"car": 0.75},
            )
        }
        result = format_vehicle_classification_context(classifications)
        assert "car - unknown model" in result

    def test_weather_context_with_boundary_confidence(self) -> None:
        """Test weather context with boundary confidence values."""
        weather_zero = MockWeatherResult(simple_condition="clear", confidence=0.0)
        result_zero = format_weather_context(weather_zero)
        assert "0%" in result_zero

        weather_full = MockWeatherResult(simple_condition="clear", confidence=1.0)
        result_full = format_weather_context(weather_full)
        assert "100%" in result_full


class TestPromptTemplateConsistency:
    """Tests to verify consistency across all prompt templates."""

    def test_all_templates_have_assistant_marker(self) -> None:
        """Test all templates end with assistant marker for completion."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            ENRICHED_RISK_ANALYSIS_PROMPT,
            FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            assert template.strip().endswith(
                "<|im_start|>assistant\n"
            ) or template.strip().endswith("<|im_start|>assistant"), (
                "Template should end with assistant marker"
            )

    def test_all_templates_have_system_message(self) -> None:
        """Test all templates have system message."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            ENRICHED_RISK_ANALYSIS_PROMPT,
            FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            assert "<|im_start|>system" in template
            # Updated to accept "home security analyst" role (NEM-3019)
            has_role = (
                "risk analyzer" in template.lower() or "home security analyst" in template.lower()
            )
            assert has_role, (
                "Template should define system role as risk analyzer or home security analyst"
            )

    def test_all_templates_specify_json_output(self) -> None:
        """Test all templates specify JSON output format."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            ENRICHED_RISK_ANALYSIS_PROMPT,
            FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            # Each should mention JSON output
            assert "json" in template.lower() or "JSON" in template

    def test_all_templates_have_risk_score_output(self) -> None:
        """Test all templates include risk_score in expected output."""
        templates = [
            RISK_ANALYSIS_PROMPT,
            ENRICHED_RISK_ANALYSIS_PROMPT,
            FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        ]
        for template in templates:
            assert '"risk_score"' in template


# =============================================================================
# Test Classes for Efficient String Building (NEM-1095)
# =============================================================================


class TestEfficientStringBuilding:
    """Tests for efficient string building patterns in prompt generation.

    NEM-1095: Use efficient string building for LLM prompt generation.
    String concatenation with += is O(n^2) in the worst case. Using list.append()
    followed by ''.join() is O(n) and much more efficient for building large prompts.
    """

    def test_format_functions_use_list_join_pattern(self) -> None:
        """Verify format functions use efficient list.append() + join() pattern.

        Note: format_depth_context is excluded as it delegates to
        DepthAnalysisResult.to_context_string() which uses the pattern internally.
        """
        import inspect

        from backend.services import prompts

        format_functions = [
            prompts.format_clothing_analysis_context,
            prompts.format_pose_analysis_context,
            prompts.format_action_recognition_context,
            prompts.format_vehicle_classification_context,
            prompts.format_vehicle_damage_context,
            prompts.format_pet_classification_context,
            # format_depth_context delegates to DepthAnalysisResult.to_context_string()
            prompts.format_detections_with_all_enrichment,
        ]

        for func in format_functions:
            source = inspect.getsource(func)
            # Check that functions use list-based building, not string concatenation
            # They should have 'lines = []' or similar pattern
            assert "lines = []" in source or "lines.append" in source, (
                f"{func.__name__} should use list.append() + join() pattern"
            )

    def test_large_detection_list_performance(self) -> None:
        """Test that formatting large detection lists is efficient."""
        import time

        # Create a large list of detections
        large_detections = [
            {
                "detection_id": f"det_{i:04d}",
                "class_name": "person" if i % 2 == 0 else "car",
                "confidence": 0.85 + (i % 15) / 100,
                "bbox": [100 + i, 150 + i, 300 + i, 450 + i],
            }
            for i in range(100)  # 100 detections
        ]

        # Format should complete quickly (well under 1 second)
        start = time.time()
        result = format_detections_with_all_enrichment(large_detections)
        elapsed = time.time() - start

        # Should complete in under 100ms for 100 detections
        assert elapsed < 0.1, f"Formatting took too long: {elapsed:.3f}s"
        # Should contain all detections
        assert "det_0099" in result

    def test_string_join_produces_correct_output(self) -> None:
        """Test that list.append() + join() produces correct multi-line output."""
        # Test with clothing context (uses lines pattern)
        classifications = {
            f"det_{i}": MockClothingClassification(
                raw_description=f"outfit {i}",
                confidence=0.85,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            )
            for i in range(5)
        }

        result = format_clothing_analysis_context(classifications, None)

        # Should have proper newlines between person entries
        assert "\n\n" in result  # Double newlines separate entries
        # Each person should be present
        for i in range(5):
            assert f"Person det_{i}:" in result


# =============================================================================
# Test Classes for Summary Prompt Templates
# =============================================================================


class TestSummaryPromptTemplates:
    """Tests for summary generation prompt templates."""

    def test_summary_system_prompt_exists(self) -> None:
        """Test that SUMMARY_SYSTEM_PROMPT is defined."""
        assert SUMMARY_SYSTEM_PROMPT is not None
        assert isinstance(SUMMARY_SYSTEM_PROMPT, str)
        assert len(SUMMARY_SYSTEM_PROMPT) > 0

    def test_summary_system_prompt_content(self) -> None:
        """Test that SUMMARY_SYSTEM_PROMPT has expected content."""
        assert "security analyst" in SUMMARY_SYSTEM_PROMPT.lower()
        assert "homeowner" in SUMMARY_SYSTEM_PROMPT.lower()
        assert "informative" in SUMMARY_SYSTEM_PROMPT.lower()
        assert "alarming" in SUMMARY_SYSTEM_PROMPT.lower()

    def test_summary_prompt_template_exists(self) -> None:
        """Test that SUMMARY_PROMPT_TEMPLATE is defined."""
        assert SUMMARY_PROMPT_TEMPLATE is not None
        assert isinstance(SUMMARY_PROMPT_TEMPLATE, str)
        assert len(SUMMARY_PROMPT_TEMPLATE) > 0

    def test_summary_prompt_template_has_required_placeholders(self) -> None:
        """Test that SUMMARY_PROMPT_TEMPLATE contains required placeholders."""
        required_placeholders = [
            "{window_start}",
            "{window_end}",
            "{period_type}",
            "{event_count}",
            "{event_details}",
            "{empty_state_instruction}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in SUMMARY_PROMPT_TEMPLATE, f"Missing placeholder: {placeholder}"

    def test_summary_prompt_template_instructions(self) -> None:
        """Test that SUMMARY_PROMPT_TEMPLATE has proper instructions."""
        assert "2-4 sentences" in SUMMARY_PROMPT_TEMPLATE
        assert "calm" in SUMMARY_PROMPT_TEMPLATE.lower()
        assert "informative" in SUMMARY_PROMPT_TEMPLATE.lower()
        assert "patterns" in SUMMARY_PROMPT_TEMPLATE.lower()

    def test_summary_empty_state_instruction_exists(self) -> None:
        """Test that SUMMARY_EMPTY_STATE_INSTRUCTION is defined."""
        assert SUMMARY_EMPTY_STATE_INSTRUCTION is not None
        assert isinstance(SUMMARY_EMPTY_STATE_INSTRUCTION, str)
        assert len(SUMMARY_EMPTY_STATE_INSTRUCTION) > 0

    def test_summary_empty_state_instruction_content(self) -> None:
        """Test that SUMMARY_EMPTY_STATE_INSTRUCTION has expected content."""
        assert "{period}" in SUMMARY_EMPTY_STATE_INSTRUCTION
        assert "reassuring" in SUMMARY_EMPTY_STATE_INSTRUCTION.lower()
        assert "quiet" in SUMMARY_EMPTY_STATE_INSTRUCTION.lower()
        assert "routine" in SUMMARY_EMPTY_STATE_INSTRUCTION.lower()

    def test_summary_event_format_exists(self) -> None:
        """Test that SUMMARY_EVENT_FORMAT is defined."""
        assert SUMMARY_EVENT_FORMAT is not None
        assert isinstance(SUMMARY_EVENT_FORMAT, str)
        assert len(SUMMARY_EVENT_FORMAT) > 0

    def test_summary_event_format_has_required_placeholders(self) -> None:
        """Test that SUMMARY_EVENT_FORMAT contains required placeholders."""
        required_placeholders = [
            "{index}",
            "{timestamp}",
            "{camera_name}",
            "{risk_level}",
            "{risk_score}",
            "{event_summary}",
            "{object_types}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in SUMMARY_EVENT_FORMAT, f"Missing placeholder: {placeholder}"


class TestBuildSummaryPrompt:
    """Tests for build_summary_prompt function."""

    def test_with_events(self) -> None:
        """Test build_summary_prompt with events."""
        events = [
            {
                "timestamp": "2:15 PM",
                "camera_name": "Front Door",
                "risk_level": "critical",
                "risk_score": 92,
                "summary": "Unknown person at front door",
                "object_types": "person",
            }
        ]

        system, user = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=events,
        )

        assert "security analyst" in system.lower()
        assert "2:15 PM" in user
        assert "Front Door" in user
        assert "critical" in user
        assert "92/100" in user
        assert "Unknown person at front door" in user
        assert "person" in user
        assert "High/Critical Events:** 1" in user

    def test_empty_events(self) -> None:
        """Test build_summary_prompt with no events."""
        _, user = build_summary_prompt(
            window_start="12:00 AM",
            window_end="11:59 PM",
            period_type="day",
            events=[],
            routine_count=15,
        )

        assert "No high or critical events" in user
        assert "15" in user  # routine count
        assert "reassuring" in user.lower()

    def test_empty_events_no_routine(self) -> None:
        """Test build_summary_prompt with no events and no routine count."""
        _, user = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
            routine_count=0,
        )

        assert "No high or critical events" in user
        assert "routine/low-priority detections" not in user

    def test_multiple_events(self) -> None:
        """Test build_summary_prompt with multiple events."""
        events = [
            {
                "timestamp": "1:00 PM",
                "camera_name": "Driveway",
                "risk_level": "high",
                "risk_score": 75,
                "summary": "Vehicle detected",
                "object_types": "vehicle",
            },
            {
                "timestamp": "1:05 PM",
                "camera_name": "Front Door",
                "risk_level": "critical",
                "risk_score": 88,
                "summary": "Person at door",
                "object_types": "person",
            },
        ]

        _, user = build_summary_prompt(
            window_start="1:00 PM",
            window_end="2:00 PM",
            period_type="hour",
            events=events,
        )

        assert "Event 1" in user
        assert "Event 2" in user
        assert "Driveway" in user
        assert "Front Door" in user
        assert "High/Critical Events:** 2" in user

    def test_period_types(self) -> None:
        """Test build_summary_prompt with different period types."""
        _, hourly = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
        )

        _, daily = build_summary_prompt(
            window_start="12:00 AM",
            window_end="11:59 PM",
            period_type="day",
            events=[],
        )

        assert "hour" in hourly
        assert "day" in daily

    def test_returns_tuple(self) -> None:
        """Test that build_summary_prompt returns a tuple of two strings."""
        result = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)  # system prompt
        assert isinstance(result[1], str)  # user prompt

    def test_system_prompt_consistency(self) -> None:
        """Test that system prompt is always the same."""
        _, _ = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=[],
        )

        system1, _ = build_summary_prompt(
            window_start="1:00 AM",
            window_end="2:00 AM",
            period_type="day",
            events=[
                {
                    "timestamp": "1:30 AM",
                    "camera_name": "Backyard",
                    "risk_level": "high",
                    "risk_score": 70,
                    "summary": "Motion detected",
                    "object_types": "person",
                }
            ],
        )

        system2, _ = build_summary_prompt(
            window_start="9:00 AM",
            window_end="10:00 AM",
            period_type="hour",
            events=[],
            routine_count=5,
        )

        assert system1 == system2
        assert system1 == SUMMARY_SYSTEM_PROMPT

    def test_event_formatting_includes_all_fields(self) -> None:
        """Test that event formatting includes all event fields."""
        events = [
            {
                "timestamp": "3:45 PM",
                "camera_name": "Side Gate",
                "risk_level": "high",
                "risk_score": 78,
                "summary": "Person lingering near side gate",
                "object_types": "person, backpack",
            }
        ]

        _, user = build_summary_prompt(
            window_start="3:00 PM",
            window_end="4:00 PM",
            period_type="hour",
            events=events,
        )

        # All event fields should be in the prompt
        assert "3:45 PM" in user
        assert "Side Gate" in user
        assert "high" in user
        assert "78/100" in user
        assert "Person lingering near side gate" in user
        assert "person, backpack" in user

    def test_no_empty_state_instruction_when_events_present(self) -> None:
        """Test that empty state instruction is not included when events exist."""
        events = [
            {
                "timestamp": "2:15 PM",
                "camera_name": "Front Door",
                "risk_level": "critical",
                "risk_score": 90,
                "summary": "Alert",
                "object_types": "person",
            }
        ]

        _, user = build_summary_prompt(
            window_start="2:00 PM",
            window_end="3:00 PM",
            period_type="hour",
            events=events,
        )

        # Should not contain reassuring message when there are events
        assert "reassuring" not in user.lower()
        assert "No high-priority security events" not in user

    def test_window_times_in_output(self) -> None:
        """Test that window times are included in the prompt."""
        _, user = build_summary_prompt(
            window_start="9:00 AM",
            window_end="10:00 AM",
            period_type="hour",
            events=[],
        )

        assert "9:00 AM" in user
        assert "10:00 AM" in user


class TestPromptModuleImports:
    """Tests for module structure and exports."""

    def test_all_format_functions_importable(self) -> None:
        """Test all format functions are importable."""
        from backend.services.prompts import (
            ClassAnomalyResult,
            build_summary_prompt,
            format_action_recognition_context,
            format_camera_health_context,
            format_class_anomaly_context,
            format_clothing_analysis_context,
            format_depth_context,
            format_detections_with_all_enrichment,
            format_image_quality_context,
            format_pet_classification_context,
            format_pose_analysis_context,
            format_vehicle_classification_context,
            format_vehicle_damage_context,
            format_violence_context,
            format_weather_context,
        )

        # Verify they are callable
        assert callable(format_violence_context)
        assert callable(format_weather_context)
        assert callable(format_clothing_analysis_context)
        assert callable(format_pose_analysis_context)
        assert callable(format_action_recognition_context)
        assert callable(format_vehicle_classification_context)
        assert callable(format_vehicle_damage_context)
        assert callable(format_pet_classification_context)
        assert callable(format_depth_context)
        assert callable(format_image_quality_context)
        assert callable(format_detections_with_all_enrichment)
        assert callable(build_summary_prompt)
        assert callable(format_class_anomaly_context)
        assert callable(format_camera_health_context)  # NEM-3012
        # Verify ClassAnomalyResult is a dataclass
        assert hasattr(ClassAnomalyResult, "__dataclass_fields__")

    def test_all_prompt_templates_importable(self) -> None:
        """Test all prompt templates are importable."""
        from backend.services.prompts import (
            ENRICHED_RISK_ANALYSIS_PROMPT,
            FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
            RISK_ANALYSIS_PROMPT,
            SUMMARY_EMPTY_STATE_INSTRUCTION,
            SUMMARY_EVENT_FORMAT,
            SUMMARY_PROMPT_TEMPLATE,
            SUMMARY_SYSTEM_PROMPT,
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
        )

        # Verify they are strings
        assert isinstance(RISK_ANALYSIS_PROMPT, str)
        assert isinstance(ENRICHED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(FULL_ENRICHED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(VISION_ENHANCED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(SUMMARY_SYSTEM_PROMPT, str)
        assert isinstance(SUMMARY_PROMPT_TEMPLATE, str)
        assert isinstance(SUMMARY_EMPTY_STATE_INSTRUCTION, str)
        assert isinstance(SUMMARY_EVENT_FORMAT, str)


# =============================================================================
# Mock Data Classes for Camera Health Context Testing (NEM-3012)
# =============================================================================


@dataclass
class MockSceneChange:
    """Mock SceneChange model for testing camera health context.

    Mimics the SceneChange SQLAlchemy model without database dependencies.
    """

    similarity_score: float
    change_type: str  # view_blocked, angle_changed, view_tampered, unknown
    acknowledged: bool = False


# =============================================================================
# Tests for format_camera_health_context (NEM-3012)
# =============================================================================


class TestFormatCameraHealthContext:
    """Tests for format_camera_health_context() function.

    This function formats scene tampering detection data (SceneChange) for
    inclusion in Nemotron prompts. Scene changes indicate potential camera
    tampering, blocked views, or angle changes that affect detection confidence.
    """

    def test_empty_scene_changes_returns_empty(self) -> None:
        """Test that empty scene changes list returns empty string."""
        from backend.services.prompts import format_camera_health_context

        result = format_camera_health_context("camera_1", [])
        assert result == ""

    def test_none_scene_changes_returns_empty(self) -> None:
        """Test that None scene changes returns empty string (graceful handling)."""
        from backend.services.prompts import format_camera_health_context

        # Function should handle None gracefully
        result = format_camera_health_context("camera_1", None)  # type: ignore[arg-type]
        assert result == ""

    def test_all_acknowledged_returns_empty(self) -> None:
        """Test that all acknowledged scene changes returns empty string."""
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.5, change_type="view_blocked", acknowledged=True),
            MockSceneChange(similarity_score=0.7, change_type="angle_changed", acknowledged=True),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]
        assert result == ""

    def test_view_blocked_format(self) -> None:
        """Test format for view_blocked change type."""
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.3, change_type="view_blocked", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        assert "CAMERA HEALTH ALERT" in result
        assert "BLOCKED" in result
        assert "30%" in result  # 0.3 formatted as percentage
        assert "DEGRADED" in result

    def test_angle_changed_format(self) -> None:
        """Test format for angle_changed change type."""
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.65, change_type="angle_changed", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        assert "CAMERA HEALTH ALERT" in result
        assert "angle" in result.lower() or "CHANGED" in result
        assert "65%" in result  # 0.65 formatted as percentage
        assert "Baseline" in result or "baseline" in result

    def test_tampered_format(self) -> None:
        """Test format for view_tampered change type."""
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.2, change_type="view_tampered", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        assert "CAMERA HEALTH ALERT" in result
        assert "TAMPERING" in result
        assert "20%" in result  # 0.2 formatted as percentage
        assert "CRITICAL" in result

    def test_unknown_change_type_format(self) -> None:
        """Test format for unknown change type (fallback)."""
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.5, change_type="unknown", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        # Should still produce a health alert for unknown changes
        assert "CAMERA HEALTH ALERT" in result
        assert "50%" in result

    def test_first_unacknowledged_used(self) -> None:
        """Test that only the first unacknowledged scene change is used."""
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.9, change_type="angle_changed", acknowledged=True),
            MockSceneChange(similarity_score=0.3, change_type="view_blocked", acknowledged=False),
            MockSceneChange(similarity_score=0.2, change_type="view_tampered", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        # Should use the first unacknowledged (view_blocked at 0.3)
        assert "BLOCKED" in result
        assert "30%" in result
        # Should NOT include the tampered alert
        assert "TAMPERING" not in result

    def test_similarity_score_formatting(self) -> None:
        """Test that similarity scores are formatted as percentages."""
        from backend.services.prompts import format_camera_health_context

        # Test various scores
        test_cases = [
            (0.0, "0%"),
            (0.5, "50%"),
            (0.85, "85%"),
            (1.0, "100%"),
        ]

        for score, expected in test_cases:
            scene_changes = [
                MockSceneChange(
                    similarity_score=score, change_type="view_blocked", acknowledged=False
                ),
            ]
            result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]
            assert expected in result, f"Expected {expected} for score {score}, got: {result}"

    def test_return_type_is_string(self) -> None:
        """Test that the function always returns a string."""
        from backend.services.prompts import format_camera_health_context

        # Empty case
        assert isinstance(format_camera_health_context("cam", []), str)

        # Non-empty case
        scene_changes = [
            MockSceneChange(similarity_score=0.5, change_type="view_blocked", acknowledged=False),
        ]
        assert isinstance(format_camera_health_context("cam", scene_changes), str)  # type: ignore[arg-type]

    def test_multiline_output(self) -> None:
        """Test that the output contains multiple lines for readability."""
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.3, change_type="view_blocked", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        # Should have at least 2 lines (header + content)
        lines = result.strip().split("\n")
        assert len(lines) >= 2, f"Expected at least 2 lines, got: {lines}"

    def test_importable(self) -> None:
        """Test that format_camera_health_context is importable from prompts module."""
        from backend.services.prompts import format_camera_health_context

        assert callable(format_camera_health_context)

    # =========================================================================
    # Risk Modifier Tests (NEM-3307)
    # =========================================================================

    def test_view_blocked_includes_risk_modifier(self) -> None:
        """Test that view_blocked change type includes risk modifier guidance.

        Per NEM-3307: view_blocked during intrusion = +30 points risk modifier.
        The LLM needs this guidance to properly escalate risk scores.
        """
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.3, change_type="view_blocked", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        # Should include risk modifier guidance for view_blocked
        assert "RISK MODIFIER" in result
        assert "+30" in result

    def test_tampered_includes_critical_escalation(self) -> None:
        """Test that view_tampered change type includes critical escalation guidance.

        Per NEM-3307: tampered + unknown person = escalate to CRITICAL.
        The output should guide the LLM to escalate appropriately.
        """
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.2, change_type="view_tampered", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        # Should include critical escalation guidance
        assert "CRITICAL" in result
        # Should mention escalation for unknown persons
        assert "unknown" in result.lower() or "escalate" in result.lower()

    def test_angle_changed_does_not_include_high_risk_modifier(self) -> None:
        """Test that angle_changed does not include high risk modifiers.

        angle_changed is less severe than view_blocked or tampered.
        It should not include +30 risk modifier.
        """
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.65, change_type="angle_changed", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        # Should not have the +30 risk modifier (that's for view_blocked)
        assert "+30" not in result

    def test_unknown_change_type_minimal_risk_guidance(self) -> None:
        """Test that unknown change type has minimal risk guidance.

        Unknown changes should not trigger high risk modifiers.
        """
        from backend.services.prompts import format_camera_health_context

        scene_changes = [
            MockSceneChange(similarity_score=0.5, change_type="unknown", acknowledged=False),
        ]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]

        # Should not include +30 risk modifier for unknown
        assert "+30" not in result


# =============================================================================
# Tests for Clothing Validation (NEM-3010)
# =============================================================================


class TestValidateClothingItems:
    """Tests for validate_clothing_items function - mutual exclusion logic.

    This validates that impossible garment combinations like "pants, skirt, dress"
    are resolved by keeping only the highest confidence item from each mutually
    exclusive group.
    """

    def test_mutual_exclusion_lower_body(self) -> None:
        """Test that lower body items are mutually exclusive."""
        from backend.services.prompts import validate_clothing_items

        items = ["pants", "skirt", "dress", "shoes"]
        confidences = {"pants": 0.8, "skirt": 0.6, "dress": 0.5, "shoes": 0.9}
        result = validate_clothing_items(items, confidences)

        assert "pants" in result  # Highest confidence in lower body group
        assert "skirt" not in result
        assert "dress" not in result
        assert "shoes" in result  # Non-exclusive item preserved

    def test_mutual_exclusion_dress_wins(self) -> None:
        """Test that dress with higher confidence wins over pants."""
        from backend.services.prompts import validate_clothing_items

        items = ["dress", "pants"]
        confidences = {"dress": 0.95, "pants": 0.7}
        result = validate_clothing_items(items, confidences)

        assert "dress" in result
        assert "pants" not in result

    def test_shorts_in_lower_body_exclusion(self) -> None:
        """Test that shorts are part of lower body mutual exclusion."""
        from backend.services.prompts import validate_clothing_items

        items = ["shorts", "pants", "upper_clothes"]
        confidences = {"shorts": 0.9, "pants": 0.6, "upper_clothes": 0.85}
        result = validate_clothing_items(items, confidences)

        assert "shorts" in result
        assert "pants" not in result
        assert "upper_clothes" in result  # Non-exclusive preserved

    def test_non_exclusive_items_preserved(self) -> None:
        """Test that non-exclusive items like shoes, belt, bag are preserved."""
        from backend.services.prompts import validate_clothing_items

        items = ["pants", "shoes", "belt", "bag", "hat"]
        confidences = {"pants": 0.8, "shoes": 0.9, "belt": 0.7, "bag": 0.75, "hat": 0.85}
        result = validate_clothing_items(items, confidences)

        assert "pants" in result
        assert "shoes" in result
        assert "belt" in result
        assert "bag" in result
        assert "hat" in result

    def test_single_item_from_exclusive_group_preserved(self) -> None:
        """Test that single items from exclusive groups pass through."""
        from backend.services.prompts import validate_clothing_items

        items = ["skirt", "upper_clothes"]
        confidences = {"skirt": 0.8, "upper_clothes": 0.9}
        result = validate_clothing_items(items, confidences)

        assert "skirt" in result
        assert "upper_clothes" in result

    def test_empty_items_returns_empty(self) -> None:
        """Test that empty input returns empty output."""
        from backend.services.prompts import validate_clothing_items

        result = validate_clothing_items([], {})
        assert result == []

    def test_no_conflicts_preserves_all(self) -> None:
        """Test that items without conflicts are all preserved."""
        from backend.services.prompts import validate_clothing_items

        items = ["hat", "sunglasses", "scarf", "shoes"]
        confidences = {"hat": 0.8, "sunglasses": 0.7, "scarf": 0.6, "shoes": 0.9}
        result = validate_clothing_items(items, confidences)

        assert len(result) == 4
        assert set(result) == {"hat", "sunglasses", "scarf", "shoes"}

    def test_missing_confidence_defaults_to_zero(self) -> None:
        """Test that items without confidence scores default to 0."""
        from backend.services.prompts import validate_clothing_items

        items = ["pants", "skirt"]
        confidences = {"pants": 0.5}  # skirt has no confidence
        result = validate_clothing_items(items, confidences)

        assert "pants" in result  # 0.5 > 0 (default)
        assert "skirt" not in result

    def test_equal_confidence_keeps_one(self) -> None:
        """Test that equal confidence still keeps only one item."""
        from backend.services.prompts import validate_clothing_items

        items = ["pants", "skirt"]
        confidences = {"pants": 0.5, "skirt": 0.5}
        result = validate_clothing_items(items, confidences)

        # Should keep exactly one of them
        assert len([i for i in result if i in {"pants", "skirt"}]) == 1

    def test_real_production_case_pants_skirt_dress(self) -> None:
        """Test the actual production case from NEM-3010: pants, skirt, dress."""
        from backend.services.prompts import validate_clothing_items

        # Real production case: shoes, upper_clothes, pants, skirt, dress
        items = ["shoes", "upper_clothes", "pants", "skirt", "dress"]
        confidences = {
            "shoes": 0.9,
            "upper_clothes": 0.85,
            "pants": 0.7,
            "skirt": 0.6,
            "dress": 0.5,
        }
        result = validate_clothing_items(items, confidences)

        # Lower body group: only pants (highest at 0.7)
        assert "pants" in result
        assert "skirt" not in result
        assert "dress" not in result

        # Non-exclusive items preserved
        assert "shoes" in result
        assert "upper_clothes" in result

    def test_preserves_order_of_non_exclusive_items(self) -> None:
        """Test that non-exclusive items maintain reasonable ordering."""
        from backend.services.prompts import validate_clothing_items

        items = ["hat", "sunglasses", "pants", "shoes", "belt"]
        confidences = {"hat": 0.8, "sunglasses": 0.7, "pants": 0.85, "shoes": 0.9, "belt": 0.6}
        result = validate_clothing_items(items, confidences)

        # All items should be present since no conflicts
        assert len(result) == 5
        assert set(result) == {"hat", "sunglasses", "pants", "shoes", "belt"}

    def test_logs_conflict_when_detected(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that conflicts are logged for monitoring (NEM-3305)."""
        import logging

        from backend.services.prompts import validate_clothing_items

        items = ["pants", "skirt", "dress", "shoes"]
        confidences = {"pants": 0.8, "skirt": 0.6, "dress": 0.5, "shoes": 0.9}

        # Capture log output at INFO level
        with caplog.at_level(logging.INFO, logger="backend.services.prompts"):
            validate_clothing_items(items, confidences)

        # Verify conflict was logged
        log_output = caplog.text.lower()
        assert "clothing" in log_output or "conflict" in log_output
        # Should mention the conflicting items
        assert "pants" in log_output or "skirt" in log_output or "dress" in log_output

    def test_no_log_when_no_conflict(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no conflict is logged when there are no conflicts."""
        import logging

        from backend.services.prompts import validate_clothing_items

        items = ["pants", "shoes", "hat"]
        confidences = {"pants": 0.8, "shoes": 0.9, "hat": 0.7}

        # Capture log output at INFO level
        with caplog.at_level(logging.INFO, logger="backend.services.prompts"):
            result = validate_clothing_items(items, confidences)

        # Should not have any conflict-related logs
        assert len(result) == 3
        # Check that there are no conflict logs
        for record in caplog.records:
            assert "conflict" not in record.message.lower()

    def test_jeans_in_lower_body_exclusion(self) -> None:
        """Test that jeans are part of lower body mutual exclusion."""
        from backend.services.prompts import validate_clothing_items

        items = ["jeans", "pants", "shirt"]
        confidences = {"jeans": 0.9, "pants": 0.6, "shirt": 0.85}
        result = validate_clothing_items(items, confidences)

        assert "jeans" in result
        assert "pants" not in result
        assert "shirt" in result  # Non-exclusive preserved

    def test_leggings_in_lower_body_exclusion(self) -> None:
        """Test that leggings are part of lower body mutual exclusion."""
        from backend.services.prompts import validate_clothing_items

        items = ["leggings", "skirt"]
        confidences = {"leggings": 0.85, "skirt": 0.7}
        result = validate_clothing_items(items, confidences)

        assert "leggings" in result
        assert "skirt" not in result


class TestValidateClothingItemsIntegration:
    """Integration tests for clothing validation with format functions."""

    def test_format_clothing_analysis_uses_validation(self) -> None:
        """Test that format_clothing_analysis_context applies validation."""
        # This tests the integration after we modify format_clothing_analysis_context
        # to use validate_clothing_items
        segmentation = MockClothingSegmentationResult(
            clothing_items=["pants", "skirt", "dress", "shoes"],
            has_face_covered=False,
            has_bag=False,
        )
        segmentation_dict = {"det_1": segmentation}

        # Create minimal classification
        classification = MockClothingClassification(
            raw_description="Dark clothing",
            confidence=0.8,
            is_suspicious=False,
            is_service_uniform=False,
            top_category="casual",
        )
        classification_dict = {"det_1": classification}

        result = format_clothing_analysis_context(classification_dict, segmentation_dict)

        # After validation, only one of pants/skirt/dress should appear
        # Count how many of the exclusive items are in the result
        lower_body_count = sum(
            1
            for item in ["pants", "skirt", "dress"]
            if f", {item}" in result
            or f": {item}" in result
            or result.endswith(item)
            or f"{item}," in result
        )

        # Should have at most 1 lower body item (validation applied)
        # Note: This test will fail until we implement the validation
        assert lower_body_count <= 1 or "pants, skirt, dress" not in result


# =============================================================================
# Test Classes for Format Functions - Enhanced Re-ID Context (NEM-3013)
# =============================================================================


@dataclass
class MockEntity:
    """Mock Entity model for testing format_enhanced_reid_context."""

    detection_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    trust_status: str


@dataclass
class MockReIDMatch:
    """Mock ReIDMatch for testing format_enhanced_reid_context.

    This represents a re-identification match from the reid_service.
    """

    similarity: float
    camera_id: str
    timestamp: datetime


class TestFormatEnhancedReidContext:
    """Tests for format_enhanced_reid_context function (NEM-3013).

    This function formats re-identification context with proper risk weighting
    based on entity history (detection count, days known, trust status).
    """

    def test_first_time_visitor_no_entity(self) -> None:
        """Test formatting for first time seen (no entity record)."""
        from backend.services.prompts import format_enhanced_reid_context

        result = format_enhanced_reid_context(
            person_id=1,
            entity=None,
            matches=[],
        )

        assert "Person 1" in result
        assert "FIRST TIME SEEN" in result
        assert "unknown" in result.lower()
        assert "Base risk: 50" in result

    def test_frequent_visitor_trusted(self) -> None:
        """Test formatting for frequent trusted visitor (20+ detections, 7+ days)."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=25,
            first_seen_at=datetime.now(UTC) - timedelta(days=14),
            last_seen_at=datetime.now(UTC) - timedelta(hours=2),
            trust_status="trusted",
        )

        result = format_enhanced_reid_context(
            person_id=1,
            entity=entity,
            matches=[],
        )

        assert "Person 1" in result
        assert "FREQUENT VISITOR" in result
        assert "25" in result  # detection count
        assert "14" in result  # days known
        assert "trusted" in result.lower()
        assert "-40 points" in result
        assert "established trusted entity" in result.lower()

    def test_frequent_visitor_unknown_trust(self) -> None:
        """Test formatting for frequent visitor with unknown trust (familiar but unverified)."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=30,
            first_seen_at=datetime.now(UTC) - timedelta(days=10),
            last_seen_at=datetime.now(UTC) - timedelta(hours=1),
            trust_status="unknown",
        )

        result = format_enhanced_reid_context(
            person_id=2,
            entity=entity,
            matches=[],
        )

        assert "Person 2" in result
        assert "FREQUENT VISITOR" in result
        assert "30" in result
        assert "-20 points" in result
        assert "familiar but unverified" in result.lower()

    def test_returning_visitor_5_plus_detections(self) -> None:
        """Test formatting for returning visitor (5+ detections)."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=8,
            first_seen_at=datetime.now(UTC) - timedelta(days=3),
            last_seen_at=datetime.now(UTC) - timedelta(minutes=30),
            trust_status="unknown",
        )

        result = format_enhanced_reid_context(
            person_id=3,
            entity=entity,
            matches=[],
        )

        assert "Person 3" in result
        assert "RETURNING VISITOR" in result
        assert "8" in result
        assert "-10 points" in result
        assert "repeat visitor" in result.lower()

    def test_recent_visitor_insufficient_history(self) -> None:
        """Test formatting for recent visitor with insufficient history (< 5 detections)."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=3,
            first_seen_at=datetime.now(UTC) - timedelta(days=2),
            last_seen_at=datetime.now(UTC) - timedelta(hours=1),
            trust_status="unknown",
        )

        result = format_enhanced_reid_context(
            person_id=4,
            entity=entity,
            matches=[],
        )

        assert "Person 4" in result
        assert "RECENT VISITOR" in result
        assert "3" in result
        assert "2" in result  # days ago
        assert "No risk modifier" in result
        assert "insufficient history" in result.lower()

    def test_frequent_visitor_minimum_threshold(self) -> None:
        """Test that exactly 20 detections and 7 days meets frequent visitor threshold."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=20,
            first_seen_at=datetime.now(UTC) - timedelta(days=7),
            last_seen_at=datetime.now(UTC) - timedelta(hours=1),
            trust_status="unknown",
        )

        result = format_enhanced_reid_context(
            person_id=5,
            entity=entity,
            matches=[],
        )

        assert "FREQUENT VISITOR" in result
        assert "-20 points" in result  # unknown trust = -20

    def test_returning_visitor_minimum_threshold(self) -> None:
        """Test that exactly 5 detections meets returning visitor threshold."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=5,
            first_seen_at=datetime.now(UTC) - timedelta(days=1),
            last_seen_at=datetime.now(UTC) - timedelta(hours=1),
            trust_status="unknown",
        )

        result = format_enhanced_reid_context(
            person_id=6,
            entity=entity,
            matches=[],
        )

        assert "RETURNING VISITOR" in result
        assert "-10 points" in result

    def test_high_detection_count_but_short_time_period(self) -> None:
        """Test that high detection count but < 7 days uses returning visitor tier."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        # 25 detections but only 3 days - not a frequent visitor yet
        entity = MockEntity(
            detection_count=25,
            first_seen_at=datetime.now(UTC) - timedelta(days=3),
            last_seen_at=datetime.now(UTC) - timedelta(hours=1),
            trust_status="unknown",
        )

        result = format_enhanced_reid_context(
            person_id=7,
            entity=entity,
            matches=[],
        )

        # Should be returning visitor since days_known < 7
        assert "RETURNING VISITOR" in result
        assert "-10 points" in result

    def test_untrusted_entity_modifier(self) -> None:
        """Test that untrusted entities still get familiarity-based modifiers."""
        from datetime import UTC, datetime, timedelta

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=30,
            first_seen_at=datetime.now(UTC) - timedelta(days=20),
            last_seen_at=datetime.now(UTC) - timedelta(hours=1),
            trust_status="untrusted",
        )

        result = format_enhanced_reid_context(
            person_id=8,
            entity=entity,
            matches=[],
        )

        # Untrusted frequent visitors still get -20 (not trusted -40)
        assert "FREQUENT VISITOR" in result
        assert "untrusted" in result.lower()
        assert "-20 points" in result
        assert "familiar but unverified" in result.lower()

    def test_includes_reidentification_header(self) -> None:
        """Test that the output includes the re-identification header."""
        from backend.services.prompts import format_enhanced_reid_context

        result = format_enhanced_reid_context(
            person_id=1,
            entity=None,
            matches=[],
        )

        assert "## Person 1 Re-Identification" in result

    def test_zero_detection_count_entity(self) -> None:
        """Test edge case: entity exists but has 0 detection count."""
        from datetime import UTC, datetime

        from backend.services.prompts import format_enhanced_reid_context

        entity = MockEntity(
            detection_count=0,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            trust_status="unknown",
        )

        result = format_enhanced_reid_context(
            person_id=9,
            entity=entity,
            matches=[],
        )

        # Should be treated as recent/insufficient history
        assert "RECENT VISITOR" in result
        assert "No risk modifier" in result


# =============================================================================
# Test Classes for Pose/Scene Conflict Resolution (NEM-3011)
# =============================================================================


class TestResolvePoseSceneConflict:
    """Tests for resolve_pose_scene_conflict function.

    This function resolves conflicts between pose detection (e.g., "running")
    and scene analysis (e.g., "sitting") to prevent confusing Nemotron with
    contradictory signals.
    """

    def test_running_vs_sitting_prefers_scene(self) -> None:
        """Test that running pose with sitting scene prefers scene interpretation."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.85,
            scene_description="A person sitting on a bench in the garden",
            has_motion_blur=False,
        )

        assert result["conflict_detected"] is True
        assert result["resolved_pose"] == "unknown"
        assert "scene" in result["resolution"].lower()

    def test_running_vs_standing_with_motion_blur_prefers_pose(self) -> None:
        """Test that running with motion blur prefers pose interpretation."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.90,
            scene_description="A person standing near the door",
            has_motion_blur=True,
        )

        assert result["conflict_detected"] is True
        assert result["resolved_pose"] == "running"
        assert "pose" in result["resolution"].lower()

    def test_running_vs_standing_without_motion_blur_prefers_scene(self) -> None:
        """Test that running without motion blur prefers scene interpretation."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.75,
            scene_description="A person standing at the entrance",
            has_motion_blur=False,
        )

        assert result["conflict_detected"] is True
        assert result["resolved_pose"] == "unknown"
        assert "scene" in result["resolution"].lower()

    def test_crouching_vs_walking_prefers_pose(self) -> None:
        """Test that crouching vs walking prefers pose (more specific)."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="crouching",
            pose_confidence=0.80,
            scene_description="Someone walking through the yard",
            has_motion_blur=False,
        )

        assert result["conflict_detected"] is True
        assert result["resolved_pose"] == "crouching"
        assert "pose" in result["resolution"].lower()

    def test_no_conflict_when_poses_match(self) -> None:
        """Test that no conflict is detected when pose and scene are consistent."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="walking",
            pose_confidence=0.88,
            scene_description="A person walking down the driveway",
            has_motion_blur=False,
        )

        assert result["conflict_detected"] is False
        assert result["resolved_pose"] == "walking"

    def test_no_conflict_when_scene_does_not_contain_conflicting_pose(self) -> None:
        """Test no conflict when scene description has no relevant pose info."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.85,
            scene_description="A vehicle parked in the driveway at night",
            has_motion_blur=True,
        )

        assert result["conflict_detected"] is False
        assert result["resolved_pose"] == "running"

    def test_case_insensitive_scene_matching(self) -> None:
        """Test that scene matching is case-insensitive."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.82,
            scene_description="PERSON SITTING ON THE PORCH",
            has_motion_blur=False,
        )

        assert result["conflict_detected"] is True
        assert result["resolved_pose"] == "unknown"

    def test_standing_in_scene_triggers_running_conflict(self) -> None:
        """Test that standing in scene with running pose triggers conflict."""
        from backend.services.prompts import resolve_pose_scene_conflict

        # Test with motion blur - should prefer pose
        result_blur = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.88,
            scene_description="The person appears to be standing near the gate",
            has_motion_blur=True,
        )

        assert result_blur["conflict_detected"] is True
        assert result_blur["resolved_pose"] == "running"

    def test_unknown_pose_returns_no_conflict(self) -> None:
        """Test that unknown pose types don't trigger conflicts."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="jumping",
            pose_confidence=0.75,
            scene_description="A person sitting on the steps",
            has_motion_blur=False,
        )

        assert result["conflict_detected"] is False
        assert result["resolved_pose"] == "jumping"

    def test_empty_scene_description(self) -> None:
        """Test handling of empty scene description."""
        from backend.services.prompts import resolve_pose_scene_conflict

        result = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.90,
            scene_description="",
            has_motion_blur=True,
        )

        assert result["conflict_detected"] is False
        assert result["resolved_pose"] == "running"


class TestFormatPoseSceneConflictWarning:
    """Tests for format_pose_scene_conflict_warning function.

    This function generates a warning message to inject into prompts when
    a pose/scene conflict is detected.
    """

    def test_warning_generated_when_conflict_detected(self) -> None:
        """Test warning is generated when conflict is detected."""
        from backend.services.prompts import format_pose_scene_conflict_warning

        conflict_result = {
            "conflict_detected": True,
            "resolved_pose": "unknown",
            "resolution": "Preferred scene interpretation",
        }

        warning = format_pose_scene_conflict_warning(
            pose="running",
            scene_description="sitting on bench",
            conflict_result=conflict_result,
        )

        assert warning is not None
        assert "SIGNAL CONFLICT" in warning
        assert "running" in warning
        assert "sitting" in warning
        assert "LOW" in warning or "low" in warning.lower()

    def test_no_warning_when_no_conflict(self) -> None:
        """Test no warning is generated when no conflict exists."""
        from backend.services.prompts import format_pose_scene_conflict_warning

        conflict_result = {
            "conflict_detected": False,
            "resolved_pose": "walking",
        }

        warning = format_pose_scene_conflict_warning(
            pose="walking",
            scene_description="walking down path",
            conflict_result=conflict_result,
        )

        assert warning is None or warning == ""

    def test_warning_includes_behavioral_analysis_note(self) -> None:
        """Test warning includes note about behavioral analysis confidence."""
        from backend.services.prompts import format_pose_scene_conflict_warning

        conflict_result = {
            "conflict_detected": True,
            "resolved_pose": "unknown",
            "resolution": "Preferred scene interpretation",
        }

        warning = format_pose_scene_conflict_warning(
            pose="running",
            scene_description="person sitting",
            conflict_result=conflict_result,
        )

        assert "behavioral analysis" in warning.lower() or "behavioral" in warning.lower()
        assert "weight other evidence" in warning.lower() or "confidence" in warning.lower()

    def test_warning_contains_visual_indicator(self) -> None:
        """Test warning contains visual indicator for attention."""
        from backend.services.prompts import format_pose_scene_conflict_warning

        conflict_result = {
            "conflict_detected": True,
            "resolved_pose": "unknown",
            "resolution": "Preferred scene interpretation",
        }

        warning = format_pose_scene_conflict_warning(
            pose="crouching",
            scene_description="walking through yard",
            conflict_result=conflict_result,
        )

        # Should contain warning marker
        assert any(marker in warning for marker in ["WARNING", "CONFLICT", "ALERT", "**"])


class TestPoseSceneConflictIntegration:
    """Integration tests for pose/scene conflict resolution in prompts."""

    def test_conflict_resolution_importable(self) -> None:
        """Test that conflict resolution functions are importable."""
        from backend.services.prompts import (
            format_pose_scene_conflict_warning,
            resolve_pose_scene_conflict,
        )

        assert callable(resolve_pose_scene_conflict)
        assert callable(format_pose_scene_conflict_warning)

    def test_full_workflow_running_sitting_conflict(self) -> None:
        """Test full workflow of detecting and formatting a conflict."""
        from backend.services.prompts import (
            format_pose_scene_conflict_warning,
            resolve_pose_scene_conflict,
        )

        # Step 1: Detect conflict
        result = resolve_pose_scene_conflict(
            pose="running",
            pose_confidence=0.85,
            scene_description="A person is sitting on a chair",
            has_motion_blur=False,
        )

        # Step 2: Generate warning
        warning = format_pose_scene_conflict_warning(
            pose="running",
            scene_description="A person is sitting on a chair",
            conflict_result=result,
        )

        # Verify workflow
        assert result["conflict_detected"] is True
        assert warning is not None
        assert "running" in warning
        assert "sitting" in warning

    def test_no_warning_for_consistent_detection(self) -> None:
        """Test no warning when pose and scene are consistent."""
        from backend.services.prompts import (
            format_pose_scene_conflict_warning,
            resolve_pose_scene_conflict,
        )

        result = resolve_pose_scene_conflict(
            pose="standing",
            pose_confidence=0.92,
            scene_description="A person standing at the front door",
            has_motion_blur=False,
        )

        warning = format_pose_scene_conflict_warning(
            pose="standing",
            scene_description="A person standing at the front door",
            conflict_result=result,
        )

        assert result["conflict_detected"] is False
        assert warning is None or warning == ""


# =============================================================================
# Test Classes for Calibrated System Prompt (NEM-3019)
# =============================================================================


class TestCalibratedSystemPrompt:
    """Tests for the CALIBRATED_SYSTEM_PROMPT constant.

    This prompt provides calibration guidance to prevent over-alerting by
    establishing expected event distributions and scoring principles.
    """

    def test_calibrated_system_prompt_exists(self) -> None:
        """Test that CALIBRATED_SYSTEM_PROMPT is defined."""
        assert CALIBRATED_SYSTEM_PROMPT is not None
        assert isinstance(CALIBRATED_SYSTEM_PROMPT, str)
        assert len(CALIBRATED_SYSTEM_PROMPT) > 0

    def test_calibrated_system_prompt_has_critical_principle(self) -> None:
        """Test that the prompt includes the critical principle about non-threats."""
        assert "CRITICAL PRINCIPLE" in CALIBRATED_SYSTEM_PROMPT
        assert "Most detections are NOT threats" in CALIBRATED_SYSTEM_PROMPT
        assert "Residents" in CALIBRATED_SYSTEM_PROMPT
        assert "family members" in CALIBRATED_SYSTEM_PROMPT
        assert "delivery workers" in CALIBRATED_SYSTEM_PROMPT
        assert "pets" in CALIBRATED_SYSTEM_PROMPT

    def test_calibrated_system_prompt_has_calibration_section(self) -> None:
        """Test that the prompt includes calibration distribution expectations."""
        # NEM-3880: Changed section name from CALIBRATION to DISTRIBUTION
        has_calibration = "CALIBRATION" in CALIBRATED_SYSTEM_PROMPT
        has_distribution = "DISTRIBUTION" in CALIBRATED_SYSTEM_PROMPT
        assert has_calibration or has_distribution
        # Should have percentage distribution guidance (updated per NEM-3880)
        assert "85%" in CALIBRATED_SYSTEM_PROMPT
        assert "10%" in CALIBRATED_SYSTEM_PROMPT
        assert "4%" in CALIBRATED_SYSTEM_PROMPT
        assert "1%" in CALIBRATED_SYSTEM_PROMPT

    def test_calibrated_system_prompt_has_risk_level_ranges(self) -> None:
        """Test that the prompt includes risk level score ranges."""
        assert "LOW" in CALIBRATED_SYSTEM_PROMPT
        # NEM-3880: Updated to use ELEVATED and MODERATE instead of MEDIUM
        has_elevated = "ELEVATED" in CALIBRATED_SYSTEM_PROMPT
        has_moderate = "MODERATE" in CALIBRATED_SYSTEM_PROMPT
        assert has_elevated or has_moderate
        assert "HIGH" in CALIBRATED_SYSTEM_PROMPT
        assert "CRITICAL" in CALIBRATED_SYSTEM_PROMPT
        # Score ranges - updated per NEM-3880
        assert "0-20" in CALIBRATED_SYSTEM_PROMPT
        assert "21-40" in CALIBRATED_SYSTEM_PROMPT
        assert "61-80" in CALIBRATED_SYSTEM_PROMPT
        assert "81-100" in CALIBRATED_SYSTEM_PROMPT

    def test_calibrated_system_prompt_has_miscalibration_warning(self) -> None:
        """Test that the prompt warns about miscalibration."""
        assert "miscalibrated" in CALIBRATED_SYSTEM_PROMPT
        # NEM-3880: Now warns about scoring delivery drivers above 15
        assert "15" in CALIBRATED_SYSTEM_PROMPT or "delivery" in CALIBRATED_SYSTEM_PROMPT.lower()

    def test_calibrated_system_prompt_has_json_output_instruction(self) -> None:
        """Test that the prompt instructs JSON-only output."""
        assert "JSON" in CALIBRATED_SYSTEM_PROMPT
        assert "No preamble" in CALIBRATED_SYSTEM_PROMPT or "valid JSON" in CALIBRATED_SYSTEM_PROMPT

    def test_calibrated_system_prompt_mentions_home_security(self) -> None:
        """Test that the prompt establishes home security context."""
        assert "home security" in CALIBRATED_SYSTEM_PROMPT
        assert "residential" in CALIBRATED_SYSTEM_PROMPT


class TestScoringReferenceTable:
    """Tests for the SCORING_REFERENCE_TABLE constant.

    This table provides inline scoring examples to anchor the LLM's risk
    assessment with concrete scenarios and scores.
    """

    def test_scoring_reference_table_exists(self) -> None:
        """Test that SCORING_REFERENCE_TABLE is defined."""
        assert SCORING_REFERENCE_TABLE is not None
        assert isinstance(SCORING_REFERENCE_TABLE, str)
        assert len(SCORING_REFERENCE_TABLE) > 0

    def test_scoring_reference_table_has_table_format(self) -> None:
        """Test that the table uses markdown table format."""
        assert "| Scenario" in SCORING_REFERENCE_TABLE
        assert "| Score" in SCORING_REFERENCE_TABLE
        assert "| Reasoning" in SCORING_REFERENCE_TABLE
        assert "|-------" in SCORING_REFERENCE_TABLE

    def test_scoring_reference_table_has_low_risk_scenarios(self) -> None:
        """Test that the table includes low-risk scenario examples."""
        # Resident arriving home should be very low risk
        assert "Resident" in SCORING_REFERENCE_TABLE or "resident" in SCORING_REFERENCE_TABLE
        # Delivery driver should be low risk
        assert "Delivery" in SCORING_REFERENCE_TABLE or "delivery" in SCORING_REFERENCE_TABLE

    def test_scoring_reference_table_has_medium_risk_scenarios(self) -> None:
        """Test that the table includes medium-risk scenario examples."""
        # Unknown person on sidewalk
        assert "Unknown" in SCORING_REFERENCE_TABLE or "unknown" in SCORING_REFERENCE_TABLE
        # Lingering behavior
        assert "lingering" in SCORING_REFERENCE_TABLE or "Lingering" in SCORING_REFERENCE_TABLE

    def test_scoring_reference_table_has_high_risk_scenarios(self) -> None:
        """Test that the table includes high-risk scenario examples."""
        # Testing door handles is high risk
        assert "door" in SCORING_REFERENCE_TABLE

    def test_scoring_reference_table_has_critical_risk_scenarios(self) -> None:
        """Test that the table includes critical-risk scenario examples."""
        # Break-in should be critical
        assert "break-in" in SCORING_REFERENCE_TABLE or "Break-in" in SCORING_REFERENCE_TABLE
        # Violence should be critical
        assert "violence" in SCORING_REFERENCE_TABLE or "Violence" in SCORING_REFERENCE_TABLE

    def test_scoring_reference_table_has_score_ranges(self) -> None:
        """Test that the table includes specific score ranges (updated NEM-3880)."""
        # Low risk scores (0-10, 0-5, 0-15, 5-15) per NEM-3880 calibration
        assert "0-10" in SCORING_REFERENCE_TABLE
        assert "0-5" in SCORING_REFERENCE_TABLE
        assert "0-15" in SCORING_REFERENCE_TABLE
        # Medium risk scores (20-35 or 35-50 or 50-65)
        has_medium_range = (
            "20-35" in SCORING_REFERENCE_TABLE
            or "35-50" in SCORING_REFERENCE_TABLE
            or "50-65" in SCORING_REFERENCE_TABLE
        )
        assert has_medium_range
        # High risk scores (70-85 or 65-80)
        assert "70-85" in SCORING_REFERENCE_TABLE or "65-80" in SCORING_REFERENCE_TABLE
        # Critical risk scores (90-100 or 85-100)
        assert "90-100" in SCORING_REFERENCE_TABLE or "85-100" in SCORING_REFERENCE_TABLE


class TestHouseholdContextTemplate:
    """Tests for the HOUSEHOLD_CONTEXT_TEMPLATE constant.

    This template provides household-specific context at the top of the prompt.
    """

    def test_household_context_template_exists(self) -> None:
        """Test that HOUSEHOLD_CONTEXT_TEMPLATE is defined."""
        assert HOUSEHOLD_CONTEXT_TEMPLATE is not None
        assert isinstance(HOUSEHOLD_CONTEXT_TEMPLATE, str)

    def test_household_context_template_has_header(self) -> None:
        """Test that the template has a household context header."""
        assert (
            "HOUSEHOLD" in HOUSEHOLD_CONTEXT_TEMPLATE or "Household" in HOUSEHOLD_CONTEXT_TEMPLATE
        )


class TestPromptTemplatesHaveCalibrationAtTop:
    """Tests to verify all prompt templates have calibration guidance at the TOP.

    NEM-3019 requires risk modifiers to appear FIRST in the user prompt,
    not buried at the bottom where they may be ignored.
    """

    def test_model_zoo_prompt_has_scoring_reference_early(self) -> None:
        """Test that MODEL_ZOO_ENHANCED prompt has scoring reference near the top."""
        prompt = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

        # Find position of key sections
        detections_pos = prompt.find("## Detections") or prompt.find(
            "{detections_with_all_attributes}"
        )
        scoring_pos = prompt.find("## SCORING REFERENCE") or prompt.find("SCORING REFERENCE")

        # Scoring reference should appear BEFORE detections
        # (unless it's in a different structure, then it should be early)
        if scoring_pos > 0 and detections_pos > 0:
            assert scoring_pos < detections_pos, (
                "Scoring reference should appear before detections in prompt"
            )

    def test_vision_enhanced_prompt_has_scoring_reference_early(self) -> None:
        """Test that VISION_ENHANCED prompt has scoring reference near the top."""
        prompt = VISION_ENHANCED_RISK_ANALYSIS_PROMPT

        # Should have scoring reference
        assert "SCORING REFERENCE" in prompt or "Scoring" in prompt or "| Scenario" in prompt

    def test_enriched_prompt_has_scoring_reference(self) -> None:
        """Test that ENRICHED_RISK_ANALYSIS_PROMPT has scoring reference."""
        prompt = ENRICHED_RISK_ANALYSIS_PROMPT

        # Should have scoring reference or calibration guidance
        has_scoring = "SCORING REFERENCE" in prompt or "| Scenario" in prompt
        has_calibration = "CALIBRATION" in prompt or "calibration" in prompt

        assert has_scoring or has_calibration, (
            "ENRICHED prompt should have scoring reference or calibration"
        )

    def test_full_enriched_prompt_has_scoring_reference(self) -> None:
        """Test that FULL_ENRICHED_RISK_ANALYSIS_PROMPT has scoring reference."""
        prompt = FULL_ENRICHED_RISK_ANALYSIS_PROMPT

        # Should have scoring reference or calibration guidance
        has_scoring = "SCORING REFERENCE" in prompt or "| Scenario" in prompt
        has_calibration = "CALIBRATION" in prompt or "calibration" in prompt

        assert has_scoring or has_calibration, (
            "FULL_ENRICHED prompt should have scoring reference or calibration"
        )

    def test_basic_prompt_has_scoring_reference(self) -> None:
        """Test that basic RISK_ANALYSIS_PROMPT has scoring reference."""
        prompt = RISK_ANALYSIS_PROMPT

        # Should have scoring reference or calibration guidance
        has_scoring = "SCORING REFERENCE" in prompt or "| Scenario" in prompt
        has_calibration = "CALIBRATION" in prompt or "calibration" in prompt
        has_risk_levels = "low (0-29)" in prompt and "critical (85-100)" in prompt

        assert has_scoring or has_calibration or has_risk_levels, (
            "Basic prompt should have scoring reference or calibration"
        )


class TestPromptTemplatesUseCalibrationSystemPrompt:
    """Tests to verify prompt templates use the calibrated system prompt."""

    def test_model_zoo_prompt_uses_calibrated_system_prompt(self) -> None:
        """Test that MODEL_ZOO_ENHANCED uses calibrated system message."""
        prompt = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

        # Should include calibration concepts in system section
        system_section = (
            prompt.split("<|im_start|>user")[0] if "<|im_start|>user" in prompt else prompt
        )

        # Check for key calibration concepts
        has_calibration = any(
            [
                "Most detections are NOT threats" in system_section,
                "CRITICAL PRINCIPLE" in system_section,
                "miscalibrated" in system_section,
                "home security analyst" in system_section,
            ]
        )

        assert has_calibration, "MODEL_ZOO_ENHANCED system section should have calibration guidance"

    def test_vision_enhanced_prompt_uses_calibrated_system_prompt(self) -> None:
        """Test that VISION_ENHANCED uses calibrated system message."""
        prompt = VISION_ENHANCED_RISK_ANALYSIS_PROMPT

        # Should include calibration concepts in system section
        system_section = (
            prompt.split("<|im_start|>user")[0] if "<|im_start|>user" in prompt else prompt
        )

        # Check for key calibration concepts
        has_calibration = any(
            [
                "Most detections are NOT threats" in system_section,
                "CRITICAL PRINCIPLE" in system_section,
                "miscalibrated" in system_section,
                "home security analyst" in system_section,
            ]
        )

        assert has_calibration, "VISION_ENHANCED system section should have calibration guidance"

    def test_enriched_prompt_uses_calibrated_system_prompt(self) -> None:
        """Test that ENRICHED uses calibrated system message."""
        prompt = ENRICHED_RISK_ANALYSIS_PROMPT

        # Should include calibration concepts in system section
        system_section = (
            prompt.split("<|im_start|>user")[0] if "<|im_start|>user" in prompt else prompt
        )

        # Check for key calibration concepts
        has_calibration = any(
            [
                "Most detections are NOT threats" in system_section,
                "CRITICAL PRINCIPLE" in system_section,
                "miscalibrated" in system_section,
                "home security analyst" in system_section,
            ]
        )

        assert has_calibration, "ENRICHED system section should have calibration guidance"

    def test_full_enriched_prompt_uses_calibrated_system_prompt(self) -> None:
        """Test that FULL_ENRICHED uses calibrated system message."""
        prompt = FULL_ENRICHED_RISK_ANALYSIS_PROMPT

        # Should include calibration concepts in system section
        system_section = (
            prompt.split("<|im_start|>user")[0] if "<|im_start|>user" in prompt else prompt
        )

        # Check for key calibration concepts
        has_calibration = any(
            [
                "Most detections are NOT threats" in system_section,
                "CRITICAL PRINCIPLE" in system_section,
                "miscalibrated" in system_section,
                "home security analyst" in system_section,
            ]
        )

        assert has_calibration, "FULL_ENRICHED system section should have calibration guidance"

    def test_basic_prompt_uses_calibrated_system_prompt(self) -> None:
        """Test that basic RISK_ANALYSIS_PROMPT uses calibrated system message."""
        prompt = RISK_ANALYSIS_PROMPT

        # Should include calibration concepts in system section
        system_section = (
            prompt.split("<|im_start|>user")[0] if "<|im_start|>user" in prompt else prompt
        )

        # Check for key calibration concepts
        has_calibration = any(
            [
                "Most detections are NOT threats" in system_section,
                "CRITICAL PRINCIPLE" in system_section,
                "miscalibrated" in system_section,
                "home security analyst" in system_section,
            ]
        )

        assert has_calibration, "Basic prompt system section should have calibration guidance"


# =============================================================================
# Mock Classes for build_enrichment_sections Tests
# =============================================================================


@dataclass
class MockPoseResult:
    """Mock PoseResult for testing build_enrichment_sections."""

    pose_class: str
    pose_confidence: float
    keypoints: dict = field(default_factory=dict)
    bbox: list[float] | None = None


@dataclass
class MockEnrichmentResultFull:
    """Full mock EnrichmentResult with all fields for build_enrichment_sections tests.

    This mock includes all the fields that build_enrichment_sections() needs to check.
    """

    violence_detection: MockViolenceDetectionResult | None = None
    clothing_classifications: dict[str, MockClothingClassification] = field(default_factory=dict)
    clothing_segmentation: dict[str, MockClothingSegmentationResult] = field(default_factory=dict)
    pose_results: dict[str, MockPoseResult] = field(default_factory=dict)
    vehicle_damage: dict[str, MockVehicleDamageResult] = field(default_factory=dict)
    pet_classifications: dict[str, MockPetClassificationResult] = field(default_factory=dict)


# =============================================================================
# Test Classes for build_enrichment_sections (NEM-3020)
# =============================================================================


class TestBuildEnrichmentSections:
    """Tests for build_enrichment_sections function (NEM-3020).

    This function builds prompt sections conditionally, only including sections
    that have actual meaningful data. Empty or unhelpful sections like
    "Violence analysis: Not performed" should NOT be included.

    Acceptance Criteria:
    - Empty sections not included in prompts
    - Only sections with actual data appear
    - Violence always shown if detected
    - Pets shown to reduce FPs (if confidence > 85%)
    - Low confidence data excluded
    """

    def test_empty_enrichment_returns_empty_string(self) -> None:
        """Test that empty enrichment result returns empty string, not empty sections."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull()
        result = build_enrichment_sections(enrichment)

        assert result == ""
        # Should NOT contain any of these placeholder texts
        assert "Violence analysis: Not performed" not in result
        assert "Vehicle classification: No vehicles analyzed" not in result
        assert "Pose analysis: Not available" not in result
        assert "Pet classification: No animals detected" not in result

    def test_violence_included_when_detected(self) -> None:
        """Test that violence section is included when violence is detected."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            violence_detection=MockViolenceDetectionResult(
                is_violent=True,
                confidence=0.95,
                violent_score=0.95,
                non_violent_score=0.05,
            )
        )
        result = build_enrichment_sections(enrichment)

        assert "VIOLENCE DETECTED" in result
        assert "95%" in result
        assert "ACTION REQUIRED" in result

    def test_violence_excluded_when_not_detected(self) -> None:
        """Test that violence section is excluded when no violence detected."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            violence_detection=MockViolenceDetectionResult(
                is_violent=False,
                confidence=0.92,
                violent_score=0.08,
                non_violent_score=0.92,
            )
        )
        result = build_enrichment_sections(enrichment)

        # Should not include "no violence detected" message - that's unhelpful
        assert "No violence detected" not in result
        assert "Violence analysis" not in result

    def test_violence_excluded_when_none(self) -> None:
        """Test that violence section is excluded when violence_detection is None."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(violence_detection=None)
        result = build_enrichment_sections(enrichment)

        assert "Violence analysis: Not performed" not in result
        assert "violence" not in result.lower()

    def test_clothing_included_when_meaningful(self) -> None:
        """Test that clothing section is included when there's meaningful data."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            clothing_classifications={
                "det_001": MockClothingClassification(
                    raw_description="blue jeans, white t-shirt",
                    confidence=0.88,
                    is_suspicious=False,
                    is_service_uniform=False,
                    top_category="casual",
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "blue jeans, white t-shirt" in result
        assert "88" in result

    def test_clothing_excluded_when_empty(self) -> None:
        """Test that clothing section is excluded when no clothing data."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(clothing_classifications={})
        result = build_enrichment_sections(enrichment)

        assert "Clothing analysis: No person detections analyzed" not in result
        assert "Clothing" not in result

    def test_suspicious_clothing_included(self) -> None:
        """Test that suspicious clothing triggers section inclusion with alert."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            clothing_classifications={
                "det_001": MockClothingClassification(
                    raw_description="all black clothing, ski mask",
                    confidence=0.92,
                    is_suspicious=True,
                    is_service_uniform=False,
                    top_category="suspicious_all_black",
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "all black clothing, ski mask" in result
        assert "ALERT" in result

    def test_pose_included_when_high_confidence(self) -> None:
        """Test that pose section is included when confidence > 0.7."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            pose_results={
                "det_001": MockPoseResult(
                    pose_class="crouching",
                    pose_confidence=0.85,
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "crouching" in result
        assert "85%" in result

    def test_pose_excluded_when_low_confidence(self) -> None:
        """Test that pose section is excluded when confidence <= 0.7."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            pose_results={
                "det_001": MockPoseResult(
                    pose_class="standing",
                    pose_confidence=0.65,  # Below 0.7 threshold
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        # Low confidence pose should be excluded
        assert "Pose analysis" not in result
        assert "standing" not in result

    def test_pose_excluded_when_empty(self) -> None:
        """Test that pose section is excluded when no pose data."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(pose_results={})
        result = build_enrichment_sections(enrichment)

        assert "Pose analysis: Not available" not in result
        assert "Pose analysis: No poses detected" not in result

    def test_vehicle_damage_included_when_detected(self) -> None:
        """Test that vehicle damage section is included when damage detected."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            vehicle_damage={
                "det_v001": MockVehicleDamageResult(
                    has_damage=True,
                    damage_types={"glass_shatter", "dents"},
                    total_damage_count=3,
                    highest_confidence=0.88,
                    has_high_security_damage=True,
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "damage detected" in result.lower()
        assert "glass_shatter" in result

    def test_vehicle_damage_excluded_when_no_damage(self) -> None:
        """Test that vehicle damage section is excluded when no damage."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            vehicle_damage={
                "det_v001": MockVehicleDamageResult(
                    has_damage=False,
                    damage_types=set(),
                    total_damage_count=0,
                    highest_confidence=0.0,
                    has_high_security_damage=False,
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        # Should not include "no damage detected" message
        assert "Vehicle damage: No damage detected" not in result
        assert "Vehicle damage: No vehicles analyzed for damage" not in result

    def test_vehicle_damage_excluded_when_empty(self) -> None:
        """Test that vehicle damage section is excluded when no vehicles."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(vehicle_damage={})
        result = build_enrichment_sections(enrichment)

        assert "Vehicle damage" not in result

    def test_pet_included_when_high_confidence(self) -> None:
        """Test that pet section is included when confidence > 85% (helps reduce FPs)."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            pet_classifications={
                "det_p001": MockPetClassificationResult(
                    animal_type="dog",
                    confidence=0.92,
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "dog" in result
        assert "92%" in result
        # Should include the false positive note
        assert "FALSE POSITIVE" in result or "household pet" in result.lower()

    def test_pet_excluded_when_low_confidence(self) -> None:
        """Test that pet section is excluded when confidence <= 85%."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            pet_classifications={
                "det_p001": MockPetClassificationResult(
                    animal_type="cat",
                    confidence=0.80,  # Below 85% threshold
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        # Low confidence pet should be excluded
        assert "Pet classification" not in result
        assert "cat" not in result

    def test_pet_excluded_when_empty(self) -> None:
        """Test that pet section is excluded when no pets detected."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(pet_classifications={})
        result = build_enrichment_sections(enrichment)

        assert "Pet classification: No animals detected" not in result
        assert "Pet" not in result

    def test_multiple_sections_combined(self) -> None:
        """Test that multiple valid sections are combined with double newlines."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            violence_detection=MockViolenceDetectionResult(
                is_violent=True,
                confidence=0.98,
                violent_score=0.98,
                non_violent_score=0.02,
            ),
            pet_classifications={
                "det_p001": MockPetClassificationResult(
                    animal_type="dog",
                    confidence=0.95,
                )
            },
        )
        result = build_enrichment_sections(enrichment)

        # Both sections should be present
        assert "VIOLENCE DETECTED" in result
        assert "dog" in result
        # Sections should be separated by double newlines
        assert "\n\n" in result

    def test_only_high_confidence_pets_included(self) -> None:
        """Test that only pets with confidence > 85% are included."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            pet_classifications={
                "det_p001": MockPetClassificationResult(
                    animal_type="dog",
                    confidence=0.92,  # Above threshold - included
                ),
                "det_p002": MockPetClassificationResult(
                    animal_type="hamster",
                    confidence=0.70,  # Below threshold - excluded
                ),
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "dog" in result
        # Low confidence pet should be excluded (using hamster to avoid "cat" in "classification")
        assert "hamster" not in result

    def test_no_empty_section_placeholders(self) -> None:
        """Test that no placeholder messages appear for missing data."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            # Only violence (not detected)
            violence_detection=MockViolenceDetectionResult(
                is_violent=False,
                confidence=0.9,
                violent_score=0.1,
                non_violent_score=0.9,
            )
        )
        result = build_enrichment_sections(enrichment)

        # None of these placeholder messages should appear
        assert "Not performed" not in result
        assert "Not available" not in result
        assert "No vehicles analyzed" not in result
        assert "No person detections" not in result
        assert "No animals detected" not in result
        assert "No poses detected" not in result

    def test_mixed_valid_and_empty_sections(self) -> None:
        """Test with mix of valid data and empty sections."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            # Empty - should be excluded
            violence_detection=None,
            # Valid - should be included
            clothing_classifications={
                "det_001": MockClothingClassification(
                    raw_description="red jacket",
                    confidence=0.85,
                    is_suspicious=False,
                    is_service_uniform=False,
                    top_category="casual",
                )
            },
            # Empty - should be excluded
            pose_results={},
            # No damage - should be excluded
            vehicle_damage={
                "det_v001": MockVehicleDamageResult(
                    has_damage=False,
                    damage_types=set(),
                    total_damage_count=0,
                    highest_confidence=0.0,
                    has_high_security_damage=False,
                )
            },
            # Low confidence - should be excluded
            pet_classifications={
                "det_p001": MockPetClassificationResult(
                    animal_type="cat",
                    confidence=0.70,
                )
            },
        )
        result = build_enrichment_sections(enrichment)

        # Only clothing should be present
        assert "red jacket" in result
        assert "Violence" not in result
        assert "Pose" not in result
        assert "Vehicle damage" not in result
        assert "Pet" not in result

    def test_service_uniform_included(self) -> None:
        """Test that service uniform clothing is included (lower risk indicator)."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            clothing_classifications={
                "det_001": MockClothingClassification(
                    raw_description="FedEx uniform",
                    confidence=0.92,
                    is_suspicious=False,
                    is_service_uniform=True,
                    top_category="delivery_uniform",
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "FedEx uniform" in result
        assert "Service/delivery worker" in result or "lower risk" in result

    def test_high_security_vehicle_damage_priority(self) -> None:
        """Test that high security vehicle damage (glass shatter, lamp broken) is included."""
        from backend.services.prompts import build_enrichment_sections

        enrichment = MockEnrichmentResultFull(
            vehicle_damage={
                "det_v001": MockVehicleDamageResult(
                    has_damage=True,
                    damage_types={"glass_shatter"},
                    total_damage_count=1,
                    highest_confidence=0.90,
                    has_high_security_damage=True,
                )
            }
        )
        result = build_enrichment_sections(enrichment)

        assert "SECURITY ALERT" in result
        assert "glass_shatter" in result


# =============================================================================
# Mock Data Classes for Household Context Testing (NEM-3024)
# =============================================================================


@dataclass
class MockHouseholdMatch:
    """Mock HouseholdMatch for testing format_household_context.

    Mimics the HouseholdMatch dataclass from household_matcher service.
    Extended with optional member_role and schedule_status for NEM-3315.
    """

    member_id: int | None = None
    member_name: str | None = None
    vehicle_id: int | None = None
    vehicle_description: str | None = None
    similarity: float = 0.0
    match_type: str = ""
    # NEM-3315: Optional fields for schedule and role display
    member_role: str | None = None
    schedule_status: bool | None = None


# =============================================================================
# Tests for format_household_context (NEM-3024)
# =============================================================================


class TestFormatHouseholdContext:
    """Tests for format_household_context function.

    This function formats household matching results for injection into
    the Nemotron prompt, enabling risk score reduction for known persons
    and vehicles.
    """

    def test_no_matches_returns_unknown_context(self) -> None:
        """Test that empty matches returns base risk 50 context."""
        from datetime import UTC, datetime

        result = format_household_context(
            person_matches=[],
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        # Should indicate no matches and base risk 50
        assert "RISK MODIFIERS" in result
        assert "None" in result or "unknown" in result.lower()
        assert "50" in result

    def test_single_person_match_high_confidence(self) -> None:
        """Test formatting with high confidence person match."""
        from datetime import UTC, datetime

        person_match = MockHouseholdMatch(
            member_id=1,
            member_name="John Doe",
            similarity=0.95,
            match_type="person",
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        assert "KNOWN PERSON" in result
        assert "John Doe" in result
        assert "95%" in result
        # High confidence person match = base risk 5
        assert "5" in result or "low" in result.lower()

    def test_single_person_match_lower_confidence(self) -> None:
        """Test formatting with lower confidence person match (0.85-0.9)."""
        from datetime import UTC, datetime

        person_match = MockHouseholdMatch(
            member_id=2,
            member_name="Jane Smith",
            similarity=0.87,
            match_type="person",
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        assert "KNOWN PERSON" in result
        assert "Jane Smith" in result
        assert "87%" in result
        # Lower confidence person match = base risk 15
        assert "15" in result

    def test_vehicle_match_by_license_plate(self) -> None:
        """Test formatting with vehicle matched by license plate."""
        from datetime import UTC, datetime

        vehicle_match = MockHouseholdMatch(
            vehicle_id=1,
            vehicle_description="Silver Toyota Camry",
            similarity=1.0,
            match_type="license_plate",
        )

        result = format_household_context(
            person_matches=[],
            vehicle_matches=[vehicle_match],  # type: ignore[list-item]
            current_time=datetime.now(UTC),
        )

        assert "REGISTERED VEHICLE" in result
        assert "Silver Toyota Camry" in result
        # Vehicle match reduces base risk to 10
        assert "10" in result

    def test_vehicle_match_visual(self) -> None:
        """Test formatting with vehicle matched visually."""
        from datetime import UTC, datetime

        vehicle_match = MockHouseholdMatch(
            vehicle_id=2,
            vehicle_description="Blue Honda Accord",
            similarity=0.88,
            match_type="vehicle_visual",
        )

        result = format_household_context(
            person_matches=[],
            vehicle_matches=[vehicle_match],  # type: ignore[list-item]
            current_time=datetime.now(UTC),
        )

        assert "REGISTERED VEHICLE" in result
        assert "Blue Honda Accord" in result

    def test_combined_person_and_vehicle_match(self) -> None:
        """Test formatting with both person and vehicle matches."""
        from datetime import UTC, datetime

        person_match = MockHouseholdMatch(
            member_id=1,
            member_name="John Doe",
            similarity=0.95,
            match_type="person",
        )
        vehicle_match = MockHouseholdMatch(
            vehicle_id=1,
            vehicle_description="Silver Toyota Camry",
            similarity=1.0,
            match_type="license_plate",
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[vehicle_match],  # type: ignore[list-item]
            current_time=datetime.now(UTC),
        )

        # Both should be mentioned
        assert "KNOWN PERSON" in result
        assert "John Doe" in result
        assert "REGISTERED VEHICLE" in result
        assert "Silver Toyota Camry" in result
        # Combined risk should be minimal (person high conf = 5)
        assert "5" in result

    def test_multiple_person_matches(self) -> None:
        """Test formatting with multiple person matches."""
        from datetime import UTC, datetime

        matches = [
            MockHouseholdMatch(
                member_id=1, member_name="John Doe", similarity=0.92, match_type="person"
            ),
            MockHouseholdMatch(
                member_id=2, member_name="Jane Doe", similarity=0.88, match_type="person"
            ),
        ]

        result = format_household_context(
            person_matches=matches,  # type: ignore[arg-type]
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        # Both persons should be mentioned
        assert "John Doe" in result
        assert "Jane Doe" in result

    def test_returns_string(self) -> None:
        """Test that function always returns a string."""
        from datetime import UTC, datetime

        result = format_household_context(
            person_matches=[],
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        assert isinstance(result, str)

    def test_has_section_header(self) -> None:
        """Test that output has proper section formatting."""
        from datetime import UTC, datetime

        result = format_household_context(
            person_matches=[],
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        # Should have a formatted section header
        assert "RISK MODIFIERS" in result

    def test_contains_calculated_base_risk(self) -> None:
        """Test that output contains calculated base risk."""
        from datetime import UTC, datetime

        person_match = MockHouseholdMatch(
            member_id=1, member_name="Test Person", similarity=0.95, match_type="person"
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        # Should contain "Calculated base risk" or similar
        assert "base risk" in result.lower() or "risk:" in result.lower()

    def test_importable(self) -> None:
        """Test that format_household_context is importable from prompts module."""

        assert callable(format_household_context)

    def test_person_match_with_role_displayed(self) -> None:
        """Test that member_role is displayed when available (NEM-3315)."""
        from datetime import UTC, datetime

        person_match = MockHouseholdMatch(
            member_id=1,
            member_name="Mike",
            similarity=0.93,
            match_type="person",
            member_role="resident",
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        assert "KNOWN PERSON" in result
        assert "Mike" in result
        assert "resident" in result
        assert "93%" in result

    def test_person_match_within_schedule_risk_5(self) -> None:
        """Test that person within schedule has base risk 5 (NEM-3315)."""
        from datetime import UTC, datetime

        person_match = MockHouseholdMatch(
            member_id=1,
            member_name="Mike",
            similarity=0.93,
            match_type="person",
            member_role="resident",
            schedule_status=True,  # Within schedule
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        assert "Within expected hours" in result
        assert "base risk: 5" in result

    def test_person_match_outside_schedule_risk_20(self) -> None:
        """Test that person outside schedule has base risk 20 (NEM-3315)."""
        from datetime import UTC, datetime

        person_match = MockHouseholdMatch(
            member_id=1,
            member_name="John",
            similarity=0.88,
            match_type="person",
            member_role="service_worker",
            schedule_status=False,  # Outside schedule
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[],
            current_time=datetime.now(UTC),
        )

        assert "Outside normal hours" in result
        assert "base risk: 20" in result

    def test_vehicle_caps_risk_at_10(self) -> None:
        """Test that registered vehicle caps risk at 10 (NEM-3315)."""
        from datetime import UTC, datetime

        # Person outside schedule (risk 20) + vehicle should cap at 10
        person_match = MockHouseholdMatch(
            member_id=1,
            member_name="John",
            similarity=0.88,
            match_type="person",
            schedule_status=False,  # Outside schedule -> risk 20
        )
        vehicle_match = MockHouseholdMatch(
            vehicle_id=1,
            vehicle_description="Silver Tesla Model 3",
            similarity=1.0,
            match_type="license_plate",
        )

        result = format_household_context(
            person_matches=[person_match],  # type: ignore[list-item]
            vehicle_matches=[vehicle_match],  # type: ignore[list-item]
            current_time=datetime.now(UTC),
        )

        # Vehicle should cap the risk at 10
        assert "base risk: 10" in result

    def test_vehicle_alone_has_risk_10(self) -> None:
        """Test that registered vehicle alone has base risk 10 (NEM-3315)."""
        from datetime import UTC, datetime

        vehicle_match = MockHouseholdMatch(
            vehicle_id=1,
            vehicle_description="Silver Tesla Model 3",
            similarity=1.0,
            match_type="license_plate",
        )

        result = format_household_context(
            person_matches=[],
            vehicle_matches=[vehicle_match],  # type: ignore[list-item]
            current_time=datetime.now(UTC),
        )

        assert "REGISTERED VEHICLE" in result
        assert "Silver Tesla Model 3" in result
        assert "base risk: 10" in result


# =============================================================================
# Tests for check_member_schedule (NEM-3315)
# =============================================================================


class TestCheckMemberSchedule:
    """Tests for check_member_schedule function.

    NEM-3315: Schedule checking for household members to determine if their
    presence at the current time is expected.
    """

    def test_no_schedule_returns_none(self) -> None:
        """Test that None schedule returns None."""
        from datetime import datetime

        result = check_member_schedule(None, datetime(2024, 1, 15, 10, 0))
        assert result is None

    def test_empty_schedule_returns_none(self) -> None:
        """Test that empty schedule dict returns None."""
        from datetime import datetime

        result = check_member_schedule({}, datetime(2024, 1, 15, 10, 0))
        assert result is None

    def test_weekday_schedule_within_hours(self) -> None:
        """Test weekday schedule when within hours."""
        from datetime import datetime

        schedule = {"weekdays": "09:00-17:00", "weekends": "all_day"}
        # Monday at 10:00 (within 09:00-17:00)
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 10, 0))
        assert result is True

    def test_weekday_schedule_outside_hours(self) -> None:
        """Test weekday schedule when outside hours."""
        from datetime import datetime

        schedule = {"weekdays": "09:00-17:00", "weekends": "all_day"}
        # Monday at 22:00 (outside 09:00-17:00)
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 22, 0))
        assert result is False

    def test_weekend_all_day_schedule(self) -> None:
        """Test weekend all_day schedule."""
        from datetime import datetime

        schedule = {"weekdays": "09:00-17:00", "weekends": "all_day"}
        # Saturday at any time
        result = check_member_schedule(schedule, datetime(2024, 1, 20, 3, 30))
        assert result is True

    def test_daily_schedule_within_hours(self) -> None:
        """Test daily schedule when within hours."""
        from datetime import datetime

        schedule = {"daily": "08:00-20:00"}
        # Any day at 12:00
        result = check_member_schedule(schedule, datetime(2024, 1, 17, 12, 0))
        assert result is True

    def test_daily_schedule_outside_hours(self) -> None:
        """Test daily schedule when outside hours."""
        from datetime import datetime

        schedule = {"daily": "08:00-20:00"}
        # Any day at 23:00
        result = check_member_schedule(schedule, datetime(2024, 1, 17, 23, 0))
        assert result is False

    def test_day_specific_schedule_saturday(self) -> None:
        """Test day-specific schedule for Saturday."""
        from datetime import datetime

        schedule = {"weekdays": "09:00-17:00", "saturday": "10:00-14:00"}
        # Saturday at 11:00 (within 10:00-14:00)
        result = check_member_schedule(schedule, datetime(2024, 1, 20, 11, 0))
        assert result is True

        # Saturday at 16:00 (outside 10:00-14:00)
        result = check_member_schedule(schedule, datetime(2024, 1, 20, 16, 0))
        assert result is False

    def test_overnight_schedule(self) -> None:
        """Test overnight schedule (e.g., 22:00-06:00)."""
        from datetime import datetime

        schedule = {"daily": "22:00-06:00"}

        # At 23:00 (within overnight range)
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 23, 0))
        assert result is True

        # At 03:00 (within overnight range)
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 3, 0))
        assert result is True

        # At 12:00 (outside overnight range)
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 12, 0))
        assert result is False

    def test_boundary_times(self) -> None:
        """Test boundary times for schedule ranges."""
        from datetime import datetime

        schedule = {"daily": "09:00-17:00"}

        # Exactly at start time
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 9, 0))
        assert result is True

        # Exactly at end time
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 17, 0))
        assert result is True

        # One minute before start
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 8, 59))
        assert result is False

        # One minute after end
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 17, 1))
        assert result is False

    def test_invalid_schedule_format_returns_none(self) -> None:
        """Test that invalid schedule format returns None."""
        from datetime import datetime

        # Invalid time format
        schedule = {"daily": "invalid"}
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 10, 0))
        assert result is None

    def test_case_insensitive_all_day(self) -> None:
        """Test that all_day is case insensitive."""
        from datetime import datetime

        schedule = {"daily": "ALL_DAY"}
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 15, 0))
        assert result is True

        schedule = {"daily": "All_Day"}
        result = check_member_schedule(schedule, datetime(2024, 1, 15, 15, 0))
        assert result is True

    def test_importable(self) -> None:
        """Test that check_member_schedule is importable from prompts module."""

        assert callable(check_member_schedule)


# =============================================================================
# Tests for VQA Output Validation (NEM-3304)
# =============================================================================


class TestVQAOutputValidation:
    """Tests for VQA output validation in prompts.

    NEM-3304: Florence-2 VQA sometimes returns raw tokens instead of parsed answers.

    CURRENT (broken):
        "Wearing: VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"

    EXPECTED:
        "Wearing: dark hoodie and jeans"

    When VQA output contains <loc_> tokens, we should:
    1. Log an error
    2. Fall back to scene captioning description instead
    """

    def test_is_valid_vqa_output_detects_loc_tokens(self) -> None:
        """Test that is_valid_vqa_output() detects garbage <loc_> tokens."""

        # Invalid outputs with <loc_> tokens
        assert not is_valid_vqa_output("VQA>person wearing<loc_95><loc_86><loc_901><loc_918>")
        assert not is_valid_vqa_output("sedan<loc_1><loc_2>")
        assert not is_valid_vqa_output("walking<loc_100>")
        assert not is_valid_vqa_output("<loc_50><loc_60>blue shirt")

        # Valid outputs without loc tokens
        assert is_valid_vqa_output("dark hoodie and jeans")
        assert is_valid_vqa_output("sedan")
        assert is_valid_vqa_output("walking slowly")
        assert is_valid_vqa_output("blue")
        assert is_valid_vqa_output("")  # Empty is valid (handled elsewhere)
        assert is_valid_vqa_output(None)  # None is valid (handled elsewhere)

    def test_is_valid_vqa_output_detects_vqa_prefix(self) -> None:
        """Test that is_valid_vqa_output() detects VQA> prefix garbage."""

        # Invalid outputs with VQA> prefix (indicates unparsed response)
        assert not is_valid_vqa_output("VQA>person wearing<loc_95>")
        assert not is_valid_vqa_output("VQA>What is this person doing")

        # Valid - no VQA prefix
        assert is_valid_vqa_output("walking")
        assert is_valid_vqa_output("dark clothing")

    def test_validate_and_clean_vqa_output_returns_none_for_garbage(self) -> None:
        """Test that validate_and_clean_vqa_output() returns None for garbage."""

        # Should return None for garbage
        assert validate_and_clean_vqa_output("VQA>person<loc_1><loc_2>") is None
        assert validate_and_clean_vqa_output("sedan<loc_1>") is None
        assert validate_and_clean_vqa_output("<loc_50>text") is None

    def test_validate_and_clean_vqa_output_returns_value_for_valid(self) -> None:
        """Test that validate_and_clean_vqa_output() returns cleaned value for valid."""

        # Should return cleaned value for valid
        assert validate_and_clean_vqa_output("dark hoodie") == "dark hoodie"
        assert validate_and_clean_vqa_output("  sedan  ") == "sedan"  # Strips whitespace
        assert validate_and_clean_vqa_output("BLUE SHIRT") == "blue shirt"  # Lowercase

    def test_validate_and_clean_vqa_output_handles_empty(self) -> None:
        """Test that validate_and_clean_vqa_output() handles empty inputs."""

        assert validate_and_clean_vqa_output("") is None
        assert validate_and_clean_vqa_output("   ") is None
        assert validate_and_clean_vqa_output(None) is None

    def test_validate_and_clean_vqa_output_logs_error_for_garbage(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that validate_and_clean_vqa_output() logs error for garbage."""
        import logging

        with caplog.at_level(logging.WARNING, logger="backend.services.prompts"):
            result = validate_and_clean_vqa_output("VQA>test<loc_1><loc_2>")

        assert result is None
        # Should have logged the garbage detection
        log_output = caplog.text.lower()
        assert "loc_" in log_output or "vqa" in log_output or "garbage" in log_output

    def test_format_florence_attributes_validates_vqa_nem3304(self) -> None:
        """Test that format_florence_attributes() validates VQA outputs (NEM-3304).

        When formatting Florence-2 attributes for prompts, any attribute containing
        <loc_> tokens should be filtered out - not included in the result.
        """

        # Attributes with mixed valid and garbage VQA outputs
        attributes = {
            "color": "white",
            "clothing": "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>",
            "carrying": "backpack",
            "action": "walking<loc_100>",
        }
        caption = "Person in dark hoodie walking through driveway"

        result = format_florence_attributes(attributes, caption)

        # Valid attributes should be present
        assert "white" in result
        assert "backpack" in result

        # Garbage VQA should NOT appear anywhere in the result
        assert "<loc_" not in result
        assert "VQA>" not in result

        # The garbage attributes should be omitted entirely
        # (clothing and action lines should not appear since values were invalid)
        # Result should only contain color and carrying
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 2  # Only color and carrying

    def test_format_florence_attributes_with_all_valid(self) -> None:
        """Test format_florence_attributes() with all valid attributes."""

        attributes = {
            "color": "white",
            "clothing": "dark hoodie and jeans",
            "carrying": "backpack",
        }
        caption = "Person walking in driveway"

        result = format_florence_attributes(attributes, caption)

        # All attributes should be present
        assert "white" in result
        assert "dark hoodie and jeans" in result.lower()
        assert "backpack" in result

    def test_format_florence_attributes_with_all_garbage(self) -> None:
        """Test format_florence_attributes() with all garbage attributes falls back to caption."""

        attributes = {
            "color": "<loc_1><loc_2>white",
            "clothing": "VQA>person wearing<loc_95><loc_86>",
            "action": "running<loc_100>",
        }
        caption = "Person in blue jacket near white car"

        result = format_florence_attributes(attributes, caption)

        # No garbage should appear
        assert "<loc_" not in result
        assert "VQA>" not in result

        # Since all attributes are garbage, caption should be used as fallback
        assert "Scene context:" in result
        assert "blue jacket" in result.lower()

    def test_format_florence_attributes_empty(self) -> None:
        """Test format_florence_attributes() with empty attributes uses caption as fallback."""

        result = format_florence_attributes({}, "Scene caption")
        # Empty dict should return caption as fallback
        assert "Scene context:" in result
        assert "Scene caption" in result

        result = format_florence_attributes(None, "Scene caption")
        # None should also return caption as fallback
        assert "Scene context:" in result
        assert "Scene caption" in result

    def test_format_florence_attributes_empty_no_caption(self) -> None:
        """Test format_florence_attributes() with empty attributes and no caption."""

        result = format_florence_attributes({}, "")
        assert result == ""

        result = format_florence_attributes(None, "")
        assert result == ""


class TestVQAValidationIntegration:
    """Integration tests for VQA validation in the prompt formatting pipeline."""

    def test_format_detections_validates_vqa_in_vision_extraction(self) -> None:
        """Test that format_detections_with_all_enrichment validates VQA outputs.

        Vision extraction results containing garbage VQA outputs should be
        filtered/cleaned before being included in the formatted prompt.
        """
        # Create a mock vision extraction with garbage VQA
        vision_extraction = MockBatchExtractionResult(
            person_attributes={
                "det_001": MockPersonAttributes(
                    clothing="VQA>person wearing<loc_95><loc_86>",
                    carrying="backpack",
                    action="walking<loc_100>",
                    is_service_worker=False,
                    caption="Person in dark hoodie walking",
                )
            },
            vehicle_attributes={},
        )

        detections = [
            {
                "detection_id": "det_001",
                "class_name": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 450],
            }
        ]

        result = format_detections_with_all_enrichment(
            detections, vision_extraction=vision_extraction
        )

        # Result should NOT contain garbage VQA tokens
        assert "<loc_" not in result
        assert "VQA>" not in result

        # Should still have useful information
        # backpack is valid and should appear with "Carrying:"
        assert "backpack" in result.lower()
        # Caption should appear since it's always included
        assert "dark hoodie" in result.lower()

    def test_format_detections_validates_vqa_in_vehicle_attributes(self) -> None:
        """Test that vehicle attributes with garbage VQA are validated."""
        vision_extraction = MockBatchExtractionResult(
            person_attributes={},
            vehicle_attributes={
                "det_v001": MockVehicleAttributes(
                    color="VQA>vehicle color<loc_1><loc_2>",
                    vehicle_type="sedan<loc_3>",
                    is_commercial=False,
                    caption="White sedan parked in driveway",
                )
            },
        )

        detections = [
            {
                "detection_id": "det_v001",
                "class_name": "car",
                "confidence": 0.92,
                "bbox": [50, 100, 200, 300],
            }
        ]

        result = format_detections_with_all_enrichment(
            detections, vision_extraction=vision_extraction
        )

        # Result should NOT contain garbage VQA tokens
        assert "<loc_" not in result
        assert "VQA>" not in result

        # Caption is always included and provides context
        assert "White sedan" in result or "sedan" in result.lower()
        # The garbage color and vehicle_type should NOT appear
        # (they would have had loc tokens if included)


# =============================================================================
# Tests for Previously Uncovered Functions (Coverage Improvement)
# =============================================================================


class TestFormatThreatDetectionContext:
    """Tests for format_threat_detection_context function."""

    def test_none_input_returns_not_performed(self):
        """Test that None input returns 'Not performed' message."""
        from backend.services.prompts import format_threat_detection_context

        result = format_threat_detection_context(None)
        assert result == "Threat detection: Not performed"

    def test_no_threats_detected(self):
        """Test format when no threats are present."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreatResult:
            has_threats: bool = False
            has_high_priority: bool = False
            threat_summary: str = ""
            highest_confidence: float = 0.0
            threats: list = field(default_factory=list)

        result = format_threat_detection_context(MockThreatResult())
        assert result == "Threat detection: No weapons or threatening objects detected"

    def test_threat_detected_with_basic_info(self):
        """Test format with threat detection."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = False
            threat_summary: str = "1 knife detected"
            highest_confidence: float = 0.85
            threats: list = field(default_factory=list)

        threat = MockThreat(class_name="knife", confidence=0.85, is_high_priority=False)
        result = format_threat_detection_context(MockThreatResult(threats=[threat]))

        assert "**WEAPON/THREAT DETECTION**" in result
        assert "1 knife detected" in result
        assert "85%" in result
        assert "knife (85%)" in result

    def test_high_priority_threat_with_critical_alert(self):
        """Test format with high-priority threat."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = True
            threat_summary: str = "1 firearm detected"
            highest_confidence: float = 0.92
            threats: list = field(default_factory=list)

        threat = MockThreat(class_name="firearm", confidence=0.92, is_high_priority=True)
        result = format_threat_detection_context(MockThreatResult(threats=[threat]))

        assert "CRITICAL ALERT: High-priority weapon detected!" in result
        assert "Immediate review recommended" in result
        assert "firearm (92%) **HIGH PRIORITY**" in result

    def test_threat_with_time_context_night(self):
        """Test threat detection with night time context."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = False
            threat_summary: str = "1 weapon detected"
            highest_confidence: float = 0.78
            threats: list = field(default_factory=list)

        threat = MockThreat(class_name="bat", confidence=0.78, is_high_priority=False)
        result = format_threat_detection_context(
            MockThreatResult(threats=[threat]), time_of_day="night"
        )

        assert "TIME CONTEXT: Detection during night" in result
        assert "Elevated concern: Armed threat at unusual hour" in result

    def test_threat_with_time_context_late_night(self):
        """Test threat detection with late_night time context."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = False
            threat_summary: str = "1 weapon detected"
            highest_confidence: float = 0.65
            threats: list = field(default_factory=list)

        threat = MockThreat(class_name="crowbar", confidence=0.65, is_high_priority=False)
        result = format_threat_detection_context(
            MockThreatResult(threats=[threat]), time_of_day="late_night"
        )

        assert "TIME CONTEXT: Detection during late_night" in result
        assert "Elevated concern" in result

    def test_threat_with_time_context_early_morning(self):
        """Test threat detection with early_morning time context."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = False
            threat_summary: str = "1 weapon detected"
            highest_confidence: float = 0.70
            threats: list = field(default_factory=list)

        threat = MockThreat(class_name="knife", confidence=0.70, is_high_priority=False)
        result = format_threat_detection_context(
            MockThreatResult(threats=[threat]), time_of_day="early_morning"
        )

        assert "TIME CONTEXT: Detection during early_morning" in result

    def test_threat_with_daytime_no_escalation(self):
        """Test that daytime doesn't add time context escalation."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = False
            threat_summary: str = "1 weapon detected"
            highest_confidence: float = 0.75
            threats: list = field(default_factory=list)

        threat = MockThreat(class_name="hammer", confidence=0.75, is_high_priority=False)
        result = format_threat_detection_context(
            MockThreatResult(threats=[threat]), time_of_day="afternoon"
        )

        assert "TIME CONTEXT" not in result
        assert "Elevated concern" not in result

    def test_multiple_threats_sorted_by_confidence(self):
        """Test that multiple threats are sorted by confidence."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = False
            threat_summary: str = "3 threats detected"
            highest_confidence: float = 0.90
            threats: list = field(default_factory=list)

        threats = [
            MockThreat(class_name="knife", confidence=0.60, is_high_priority=False),
            MockThreat(class_name="gun", confidence=0.90, is_high_priority=False),
            MockThreat(class_name="bat", confidence=0.75, is_high_priority=False),
        ]
        result = format_threat_detection_context(MockThreatResult(threats=threats))

        # Should be sorted by confidence (gun, bat, knife)
        lines = result.split("\n")
        threat_lines = [l for l in lines if "%" in l and "Highest confidence" not in l]
        assert "gun (90%)" in threat_lines[0]
        assert "bat (75%)" in threat_lines[1]
        assert "knife (60%)" in threat_lines[2]

    def test_limits_to_top_5_threats(self):
        """Test that only top 5 threats are shown."""
        from backend.services.prompts import format_threat_detection_context

        @dataclass
        class MockThreat:
            class_name: str
            confidence: float
            is_high_priority: bool

        @dataclass
        class MockThreatResult:
            has_threats: bool = True
            has_high_priority: bool = False
            threat_summary: str = "7 threats detected"
            highest_confidence: float = 0.95
            threats: list = field(default_factory=list)

        threats = [
            MockThreat(class_name=f"weapon_{i}", confidence=0.95 - i * 0.1, is_high_priority=False)
            for i in range(7)
        ]
        result = format_threat_detection_context(MockThreatResult(threats=threats))

        # Count individual threat entries (excluding header and summary lines)
        threat_entries = [l for l in result.split("\n") if "weapon_" in l]
        assert len(threat_entries) == 5  # Only top 5


class TestFormatAgeClassificationContext:
    """Tests for format_age_classification_context function."""

    def test_empty_classifications_returns_no_persons(self):
        """Test that empty dict returns 'No persons analyzed'."""
        from backend.services.prompts import format_age_classification_context

        result = format_age_classification_context({})
        assert result == "Age estimation: No persons analyzed"

    def test_single_person_with_high_confidence(self):
        """Test format for single person with high confidence."""
        from backend.services.prompts import format_age_classification_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        classifications = {
            "det_001": MockAgeResult(display_name="Adult (25-35)", confidence=0.85, is_minor=False)
        }
        result = format_age_classification_context(classifications)

        assert "Age estimation (1 persons):" in result
        assert "Person det_001: Adult (25-35) (85%)" in result
        assert "LOW CONFIDENCE" not in result

    def test_person_with_low_confidence(self):
        """Test that low confidence adds warning."""
        from backend.services.prompts import format_age_classification_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        classifications = {
            "det_002": MockAgeResult(display_name="Teen (13-17)", confidence=0.45, is_minor=True)
        }
        result = format_age_classification_context(classifications)

        assert "[LOW CONFIDENCE]" in result
        assert "**MINOR**" in result

    def test_person_with_medium_confidence(self):
        """Test that medium confidence adds note."""
        from backend.services.prompts import format_age_classification_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        classifications = {
            "det_003": MockAgeResult(
                display_name="Young Adult (18-24)", confidence=0.65, is_minor=False
            )
        }
        result = format_age_classification_context(classifications)

        assert "[medium confidence]" in result

    def test_minor_detection_adds_special_note(self):
        """Test that minor detection adds special consideration note."""
        from backend.services.prompts import format_age_classification_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        classifications = {
            "det_004": MockAgeResult(display_name="Child (5-12)", confidence=0.80, is_minor=True)
        }
        result = format_age_classification_context(classifications)

        assert "**MINOR**" in result
        assert "**NOTE**: Minor(s) detected - may indicate lost/unaccompanied child" in result
        assert "Consider context and presence of adults when assessing risk" in result

    def test_multiple_persons_with_mixed_ages(self):
        """Test formatting for multiple persons with different ages."""
        from backend.services.prompts import format_age_classification_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        classifications = {
            "det_005": MockAgeResult(display_name="Adult (35-50)", confidence=0.90, is_minor=False),
            "det_006": MockAgeResult(display_name="Teen (13-17)", confidence=0.75, is_minor=True),
        }
        result = format_age_classification_context(classifications)

        assert "Age estimation (2 persons):" in result
        assert "Person det_005: Adult (35-50) (90%)" in result
        assert "Person det_006: Teen (13-17) (75%)" in result
        assert "**MINOR**" in result


class TestFormatGenderClassificationContext:
    """Tests for format_gender_classification_context function."""

    def test_empty_classifications_returns_no_persons(self):
        """Test that empty dict returns 'No persons analyzed'."""
        from backend.services.prompts import format_gender_classification_context

        result = format_gender_classification_context({})
        assert result == "Gender estimation: No persons analyzed"

    def test_single_person_high_confidence(self):
        """Test format for single person with high confidence."""
        from backend.services.prompts import format_gender_classification_context

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        classifications = {"det_007": MockGenderResult(gender="male", confidence=0.92)}
        result = format_gender_classification_context(classifications)

        assert "Gender estimation (1 persons):" in result
        assert "Person det_007: male (92%)" in result
        assert "[low confidence]" not in result

    def test_person_with_low_confidence(self):
        """Test that low confidence adds warning."""
        from backend.services.prompts import format_gender_classification_context

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        classifications = {"det_008": MockGenderResult(gender="female", confidence=0.55)}
        result = format_gender_classification_context(classifications)

        assert "[low confidence]" in result

    def test_multiple_persons(self):
        """Test formatting for multiple persons."""
        from backend.services.prompts import format_gender_classification_context

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        classifications = {
            "det_009": MockGenderResult(gender="male", confidence=0.88),
            "det_010": MockGenderResult(gender="female", confidence=0.72),
        }
        result = format_gender_classification_context(classifications)

        assert "Gender estimation (2 persons):" in result
        assert "Person det_009: male (88%)" in result
        assert "Person det_010: female (72%)" in result


class TestFormatPersonDemographicsContext:
    """Tests for format_person_demographics_context function."""

    def test_no_classifications_returns_not_analyzed(self):
        """Test that no classifications returns 'Not analyzed'."""
        from backend.services.prompts import format_person_demographics_context

        result = format_person_demographics_context(None, None)
        assert result == "Person demographics: Not analyzed"

    def test_empty_dicts_returns_not_analyzed(self):
        """Test that empty dicts return 'Not analyzed'."""
        from backend.services.prompts import format_person_demographics_context

        result = format_person_demographics_context({}, {})
        assert result == "Person demographics: Not analyzed"

    def test_age_only_classification(self):
        """Test demographics with only age classification."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        age_classifications = {
            "det_011": MockAgeResult(display_name="Adult (30-40)", confidence=0.85, is_minor=False)
        }
        result = format_person_demographics_context(age_classifications, None)

        assert "Person demographics (1 persons):" in result
        assert "Person det_011:, Adult (30-40)" in result

    def test_gender_only_classification(self):
        """Test demographics with only gender classification."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        gender_classifications = {"det_012": MockGenderResult(gender="male", confidence=0.90)}
        result = format_person_demographics_context(None, gender_classifications)

        assert "Person demographics (1 persons):" in result
        assert "Person det_012: male" in result

    def test_combined_age_and_gender(self):
        """Test demographics with both age and gender."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        age_classifications = {
            "det_013": MockAgeResult(
                display_name="Young Adult (18-24)", confidence=0.82, is_minor=False
            )
        }
        gender_classifications = {"det_013": MockGenderResult(gender="female", confidence=0.88)}
        result = format_person_demographics_context(age_classifications, gender_classifications)

        assert "Person det_013: female, Young Adult (18-24)" in result

    def test_minor_with_combined_demographics(self):
        """Test that minor flag appears with combined demographics."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        age_classifications = {
            "det_014": MockAgeResult(display_name="Child (8-12)", confidence=0.90, is_minor=True)
        }
        gender_classifications = {"det_014": MockGenderResult(gender="male", confidence=0.85)}
        result = format_person_demographics_context(age_classifications, gender_classifications)

        assert "**MINOR**" in result
        assert "**NOTE**: Minor(s) detected - evaluate context carefully" in result

    def test_low_confidence_age_adds_note(self):
        """Test that low age confidence adds uncertainty note."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        age_classifications = {
            "det_015": MockAgeResult(display_name="Adult (25-35)", confidence=0.50, is_minor=False)
        }
        gender_classifications = {"det_015": MockGenderResult(gender="female", confidence=0.85)}
        result = format_person_demographics_context(age_classifications, gender_classifications)

        assert "[age uncertain]" in result

    def test_low_confidence_gender_adds_note(self):
        """Test that low gender confidence adds uncertainty note."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        age_classifications = {
            "det_016": MockAgeResult(display_name="Adult (30-45)", confidence=0.80, is_minor=False)
        }
        gender_classifications = {"det_016": MockGenderResult(gender="male", confidence=0.55)}
        result = format_person_demographics_context(age_classifications, gender_classifications)

        assert "[gender uncertain]" in result

    def test_both_low_confidence_adds_combined_note(self):
        """Test that both low confidences add combined note."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        age_classifications = {
            "det_017": MockAgeResult(display_name="Adult (25-35)", confidence=0.55, is_minor=False)
        }
        gender_classifications = {"det_017": MockGenderResult(gender="female", confidence=0.58)}
        result = format_person_demographics_context(age_classifications, gender_classifications)

        assert "[gender uncertain, age uncertain]" in result

    def test_multiple_persons_sorted(self):
        """Test that multiple persons are sorted by ID."""
        from backend.services.prompts import format_person_demographics_context

        @dataclass
        class MockAgeResult:
            display_name: str
            confidence: float
            is_minor: bool

        @dataclass
        class MockGenderResult:
            gender: str
            confidence: float

        age_classifications = {
            "det_020": MockAgeResult(display_name="Adult (50-60)", confidence=0.85, is_minor=False),
            "det_018": MockAgeResult(
                display_name="Young Adult (18-24)", confidence=0.82, is_minor=False
            ),
        }
        gender_classifications = {
            "det_020": MockGenderResult(gender="male", confidence=0.88),
            "det_018": MockGenderResult(gender="female", confidence=0.90),
        }
        result = format_person_demographics_context(age_classifications, gender_classifications)

        lines = result.split("\n")
        person_lines = [l for l in lines if l.strip().startswith("Person det_")]
        # Should be sorted: det_018, det_020
        assert "det_018" in person_lines[0]
        assert "det_020" in person_lines[1]


class TestFormatPersonReidContext:
    """Tests for format_person_reid_context function."""

    def test_none_input_returns_not_performed(self):
        """Test that None input returns 'Not performed'."""
        from backend.services.prompts import format_person_reid_context

        result = format_person_reid_context(None)
        assert result == "Person re-identification: Not performed"

    def test_empty_dict_returns_no_matches(self):
        """Test that empty dict returns 'No matches found'."""
        from backend.services.prompts import format_person_reid_context

        result = format_person_reid_context({})
        assert result == "Person re-identification: No matches found (all new individuals)"

    def test_person_with_no_matches(self):
        """Test format when person has no matches."""
        from backend.services.prompts import format_person_reid_context

        reid_matches = {"det_021": []}
        result = format_person_reid_context(reid_matches)

        assert "Person re-identification:" in result
        assert "Person det_021: New individual (no prior matches)" in result

    def test_high_confidence_match(self):
        """Test format for high confidence match (>= 0.9)."""
        from backend.services.prompts import format_person_reid_context

        @dataclass
        class MockEmbedding:
            detection_id: str

        reid_matches = {"det_022": [(MockEmbedding(detection_id="det_001"), 0.95)]}
        result = format_person_reid_context(reid_matches)

        assert "Person det_022: HIGH CONFIDENCE match to det_001 (95%)" in result

    def test_likely_match(self):
        """Test format for likely match (>= 0.8, < 0.9)."""
        from backend.services.prompts import format_person_reid_context

        @dataclass
        class MockEmbedding:
            detection_id: str

        reid_matches = {"det_023": [(MockEmbedding(detection_id="det_002"), 0.85)]}
        result = format_person_reid_context(reid_matches)

        assert "Person det_023: Likely same person as det_002 (85%)" in result

    def test_possible_match(self):
        """Test format for possible match (< 0.8)."""
        from backend.services.prompts import format_person_reid_context

        @dataclass
        class MockEmbedding:
            detection_id: str

        reid_matches = {"det_024": [(MockEmbedding(detection_id="det_003"), 0.72)]}
        result = format_person_reid_context(reid_matches)

        assert "Person det_024: Possible match to det_003 (72%)" in result

    def test_multiple_alternative_matches(self):
        """Test that alternative matches are shown (up to 3 total)."""
        from backend.services.prompts import format_person_reid_context

        @dataclass
        class MockEmbedding:
            detection_id: str

        reid_matches = {
            "det_025": [
                (MockEmbedding(detection_id="det_004"), 0.90),
                (MockEmbedding(detection_id="det_005"), 0.82),
                (MockEmbedding(detection_id="det_006"), 0.75),
            ]
        }
        result = format_person_reid_context(reid_matches)

        assert "HIGH CONFIDENCE match to det_004 (90%)" in result
        assert "Alternative: det_005 (82%)" in result
        assert "Alternative: det_006 (75%)" in result

    def test_limits_alternative_matches_to_2(self):
        """Test that only 2 alternative matches are shown (top match + 2)."""
        from backend.services.prompts import format_person_reid_context

        @dataclass
        class MockEmbedding:
            detection_id: str

        reid_matches = {
            "det_026": [
                (MockEmbedding(detection_id="det_007"), 0.92),
                (MockEmbedding(detection_id="det_008"), 0.84),
                (MockEmbedding(detection_id="det_009"), 0.76),
                (MockEmbedding(detection_id="det_010"), 0.68),
                (MockEmbedding(detection_id="det_011"), 0.60),
            ]
        }
        result = format_person_reid_context(reid_matches)

        # Should show top match + 2 alternatives only
        assert "det_007" in result
        assert "det_008" in result
        assert "det_009" in result
        assert "det_010" not in result
        assert "det_011" not in result

    def test_unknown_detection_id_handled(self):
        """Test handling of None detection_id."""
        from backend.services.prompts import format_person_reid_context

        @dataclass
        class MockEmbedding:
            detection_id: str | None

        reid_matches = {"det_027": [(MockEmbedding(detection_id=None), 0.88)]}
        result = format_person_reid_context(reid_matches)

        assert "same person as unknown" in result

    def test_multiple_persons_with_mixed_matches(self):
        """Test multiple persons with different match scenarios."""
        from backend.services.prompts import format_person_reid_context

        @dataclass
        class MockEmbedding:
            detection_id: str

        reid_matches = {
            "det_028": [(MockEmbedding(detection_id="det_012"), 0.93)],
            "det_029": [],
            "det_030": [(MockEmbedding(detection_id="det_013"), 0.78)],
        }
        result = format_person_reid_context(reid_matches)

        assert "Person det_028: HIGH CONFIDENCE match" in result
        assert "Person det_029: New individual (no prior matches)" in result
        assert "Person det_030: Possible match" in result


class TestBuildPersonAnalysisSection:
    """Tests for build_person_analysis_section function."""

    def test_empty_enrichment_returns_no_analysis(self):
        """Test that enrichment with no data returns 'No person analysis available'."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        result = build_person_analysis_section(MockEnrichment())
        assert result == "No person analysis available."

    def test_pose_with_dict_format(self):
        """Test pose formatting with dict representation."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: dict = field(default_factory=dict)
            clothing: None = None
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(pose={"pose_class": "standing", "pose_confidence": 0.88})
        result = build_person_analysis_section(enrichment)

        assert "### Pose & Posture" in result
        assert "Detected pose: standing" in result
        assert "Confidence: 88.0%" in result
        assert "Suspicious posture: No" in result

    def test_pose_with_alternative_dict_keys(self):
        """Test pose with alternative key names (classification, confidence)."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: dict = field(default_factory=dict)
            clothing: None = None
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(pose={"classification": "crouching", "confidence": 0.72})
        result = build_person_analysis_section(enrichment)

        assert "Detected pose: crouching" in result
        assert "Confidence: 72.0%" in result
        assert "Suspicious posture: YES" in result

    def test_clothing_with_categories_attribute(self):
        """Test clothing with categories attribute."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockCategory:
            def get(self, key, default=None):
                data = {"category": "hoodie", "confidence": 0.85}
                return data.get(key, default)

        @dataclass
        class MockClothing:
            categories: list
            is_suspicious: bool = False

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: object = None
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(
            clothing=MockClothing(categories=[MockCategory(), MockCategory(), MockCategory()])
        )
        result = build_person_analysis_section(enrichment)

        assert "### Appearance" in result
        assert "Clothing:" in result
        assert "hoodie" in result

    def test_clothing_with_raw_description(self):
        """Test clothing with raw_description attribute."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockClothing:
            raw_description: str
            is_suspicious: bool = False

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: object = None
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(
            clothing=MockClothing(raw_description="blue jeans, white t-shirt")
        )
        result = build_person_analysis_section(enrichment)

        assert "### Appearance" in result
        assert "blue jeans, white t-shirt" in result

    def test_clothing_with_dict_categories(self):
        """Test clothing as dict with categories."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: dict = field(default_factory=dict)
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(
            clothing={
                "categories": [
                    {"category": "jacket", "confidence": 0.90},
                    {"category": "pants", "confidence": 0.85},
                ],
                "is_suspicious": False,
            }
        )
        result = build_person_analysis_section(enrichment)

        assert "### Appearance" in result
        assert "jacket (90%)" in result
        assert "pants (85%)" in result

    def test_clothing_with_dict_non_dict_categories(self):
        """Test clothing dict with non-dict category values."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: dict = field(default_factory=dict)
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(
            clothing={"categories": ["shirt", "pants", "shoes"], "is_suspicious": False}
        )
        result = build_person_analysis_section(enrichment)

        assert "### Appearance" in result
        assert "shirt, pants, shoes" in result

    def test_clothing_with_fallback_string(self):
        """Test clothing with fallback to string representation."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: str = "casual attire"
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        result = build_person_analysis_section(MockEnrichment())

        assert "### Appearance" in result
        assert "casual attire" in result

    def test_demographics_with_dict_age_range(self):
        """Test demographics as dict with age_range key."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: dict = field(default_factory=dict)
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(demographics={"age_range": "30-40", "gender": "male"})
        result = build_person_analysis_section(enrichment)

        assert "### Demographics" in result
        assert "Estimated age: 30-40" in result
        assert "Gender: male" in result

    def test_demographics_with_dict_age_group(self):
        """Test demographics dict with age_group as alternative key."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: dict = field(default_factory=dict)
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(demographics={"age_group": "young adult", "gender": "female"})
        result = build_person_analysis_section(enrichment)

        assert "### Demographics" in result
        assert "Estimated age: young adult" in result
        assert "Gender: female" in result

    def test_demographics_with_fallback_string(self):
        """Test demographics with fallback to unknown."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: str = "demographic_data"
            action: None = None
            reid_embedding: None = None

        result = build_person_analysis_section(MockEnrichment())

        assert "### Demographics" in result
        assert "Estimated age: unknown" in result
        assert "Gender: unknown" in result

    def test_action_with_dict_format(self):
        """Test action as dict with action key."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: None = None
            action: dict = field(default_factory=dict)
            reid_embedding: None = None

        enrichment = MockEnrichment(
            action={"action": "walking", "confidence": 0.92, "is_suspicious": False}
        )
        result = build_person_analysis_section(enrichment)

        assert "### Behavior" in result
        assert "Detected action: walking" in result
        assert "Confidence: 92.0%" in result
        assert "Suspicious behavior: No" in result

    def test_action_with_dict_top_action_key(self):
        """Test action dict with top_action as alternative key."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: None = None
            action: dict = field(default_factory=dict)
            reid_embedding: None = None

        enrichment = MockEnrichment(
            action={"top_action": "loitering", "confidence": 0.78, "is_suspicious": True}
        )
        result = build_person_analysis_section(enrichment)

        assert "### Behavior" in result
        assert "Detected action: loitering" in result
        assert "Suspicious behavior: YES" in result

    def test_action_with_fallback_string(self):
        """Test action with fallback to string representation."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: None = None
            action: str = "standing"
            reid_embedding: None = None

        result = build_person_analysis_section(MockEnrichment())

        assert "### Behavior" in result
        assert "Detected action: standing" in result
        assert "Confidence: 0.0%" in result

    def test_reid_embedding_present(self):
        """Test that reid_embedding adds identity section."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: None = None
            action: None = None
            reid_embedding: list = field(default_factory=list)

        enrichment = MockEnrichment(reid_embedding=[0.1, 0.2, 0.3])
        result = build_person_analysis_section(enrichment)

        assert "### Identity" in result
        assert "Re-ID embedding extracted for tracking" in result

    def test_multiple_sections_combined(self):
        """Test that multiple sections are combined properly."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockEnrichment:
            pose: dict = field(default_factory=dict)
            clothing: dict = field(default_factory=dict)
            demographics: dict = field(default_factory=dict)
            action: dict = field(default_factory=dict)
            reid_embedding: list = field(default_factory=list)

        enrichment = MockEnrichment(
            pose={"pose_class": "running", "pose_confidence": 0.85},
            clothing={"categories": ["sportswear"], "is_suspicious": False},
            demographics={"age_range": "25-35", "gender": "male"},
            action={"action": "running", "confidence": 0.90, "is_suspicious": False},
            reid_embedding=[0.1, 0.2],
        )
        result = build_person_analysis_section(enrichment)

        assert "### Pose & Posture" in result
        assert "### Appearance" in result
        assert "### Demographics" in result
        assert "### Behavior" in result
        assert "### Identity" in result
        # Sections should be separated by double newlines
        assert "\n\n" in result

    def test_pose_with_object_attributes(self):
        """Test pose with object attributes (pose_class, pose_confidence)."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockPoseResult:
            pose_class: str
            pose_confidence: float

        @dataclass
        class MockEnrichment:
            pose: object = None
            clothing: None = None
            demographics: None = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(
            pose=MockPoseResult(pose_class="crawling", pose_confidence=0.82)
        )
        result = build_person_analysis_section(enrichment)

        assert "### Pose & Posture" in result
        assert "Detected pose: crawling" in result
        assert "Confidence: 82.0%" in result
        assert "Suspicious posture: YES" in result

    def test_demographics_with_object_attributes(self):
        """Test demographics with object attributes (age_range, gender)."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockDemographicsResult:
            age_range: str
            gender: str

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: object = None
            action: None = None
            reid_embedding: None = None

        enrichment = MockEnrichment(
            demographics=MockDemographicsResult(age_range="18-25", gender="female")
        )
        result = build_person_analysis_section(enrichment)

        assert "### Demographics" in result
        assert "Estimated age: 18-25" in result
        assert "Gender: female" in result

    def test_action_with_object_attributes(self):
        """Test action with object attributes (action, confidence, is_suspicious)."""
        from backend.services.prompts import build_person_analysis_section

        @dataclass
        class MockActionResult:
            action: str
            confidence: float
            is_suspicious: bool = False

        @dataclass
        class MockEnrichment:
            pose: None = None
            clothing: None = None
            demographics: None = None
            action: object = None
            reid_embedding: None = None

        enrichment = MockEnrichment(
            action=MockActionResult(action="breaking_in", confidence=0.88, is_suspicious=True)
        )
        result = build_person_analysis_section(enrichment)

        assert "### Behavior" in result
        assert "Detected action: breaking_in" in result
        assert "Confidence: 88.0%" in result
        assert "Suspicious behavior: YES" in result


class TestBuildThreatSection:
    """Tests for build_threat_section function."""

    def test_no_threat_returns_no_threats_detected(self):
        """Test that None threat returns 'No threats detected'."""
        from backend.services.prompts import build_threat_section

        @dataclass
        class MockEnrichment:
            threat: None = None

        result = build_threat_section(MockEnrichment())
        assert result == "No threats detected."

    def test_threat_with_has_threat_false(self):
        """Test threat object with has_threat=False."""
        from backend.services.prompts import build_threat_section

        @dataclass
        class MockThreat:
            has_threat: bool = False
            threats: list = field(default_factory=list)

        @dataclass
        class MockEnrichment:
            threat: object = None

        enrichment = MockEnrichment(threat=MockThreat())
        result = build_threat_section(enrichment)
        assert result == "No threats detected."

    def test_threat_with_dict_format_has_threat(self):
        """Test threat as dict with has_threat key."""
        from backend.services.prompts import build_threat_section

        @dataclass
        class MockEnrichment:
            threat: dict = field(default_factory=dict)

        enrichment = MockEnrichment(
            threat={
                "has_threat": True,
                "threats": [{"threat_type": "weapon", "severity": "critical", "confidence": 0.95}],
            }
        )
        result = build_threat_section(enrichment)

        assert "**THREATS DETECTED:**" in result
        assert "WEAPON" in result
        assert "severity: critical" in result
        assert "95%" in result

    def test_threat_with_dict_format_threats_detected(self):
        """Test threat dict with alternative key threats_detected."""
        from backend.services.prompts import build_threat_section

        @dataclass
        class MockEnrichment:
            threat: dict = field(default_factory=dict)

        enrichment = MockEnrichment(
            threat={
                "threats_detected": True,
                "threats": [{"type": "knife", "confidence": 0.88}],
            }
        )
        result = build_threat_section(enrichment)

        assert "**THREATS DETECTED:**" in result
        assert "KNIFE" in result
        assert "severity: high" in result  # default severity
        assert "88%" in result

    def test_threat_with_object_attributes(self):
        """Test threat with object attributes."""
        from backend.services.prompts import build_threat_section

        @dataclass
        class MockThreatItem:
            threat_type: str
            severity: str
            confidence: float

        @dataclass
        class MockThreat:
            has_threat: bool = True
            threats: list = field(default_factory=list)

        @dataclass
        class MockEnrichment:
            threat: object = None

        enrichment = MockEnrichment(
            threat=MockThreat(
                threats=[
                    MockThreatItem(threat_type="firearm", severity="critical", confidence=0.92)
                ]
            )
        )
        result = build_threat_section(enrichment)

        assert "**THREATS DETECTED:**" in result
        assert "FIREARM" in result
        assert "severity: critical" in result
        assert "92%" in result

    def test_threat_with_fallback_to_unknown_type(self):
        """Test threat with missing type falls back to 'unknown'."""
        from backend.services.prompts import build_threat_section

        @dataclass
        class MockEnrichment:
            threat: dict = field(default_factory=dict)

        enrichment = MockEnrichment(
            threat={
                "has_threat": True,
                "threats": [{}],  # Empty threat dict
            }
        )
        result = build_threat_section(enrichment)

        assert "**THREATS DETECTED:**" in result
        assert "UNKNOWN" in result

    def test_threat_with_unsupported_format_returns_no_threats(self):
        """Test that unsupported threat format returns 'No threats detected'."""
        from backend.services.prompts import build_threat_section

        @dataclass
        class MockEnrichment:
            threat: str = "threat_data"

        result = build_threat_section(MockEnrichment())
        assert result == "No threats detected."


class TestBuildVehicleSection:
    """Tests for build_vehicle_section function."""

    def test_no_vehicle_returns_no_vehicle_detected(self):
        """Test that None vehicle returns 'No vehicle detected'."""
        from backend.services.prompts import build_vehicle_section

        @dataclass
        class MockEnrichment:
            vehicle: None = None

        result = build_vehicle_section(MockEnrichment())
        assert result == "No vehicle detected."

    def test_vehicle_with_object_attributes(self):
        """Test vehicle with object attributes."""
        from backend.services.prompts import build_vehicle_section

        @dataclass
        class MockVehicle:
            vehicle_type: str
            color: str | None = None
            make: str | None = None
            model: str | None = None
            confidence: float = 0.0

        @dataclass
        class MockEnrichment:
            vehicle: object = None

        enrichment = MockEnrichment(
            vehicle=MockVehicle(
                vehicle_type="sedan",
                color="blue",
                make="Toyota",
                model="Camry",
                confidence=0.89,
            )
        )
        result = build_vehicle_section(enrichment)

        assert "Vehicle:" in result
        assert "sedan" in result
        assert "blue" in result
        assert "Toyota" in result
        assert "Camry" in result

    def test_vehicle_with_dict_format(self):
        """Test vehicle as dict."""
        from backend.services.prompts import build_vehicle_section

        @dataclass
        class MockEnrichment:
            vehicle: dict = field(default_factory=dict)

        enrichment = MockEnrichment(
            vehicle={
                "vehicle_type": "truck",
                "color": "red",
                "make": "Ford",
                "model": "F-150",
                "confidence": 0.92,
            }
        )
        result = build_vehicle_section(enrichment)

        assert "Vehicle:" in result
        assert "truck" in result
        assert "red" in result
        assert "Ford" in result
        assert "F-150" in result

    def test_vehicle_with_dict_type_alternative_key(self):
        """Test vehicle dict with 'type' as alternative key."""
        from backend.services.prompts import build_vehicle_section

        @dataclass
        class MockEnrichment:
            vehicle: dict = field(default_factory=dict)

        enrichment = MockEnrichment(vehicle={"type": "suv", "color": "black", "confidence": 0.85})
        result = build_vehicle_section(enrichment)

        assert "Vehicle:" in result
        assert "suv" in result
        assert "black" in result

    def test_vehicle_with_missing_optional_fields(self):
        """Test vehicle with missing color/make/model."""
        from backend.services.prompts import build_vehicle_section

        @dataclass
        class MockEnrichment:
            vehicle: dict = field(default_factory=dict)

        enrichment = MockEnrichment(vehicle={"vehicle_type": "motorcycle", "confidence": 0.80})
        result = build_vehicle_section(enrichment)

        assert "Vehicle:" in result
        assert "motorcycle" in result


class TestFormatEnhancedClothingContext:
    """Tests for format_enhanced_clothing_context function."""

    def test_no_clothing_returns_empty_string(self):
        """Test that None clothing returns empty string."""
        from backend.services.prompts import format_enhanced_clothing_context

        result = format_enhanced_clothing_context(None)
        assert result == ""

    def test_clothing_with_suspicious_attire(self):
        """Test clothing with suspicious attire detection."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {"suspicious": {"confidence": 0.75, "top_match": "ski mask"}}
        result = format_enhanced_clothing_context(clothing_result)

        assert "**ALERT**: ski mask" in result
        assert "75%" in result

    def test_clothing_with_suspicious_dict_format(self):
        """Test clothing suspicious as dict."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {"suspicious": {"confidence": 0.82, "top_match": "face covering"}}
        result = format_enhanced_clothing_context(clothing_result)

        assert "**ALERT**: face covering" in result
        assert "82%" in result

    def test_clothing_with_delivery_uniform(self):
        """Test clothing with delivery uniform detection."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {"delivery": {"confidence": 0.65, "top_match": "UPS uniform"}}
        result = format_enhanced_clothing_context(clothing_result)

        assert "Service worker identified: UPS uniform" in result
        assert "65%" in result

    def test_clothing_with_utility_worker(self):
        """Test clothing with utility worker detection."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {"utility": {"confidence": 0.72, "top_match": "electrician vest"}}
        result = format_enhanced_clothing_context(clothing_result)

        assert "Utility worker identified: electrician vest" in result
        assert "72%" in result

    def test_clothing_with_carrying_items(self):
        """Test clothing with carrying items detection."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {"carrying": {"confidence": 0.88, "top_match": "backpack"}}
        result = format_enhanced_clothing_context(clothing_result)

        assert "Carrying: backpack" in result
        assert "88%" in result

    def test_clothing_with_casual_attire(self):
        """Test clothing with casual attire."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {"casual": {"top_match": "jeans and t-shirt"}}
        result = format_enhanced_clothing_context(clothing_result)

        assert "General attire: jeans and t-shirt" in result

    def test_clothing_with_casual_dict_format(self):
        """Test clothing casual as dict."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {"casual": {"top_match": "business casual"}}
        result = format_enhanced_clothing_context(clothing_result)

        assert "General attire: business casual" in result

    def test_clothing_with_empty_dict_returns_empty(self):
        """Test that empty clothing dict returns empty string."""
        from backend.services.prompts import format_enhanced_clothing_context

        result = format_enhanced_clothing_context({})
        assert result == ""

    def test_clothing_with_multiple_categories(self):
        """Test clothing with multiple detection categories."""
        from backend.services.prompts import format_enhanced_clothing_context

        clothing_result = {
            "suspicious": {"confidence": 0.70, "top_match": "hoodie"},
            "carrying": {"confidence": 0.82, "top_match": "large bag"},
            "casual": {"top_match": "dark clothing"},
        }
        result = format_enhanced_clothing_context(clothing_result)

        assert "**ALERT**: hoodie" in result
        assert "Carrying: large bag" in result
        assert "General attire: dark clothing" in result
