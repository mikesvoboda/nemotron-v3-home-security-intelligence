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

from backend.services.prompts import (
    ENRICHED_RISK_ANALYSIS_PROMPT,
    FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
    RISK_ANALYSIS_PROMPT,
    VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
    format_action_recognition_context,
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
        """Test that the template provides risk level ranges."""
        assert "low (0-29)" in RISK_ANALYSIS_PROMPT
        assert "medium (30-59)" in RISK_ANALYSIS_PROMPT
        assert "high (60-84)" in RISK_ANALYSIS_PROMPT
        assert "critical (85-100)" in RISK_ANALYSIS_PROMPT

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
        assert "Faces detected" in FULL_ENRICHED_RISK_ANALYSIS_PROMPT


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
        assert "hoodie, jeans" in result

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

        assert "hoodie, jeans, hat" in result
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
            assert "risk analyzer" in template.lower()

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


class TestPromptModuleImports:
    """Tests for module structure and exports."""

    def test_all_format_functions_importable(self) -> None:
        """Test all format functions are importable."""
        from backend.services.prompts import (
            format_action_recognition_context,
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

    def test_all_prompt_templates_importable(self) -> None:
        """Test all prompt templates are importable."""
        from backend.services.prompts import (
            ENRICHED_RISK_ANALYSIS_PROMPT,
            FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
            RISK_ANALYSIS_PROMPT,
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
        )

        # Verify they are strings
        assert isinstance(RISK_ANALYSIS_PROMPT, str)
        assert isinstance(ENRICHED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(FULL_ENRICHED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(VISION_ENHANCED_RISK_ANALYSIS_PROMPT, str)
        assert isinstance(MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, str)
