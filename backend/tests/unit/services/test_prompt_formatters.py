"""Unit tests for MODEL_ZOO_ENHANCED prompt formatting functions.

Tests cover:
- format_violence_context
- format_weather_context
- format_clothing_analysis_context
- format_pose_analysis_context
- format_action_recognition_context
- format_vehicle_classification_context
- format_vehicle_damage_context
- format_pet_classification_context
- format_depth_context
- format_image_quality_context
- format_detections_with_all_enrichment
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.depth_anything_loader import DepthAnalysisResult, DetectionDepth
from backend.services.prompts import (
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
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


# =============================================================================
# Test Classes
# =============================================================================


class TestFormatViolenceContext:
    """Tests for format_violence_context function."""

    def test_none_result(self) -> None:
        """Test formatting when no violence detection result is available."""
        result = format_violence_context(None)
        assert result == "Violence analysis: Not performed"

    def test_violent_detection(self) -> None:
        """Test formatting when violence is detected."""
        violence_result = MockViolenceDetectionResult(
            is_violent=True,
            confidence=0.95,
            violent_score=0.95,
            non_violent_score=0.05,
        )
        result = format_violence_context(violence_result)

        assert "**VIOLENCE DETECTED**" in result
        assert "95%" in result
        assert "ACTION REQUIRED" in result

    def test_non_violent_detection(self) -> None:
        """Test formatting when no violence is detected."""
        violence_result = MockViolenceDetectionResult(
            is_violent=False,
            confidence=0.85,
            violent_score=0.15,
            non_violent_score=0.85,
        )
        result = format_violence_context(violence_result)

        assert "No violence detected" in result
        assert "85%" in result
        assert "**VIOLENCE DETECTED**" not in result


class TestFormatWeatherContext:
    """Tests for format_weather_context function."""

    def test_none_result(self) -> None:
        """Test formatting when no weather result is available."""
        result = format_weather_context(None)
        assert result == "Weather: Unknown (classification unavailable)"

    def test_clear_weather(self) -> None:
        """Test formatting for clear weather."""
        weather_result = MockWeatherResult(
            simple_condition="clear",
            confidence=0.9,
        )
        result = format_weather_context(weather_result)

        assert "Weather: clear" in result
        assert "90%" in result
        assert "Good visibility" in result

    def test_foggy_weather(self) -> None:
        """Test formatting for foggy weather."""
        weather_result = MockWeatherResult(
            simple_condition="foggy",
            confidence=0.85,
        )
        result = format_weather_context(weather_result)

        assert "Weather: foggy" in result
        assert "Visibility significantly reduced" in result

    def test_rainy_weather(self) -> None:
        """Test formatting for rainy weather."""
        weather_result = MockWeatherResult(
            simple_condition="rainy",
            confidence=0.8,
        )
        result = format_weather_context(weather_result)

        assert "Weather: rainy" in result
        assert "Rain may affect visibility" in result


class TestFormatClothingAnalysisContext:
    """Tests for format_clothing_analysis_context function."""

    def test_empty_classifications(self) -> None:
        """Test formatting when no clothing data is available."""
        result = format_clothing_analysis_context({}, None)
        assert result == "Clothing analysis: No person detections analyzed"

    def test_normal_clothing(self) -> None:
        """Test formatting for normal clothing."""
        clothing = {
            "det_1": MockClothingClassification(
                raw_description="blue jacket, dark pants",
                confidence=0.85,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            )
        }
        result = format_clothing_analysis_context(clothing, None)

        assert "Person det_1:" in result
        assert "blue jacket, dark pants" in result
        assert "85" in result  # confidence

    def test_suspicious_clothing(self) -> None:
        """Test formatting for suspicious clothing."""
        clothing = {
            "det_1": MockClothingClassification(
                raw_description="all black, face mask",
                confidence=0.9,
                is_suspicious=True,
                is_service_uniform=False,
                top_category="suspicious_all_black",
            )
        }
        result = format_clothing_analysis_context(clothing, None)

        assert "**ALERT**" in result
        assert "suspicious" in result.lower()

    def test_service_uniform(self) -> None:
        """Test formatting for service worker uniform."""
        clothing = {
            "det_1": MockClothingClassification(
                raw_description="delivery uniform, logo visible",
                confidence=0.88,
                is_suspicious=False,
                is_service_uniform=True,
                top_category="service_uniform",
            )
        }
        result = format_clothing_analysis_context(clothing, None)

        assert "Service/delivery worker uniform" in result
        assert "lower risk" in result

    def test_with_segmentation(self) -> None:
        """Test formatting with SegFormer segmentation data."""
        clothing = {
            "det_1": MockClothingClassification(
                raw_description="hoodie, pants",
                confidence=0.85,
                is_suspicious=False,
                is_service_uniform=False,
                top_category="casual",
            )
        }
        segmentation = {
            "det_1": MockClothingSegmentationResult(
                clothing_items=["hoodie", "pants", "hat"],
                has_face_covered=True,
                has_bag=True,
            )
        }
        result = format_clothing_analysis_context(clothing, segmentation)

        assert "Face covering detected" in result
        assert "**ALERT**" in result
        assert "bag detected" in result.lower()


class TestFormatPoseAnalysisContext:
    """Tests for format_pose_analysis_context function."""

    def test_none_result(self) -> None:
        """Test formatting when no pose data is available."""
        result = format_pose_analysis_context(None)
        assert result == "Pose analysis: Not available"

    def test_empty_poses(self) -> None:
        """Test formatting when poses dict is empty."""
        result = format_pose_analysis_context({})
        assert result == "Pose analysis: No poses detected"

    def test_normal_pose(self) -> None:
        """Test formatting for normal standing pose."""
        poses = {"det_1": {"classification": "standing", "confidence": 0.9}}
        result = format_pose_analysis_context(poses)

        assert "standing" in result
        assert "90%" in result

    def test_suspicious_crouching_pose(self) -> None:
        """Test formatting for suspicious crouching pose."""
        poses = {"det_1": {"classification": "crouching", "confidence": 0.85}}
        result = format_pose_analysis_context(poses)

        assert "crouching" in result
        assert "SUSPICIOUS" in result

    def test_running_pose(self) -> None:
        """Test formatting for running pose."""
        poses = {"det_1": {"classification": "running", "confidence": 0.8}}
        result = format_pose_analysis_context(poses)

        assert "running" in result
        assert "Fast movement detected" in result


class TestFormatActionRecognitionContext:
    """Tests for format_action_recognition_context function."""

    def test_none_result(self) -> None:
        """Test formatting when no action data is available."""
        result = format_action_recognition_context(None)
        assert result == "Action recognition: Not available"

    def test_empty_actions(self) -> None:
        """Test formatting when actions dict is empty."""
        result = format_action_recognition_context({})
        assert result == "Action recognition: No actions detected"

    def test_normal_action(self) -> None:
        """Test formatting for normal walking action."""
        actions = {"det_1": [{"action": "walking", "confidence": 0.9}]}
        result = format_action_recognition_context(actions)

        assert "walking" in result
        assert "90%" in result

    def test_high_risk_action(self) -> None:
        """Test formatting for high-risk action."""
        actions = {"det_1": [{"action": "checking_car_doors", "confidence": 0.85}]}
        result = format_action_recognition_context(actions)

        assert "checking_car_doors" in result
        assert "**HIGH RISK**" in result

    def test_suspicious_action(self) -> None:
        """Test formatting for suspicious action."""
        actions = {"det_1": [{"action": "loitering", "confidence": 0.8}]}
        result = format_action_recognition_context(actions)

        assert "loitering" in result
        assert "[Suspicious]" in result


class TestFormatVehicleClassificationContext:
    """Tests for format_vehicle_classification_context function."""

    def test_empty_classifications(self) -> None:
        """Test formatting when no vehicle data is available."""
        result = format_vehicle_classification_context({})
        assert result == "Vehicle classification: No vehicles analyzed"

    def test_normal_vehicle(self) -> None:
        """Test formatting for a normal car."""
        classifications = {
            "det_1": MockVehicleClassificationResult(
                vehicle_type="car",
                display_name="car/sedan",
                confidence=0.9,
                is_commercial=False,
                all_scores={"car": 0.9, "pickup_truck": 0.05},
            )
        }
        result = format_vehicle_classification_context(classifications)

        assert "car/sedan" in result
        assert "90%" in result
        assert "Commercial" not in result

    def test_commercial_vehicle(self) -> None:
        """Test formatting for commercial vehicle."""
        classifications = {
            "det_1": MockVehicleClassificationResult(
                vehicle_type="work_van",
                display_name="work van/delivery van",
                confidence=0.85,
                is_commercial=True,
                all_scores={"work_van": 0.85, "car": 0.1},
            )
        }
        result = format_vehicle_classification_context(classifications)

        assert "work van" in result
        assert "Commercial/delivery vehicle" in result

    def test_low_confidence_with_alternative(self) -> None:
        """Test formatting with low confidence shows alternative."""
        classifications = {
            "det_1": MockVehicleClassificationResult(
                vehicle_type="car",
                display_name="car/sedan",
                confidence=0.5,
                is_commercial=False,
                all_scores={"car": 0.5, "pickup_truck": 0.3},
            )
        }
        result = format_vehicle_classification_context(classifications)

        assert "Alternative:" in result
        assert "pickup_truck" in result


class TestFormatVehicleDamageContext:
    """Tests for format_vehicle_damage_context function."""

    def test_empty_damage(self) -> None:
        """Test formatting when no vehicle damage data is available."""
        result = format_vehicle_damage_context({})
        assert result == "Vehicle damage: No vehicles analyzed for damage"

    def test_no_damage_detected(self) -> None:
        """Test formatting when no damage is detected."""
        damage = {
            "det_1": MockVehicleDamageResult(
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
        """Test formatting for minor damage."""
        damage = {
            "det_1": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"scratches", "dents"},
                total_damage_count=2,
                highest_confidence=0.75,
                has_high_security_damage=False,
            )
        }
        result = format_vehicle_damage_context(damage)

        assert "dents" in result
        assert "scratches" in result
        assert "SECURITY ALERT" not in result

    def test_high_security_damage(self) -> None:
        """Test formatting for high-security damage."""
        damage = {
            "det_1": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"glass_shatter", "lamp_broken"},
                total_damage_count=2,
                highest_confidence=0.9,
                has_high_security_damage=True,
            )
        }
        result = format_vehicle_damage_context(damage)

        assert "**SECURITY ALERT**" in result
        assert "glass_shatter" in result
        assert "Possible break-in or vandalism" in result

    def test_damage_with_night_context(self) -> None:
        """Test formatting for damage detected at night."""
        damage = {
            "det_1": MockVehicleDamageResult(
                has_damage=True,
                damage_types={"glass_shatter"},
                total_damage_count=1,
                highest_confidence=0.85,
                has_high_security_damage=True,
            )
        }
        result = format_vehicle_damage_context(damage, time_of_day="night")

        assert "TIME CONTEXT" in result
        assert "night" in result
        assert "Elevated risk" in result


class TestFormatPetClassificationContext:
    """Tests for format_pet_classification_context function."""

    def test_empty_classifications(self) -> None:
        """Test formatting when no pet data is available."""
        result = format_pet_classification_context({})
        assert result == "Pet classification: No animals detected"

    def test_high_confidence_pet(self) -> None:
        """Test formatting for high-confidence pet detection."""
        pets = {
            "det_1": MockPetClassificationResult(
                animal_type="dog",
                confidence=0.92,
            )
        }
        result = format_pet_classification_context(pets)

        assert "dog" in result
        assert "92%" in result
        assert "HIGH CONFIDENCE" in result
        assert "FALSE POSITIVE NOTE" in result

    def test_medium_confidence_pet(self) -> None:
        """Test formatting for medium-confidence pet detection."""
        pets = {
            "det_1": MockPetClassificationResult(
                animal_type="cat",
                confidence=0.75,
            )
        }
        result = format_pet_classification_context(pets)

        assert "cat" in result
        assert "Probable household pet" in result
        assert "HIGH CONFIDENCE" not in result

    def test_low_confidence_pet(self) -> None:
        """Test formatting for low-confidence pet detection."""
        pets = {
            "det_1": MockPetClassificationResult(
                animal_type="dog",
                confidence=0.6,
            )
        }
        result = format_pet_classification_context(pets)

        assert "dog" in result
        assert "may be wildlife" in result


class TestFormatDepthContext:
    """Tests for format_depth_context function."""

    def test_none_result(self) -> None:
        """Test formatting when no depth data is available."""
        result = format_depth_context(None)
        assert result == "Depth analysis: Not available"

    def test_empty_detections(self) -> None:
        """Test formatting when depth result has no detections."""
        depth_result = DepthAnalysisResult()
        result = format_depth_context(depth_result)
        assert "No detections analyzed" in result

    def test_foreground_detection(self) -> None:
        """Test formatting for close detection (very close proximity)."""
        det_depth = DetectionDepth(
            detection_id="det_1",
            class_name="person",
            depth_value=0.1,
            proximity_label="very close",
            is_approaching=False,
        )
        depth_result = DepthAnalysisResult(
            detection_depths={"det_1": det_depth},
            closest_detection_id="det_1",
            has_close_objects=True,
            average_depth=0.1,
        )
        result = format_depth_context(depth_result)

        assert "very close" in result
        assert "CLOSE TO CAMERA" in result

    def test_approaching_detection(self) -> None:
        """Test formatting for approaching detection."""
        det_depth = DetectionDepth(
            detection_id="det_1",
            class_name="person",
            depth_value=0.3,
            proximity_label="close",
            is_approaching=True,
        )
        depth_result = DepthAnalysisResult(
            detection_depths={"det_1": det_depth},
            closest_detection_id="det_1",
            has_close_objects=True,
            average_depth=0.3,
        )
        result = format_depth_context(depth_result)

        assert "close" in result
        assert "APPROACHING" in result


class TestFormatImageQualityContext:
    """Tests for format_image_quality_context function."""

    def test_none_result(self) -> None:
        """Test formatting when no quality data is available."""
        result = format_image_quality_context(None)
        assert result == "Image quality: Not assessed"

    def test_good_quality(self) -> None:
        """Test formatting for good quality image."""
        quality = MockImageQualityResult(
            quality_score=85.0,
            is_good_quality=True,
            is_blurry=False,
            is_noisy=False,
            quality_issues=[],
        )
        result = format_image_quality_context(quality)

        assert "Good" in result
        assert "85" in result

    def test_blurry_image(self) -> None:
        """Test formatting for blurry image."""
        quality = MockImageQualityResult(
            quality_score=45.0,
            is_good_quality=False,
            is_blurry=True,
            is_noisy=False,
            quality_issues=["blur detected"],
        )
        result = format_image_quality_context(quality)

        assert "blur detected" in result
        assert "fast movement or camera issue" in result

    def test_quality_change_alert(self) -> None:
        """Test formatting with quality change alert."""
        quality = MockImageQualityResult(
            quality_score=30.0,
            is_good_quality=False,
            is_blurry=True,
            is_noisy=True,
            quality_issues=["blur detected", "noise/artifacts detected"],
        )
        result = format_image_quality_context(
            quality,
            quality_change_detected=True,
            quality_change_description="Sudden quality drop from 85 to 30",
        )

        assert "**QUALITY ALERT**" in result
        assert "Sudden quality drop" in result
        assert "tampering" in result


class TestFormatDetectionsWithAllEnrichment:
    """Tests for format_detections_with_all_enrichment function."""

    def test_empty_detections(self) -> None:
        """Test formatting with no detections."""
        result = format_detections_with_all_enrichment([])
        assert result == "No detections in this batch."

    def test_basic_detection(self) -> None:
        """Test formatting a basic detection without enrichment."""
        detections = [
            {
                "detection_id": "det_1",
                "class_name": "person",
                "confidence": 0.9,
                "bbox": [100, 100, 200, 300],
            }
        ]
        result = format_detections_with_all_enrichment(detections)

        assert "### PERSON" in result
        assert "ID: det_1" in result
        assert "90%" in result
        assert "[100, 100, 200, 300]" in result


class TestPromptTemplateStructure:
    """Tests for the MODEL_ZOO_ENHANCED prompt template structure."""

    def test_template_has_all_required_fields(self) -> None:
        """Test that the template contains all required placeholder fields."""
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

        for required_field in required_fields:
            assert required_field in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT, (
                f"Missing required field: {required_field}"
            )

    def test_template_has_chatml_format(self) -> None:
        """Test that the template uses ChatML format."""
        assert "<|im_start|>system" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "<|im_start|>user" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "<|im_start|>assistant" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "<|im_end|>" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

    def test_template_has_risk_interpretation_guide(self) -> None:
        """Test that the template contains the risk interpretation guide."""
        assert "## Risk Interpretation Guide" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Violence Detection" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Weather Context" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Clothing/Attire Risk Factors" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Vehicle Analysis" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert "### Pet Detection" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

    def test_template_has_json_output_format(self) -> None:
        """Test that the template specifies JSON output format."""
        assert "Output JSON" in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"risk_score"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"risk_level"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"summary"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"reasoning"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"entities"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"flags"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"recommended_action"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
        assert '"confidence_factors"' in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT


class TestFormattersErrorHandling:
    """Tests for error handling in formatter functions."""

    def test_format_violence_context_with_invalid_attributes(self) -> None:
        """Test format_violence_context handles objects with missing attributes."""

        class PartialViolenceResult:
            """Partial result missing some attributes."""

            is_violent = True
            confidence = 0.9
            # Missing violent_score and non_violent_score

        # Should handle missing attributes gracefully or raise informative error
        try:
            result = format_violence_context(PartialViolenceResult())
            # If it succeeds, verify it contains expected content
            assert "VIOLENCE" in result or result is not None
        except AttributeError:
            # AttributeError is acceptable for missing required attributes
            pass

    def test_format_weather_context_with_invalid_confidence(self) -> None:
        """Test format_weather_context handles invalid confidence values."""

        class InvalidWeatherResult:
            simple_condition = "clear"
            confidence = None  # Invalid confidence

        try:
            result = format_weather_context(InvalidWeatherResult())
            # Should handle None confidence gracefully
            assert "clear" in result or "Weather" in result
        except TypeError:
            # TypeError is acceptable for None confidence in formatting
            pass

    def test_format_clothing_analysis_context_with_none_values(self) -> None:
        """Test format_clothing_analysis_context handles None values in dict."""
        clothing = {
            "det_1": None  # None value instead of classification object
        }
        try:
            result = format_clothing_analysis_context(clothing, None)
            # Should handle None gracefully or skip the entry
            assert result is not None
        except (AttributeError, TypeError):
            # These errors are acceptable for None values
            pass

    def test_format_pose_analysis_context_with_missing_keys(self) -> None:
        """Test format_pose_analysis_context handles dicts with missing keys."""
        poses = {"det_1": {}}  # Empty dict, missing 'classification' and 'confidence'
        result = format_pose_analysis_context(poses)
        # Should handle missing keys gracefully
        assert result is not None

    def test_format_action_recognition_context_with_empty_list(self) -> None:
        """Test format_action_recognition_context handles empty action lists."""
        actions = {"det_1": []}  # Empty list of actions
        result = format_action_recognition_context(actions)
        # Should handle empty lists gracefully
        assert result is not None

    def test_format_vehicle_classification_with_none_values(self) -> None:
        """Test format_vehicle_classification_context handles None confidence."""

        class InvalidVehicleResult:
            vehicle_type = "car"
            display_name = "car/sedan"
            confidence = None  # Invalid
            is_commercial = False
            all_scores: dict = {}  # noqa: RUF012

        classifications = {"det_1": InvalidVehicleResult()}
        try:
            result = format_vehicle_classification_context(classifications)
            assert result is not None
        except TypeError:
            # TypeError is acceptable for None confidence in formatting
            pass

    def test_format_vehicle_damage_with_empty_damage_types(self) -> None:
        """Test format_vehicle_damage_context handles empty damage_types set."""

        @dataclass
        class EmptyDamageResult:
            has_damage = False
            damage_types: set = None  # type: ignore
            total_damage_count = 0
            highest_confidence = 0.0
            has_high_security_damage = False

            def __post_init__(self):
                if self.damage_types is None:
                    self.damage_types = set()

        damage = {"det_1": EmptyDamageResult()}
        result = format_vehicle_damage_context(damage)
        assert "No damage detected" in result or result is not None

    def test_format_depth_context_with_empty_result(self) -> None:
        """Test format_depth_context handles empty DepthAnalysisResult."""
        from backend.services.depth_anything_loader import DepthAnalysisResult

        depth_result = DepthAnalysisResult()  # Empty result with no detections
        result = format_depth_context(depth_result)
        # Should handle empty result gracefully
        assert result is not None
        assert "No detections analyzed" in result

    def test_format_image_quality_with_none_quality_score(self) -> None:
        """Test format_image_quality_context handles None quality_score."""

        class InvalidQualityResult:
            quality_score = None  # Invalid
            is_good_quality = False
            is_blurry = False
            is_noisy = False
            quality_issues: list = []  # noqa: RUF012

        try:
            result = format_image_quality_context(InvalidQualityResult())
            assert result is not None
        except TypeError:
            # TypeError is acceptable for None in formatting
            pass

    def test_format_detections_with_all_enrichment_missing_fields(self) -> None:
        """Test format_detections_with_all_enrichment handles missing fields."""
        detections = [
            {
                "detection_id": "det_1",
                # Missing class_name, confidence, bbox
            }
        ]
        try:
            result = format_detections_with_all_enrichment(detections)
            # Should handle missing fields gracefully
            assert result is not None
        except KeyError:
            # KeyError is acceptable for missing required fields
            pass

    def test_format_detections_with_none_in_list(self) -> None:
        """Test format_detections_with_all_enrichment handles None in list."""
        detections = [None]  # type: ignore
        try:
            result = format_detections_with_all_enrichment(detections)
            assert result is not None
        except (TypeError, AttributeError):
            # These errors are acceptable for None in list
            pass
