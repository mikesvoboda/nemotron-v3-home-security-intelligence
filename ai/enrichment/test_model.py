"""Unit tests for Combined Enrichment Service.

Tests cover:
- ClothingClassifier prompt organization and categories (NEM-3030)
- Category confidence thresholds
- Multi-label classification support
- Backward compatibility with existing classify() interface
- Category lookup functions
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from pydantic import ValidationError

# Add the ai/enrichment directory to sys.path to enable imports
_enrichment_dir = Path(__file__).parent
if str(_enrichment_dir) not in sys.path:
    sys.path.insert(0, str(_enrichment_dir))

# Create proper mock modules for the ai.enrichment.vitpose import
# Using ModuleType instead of MagicMock to avoid interference with pytest
_mock_ai = ModuleType("ai")
_mock_ai_enrichment = ModuleType("ai.enrichment")
_mock_vitpose = ModuleType("ai.enrichment.vitpose")


# Create a mock PoseAnalyzer class
class MockPoseAnalyzer:
    """Mock PoseAnalyzer for testing."""

    pass


_mock_vitpose.PoseAnalyzer = MockPoseAnalyzer

# Set up the module hierarchy
_mock_ai.enrichment = _mock_ai_enrichment
_mock_ai_enrichment.vitpose = _mock_vitpose

# Install mock modules
sys.modules["ai"] = _mock_ai
sys.modules["ai.enrichment"] = _mock_ai_enrichment
sys.modules["ai.enrichment.vitpose"] = _mock_vitpose

# Now import from the local model module
from model import (
    AUTHORITY_CATEGORIES,
    CARRYING_CATEGORIES,
    CLOTHING_CATEGORY_THRESHOLDS,
    DEFAULT_CLOTHING_THRESHOLD,
    SECURITY_CLOTHING_PROMPTS,
    SECURITY_CLOTHING_PROMPTS_BY_CATEGORY,
    SERVICE_CATEGORIES,
    SUSPICIOUS_CATEGORIES,
    ClothingClassifier,
    get_category_for_prompt,
    get_threshold_for_category,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def dummy_image():
    """Create a dummy PIL image for testing."""
    return Image.new("RGB", (224, 224), color="red")


@pytest.fixture
def mock_clothing_classifier():
    """Create a mock ClothingClassifier for testing without loading models."""
    with patch.object(ClothingClassifier, "load_model"):
        classifier = ClothingClassifier(model_path="/fake/path", device="cpu")
        # Mock the model components
        classifier.model = MagicMock()
        classifier.preprocess = MagicMock(return_value=MagicMock())
        classifier.tokenizer = MagicMock(return_value=MagicMock())
        yield classifier


# =============================================================================
# Test: Clothing Prompt Organization (NEM-3030)
# =============================================================================


class TestClothingPromptOrganization:
    """Tests for SECURITY_CLOTHING_PROMPTS organization and expansion."""

    def test_prompt_count_is_approximately_40(self):
        """Test that we have approximately 40 prompts as specified in NEM-3030."""
        prompt_count = len(SECURITY_CLOTHING_PROMPTS)
        # Allow range of 35-50 for flexibility
        assert 35 <= prompt_count <= 50, (
            f"Expected ~40 prompts, got {prompt_count}. "
            "NEM-3030 specifies expanding from ~19 to ~40 prompts."
        )

    def test_prompts_organized_by_category(self):
        """Test that prompts are organized into categories."""
        expected_categories = {
            "suspicious",
            "delivery",
            "authority",
            "utility",
            "casual",
            "weather",
            "carrying",
            "athletic",
        }
        actual_categories = set(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.keys())
        assert expected_categories == actual_categories, (
            f"Missing categories: {expected_categories - actual_categories}, "
            f"Extra categories: {actual_categories - expected_categories}"
        )

    def test_each_category_has_prompts(self):
        """Test that each category has at least one prompt."""
        for category, prompts in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.items():
            assert len(prompts) > 0, f"Category '{category}' has no prompts"

    def test_flattened_prompts_match_categories(self):
        """Test that SECURITY_CLOTHING_PROMPTS contains all prompts from categories."""
        all_category_prompts = set()
        for prompts in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.values():
            all_category_prompts.update(prompts)

        flat_prompts = set(SECURITY_CLOTHING_PROMPTS)
        assert flat_prompts == all_category_prompts, (
            f"Mismatch between flat list and categories. "
            f"In flat but not categories: {flat_prompts - all_category_prompts}, "
            f"In categories but not flat: {all_category_prompts - flat_prompts}"
        )

    def test_no_duplicate_prompts(self):
        """Test that there are no duplicate prompts across categories."""
        all_prompts = []
        for prompts in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.values():
            all_prompts.extend(prompts)

        duplicates = [p for p in all_prompts if all_prompts.count(p) > 1]
        assert len(duplicates) == 0, f"Duplicate prompts found: {set(duplicates)}"


class TestSuspiciousClothingPrompts:
    """Tests for suspicious clothing category prompts."""

    def test_suspicious_category_exists(self):
        """Test that suspicious category exists."""
        assert "suspicious" in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY

    def test_suspicious_prompts_cover_key_scenarios(self):
        """Test that suspicious prompts cover key security scenarios."""
        suspicious_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["suspicious"]
        suspicious_text = " ".join(suspicious_prompts).lower()

        # Key scenarios that should be covered
        key_scenarios = [
            "hoodie",  # Dark hoodie with hood up
            "ski mask",  # Face covering
            "balaclava",  # Alternative face covering term
            "all black",  # All black clothing
            "face",  # Face partially covered/obscured
            "gloves",  # Gloves in warm weather
        ]

        for scenario in key_scenarios:
            assert scenario in suspicious_text, (
                f"Suspicious prompts should cover '{scenario}' scenario"
            )

    def test_suspicious_categories_frozenset_populated(self):
        """Test that SUSPICIOUS_CATEGORIES frozenset is properly populated."""
        assert len(SUSPICIOUS_CATEGORIES) > 0
        expected = frozenset(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["suspicious"])
        assert expected == SUSPICIOUS_CATEGORIES


class TestDeliveryUniformPrompts:
    """Tests for delivery uniform category prompts."""

    def test_delivery_category_exists(self):
        """Test that delivery category exists."""
        assert "delivery" in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY

    def test_delivery_prompts_cover_major_carriers(self):
        """Test that delivery prompts cover major delivery carriers."""
        delivery_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["delivery"]
        delivery_text = " ".join(delivery_prompts).lower()

        # Major carriers that should be covered
        major_carriers = ["ups", "fedex", "amazon", "postal"]

        for carrier in major_carriers:
            assert carrier in delivery_text, f"Delivery prompts should cover '{carrier}'"

    def test_delivery_prompts_include_food_delivery(self):
        """Test that food delivery services are included."""
        delivery_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["delivery"]
        delivery_text = " ".join(delivery_prompts).lower()

        # At least one food delivery indicator
        food_delivery_terms = ["food", "doordash", "insulated bag", "courier"]
        assert any(term in delivery_text for term in food_delivery_terms), (
            "Delivery prompts should include food delivery services"
        )


class TestAuthorityPrompts:
    """Tests for authority/emergency services category prompts."""

    def test_authority_category_exists(self):
        """Test that authority category exists."""
        assert "authority" in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY

    def test_authority_prompts_cover_key_services(self):
        """Test that authority prompts cover key emergency services."""
        authority_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["authority"]
        authority_text = " ".join(authority_prompts).lower()

        # Key services
        key_services = ["police", "security", "firefighter"]

        for service in key_services:
            assert service in authority_text, f"Authority prompts should cover '{service}'"

    def test_authority_categories_frozenset_populated(self):
        """Test that AUTHORITY_CATEGORIES frozenset is properly populated."""
        assert len(AUTHORITY_CATEGORIES) > 0
        expected = frozenset(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["authority"])
        assert expected == AUTHORITY_CATEGORIES


class TestUtilityPrompts:
    """Tests for utility/maintenance worker category prompts."""

    def test_utility_category_exists(self):
        """Test that utility category exists."""
        assert "utility" in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY

    def test_utility_prompts_cover_common_workers(self):
        """Test that utility prompts cover common utility workers."""
        utility_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["utility"]
        utility_text = " ".join(utility_prompts).lower()

        # Common utility workers
        common_workers = ["maintenance", "construction", "electrician"]

        for worker in common_workers:
            assert worker in utility_text, f"Utility prompts should cover '{worker}'"

    def test_service_categories_includes_utility(self):
        """Test that SERVICE_CATEGORIES includes utility workers."""
        utility_prompts = set(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["utility"])
        assert utility_prompts.issubset(SERVICE_CATEGORIES), (
            "SERVICE_CATEGORIES should include utility workers"
        )


class TestCarryingPrompts:
    """Tests for carrying items category prompts."""

    def test_carrying_category_exists(self):
        """Test that carrying category exists."""
        assert "carrying" in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY

    def test_carrying_prompts_cover_key_items(self):
        """Test that carrying prompts cover security-relevant items."""
        carrying_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["carrying"]
        carrying_text = " ".join(carrying_prompts).lower()

        # Key items for security assessment
        key_items = ["box", "package", "backpack", "duffel", "tools"]

        for item in key_items:
            assert item in carrying_text, f"Carrying prompts should cover '{item}'"

    def test_carrying_prompts_include_nothing_option(self):
        """Test that carrying prompts include 'carrying nothing' option."""
        carrying_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["carrying"]
        carrying_text = " ".join(carrying_prompts).lower()

        assert "nothing" in carrying_text, (
            "Carrying prompts should include 'carrying nothing' option"
        )

    def test_carrying_categories_frozenset_populated(self):
        """Test that CARRYING_CATEGORIES frozenset is properly populated."""
        assert len(CARRYING_CATEGORIES) > 0
        expected = frozenset(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["carrying"])
        assert expected == CARRYING_CATEGORIES


class TestCasualAndWeatherPrompts:
    """Tests for casual and weather-appropriate clothing prompts."""

    def test_casual_category_exists(self):
        """Test that casual category exists."""
        assert "casual" in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY

    def test_weather_category_exists(self):
        """Test that weather category exists."""
        assert "weather" in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY

    def test_casual_prompts_provide_contrast(self):
        """Test that casual prompts provide contrast to suspicious attire."""
        casual_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["casual"]
        casual_text = " ".join(casual_prompts).lower()

        # Normal attire indicators
        normal_indicators = ["casual", "jeans", "suit", "professional"]

        assert any(indicator in casual_text for indicator in normal_indicators), (
            "Casual prompts should include normal everyday attire"
        )

    def test_weather_prompts_cover_conditions(self):
        """Test that weather prompts cover different conditions."""
        weather_prompts = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["weather"]
        weather_text = " ".join(weather_prompts).lower()

        # Weather conditions
        conditions = ["rain", "winter", "summer"]

        assert any(condition in weather_text for condition in conditions), (
            "Weather prompts should cover different weather conditions"
        )


# =============================================================================
# Test: Category Confidence Thresholds (NEM-3030)
# =============================================================================


class TestCategoryConfidenceThresholds:
    """Tests for per-category confidence thresholds."""

    def test_thresholds_dict_has_all_categories(self):
        """Test that thresholds are defined for all categories."""
        expected_categories = set(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.keys())
        threshold_categories = set(CLOTHING_CATEGORY_THRESHOLDS.keys())

        assert expected_categories == threshold_categories, (
            f"Threshold mismatch. Missing: {expected_categories - threshold_categories}, "
            f"Extra: {threshold_categories - expected_categories}"
        )

    def test_suspicious_has_lower_threshold(self):
        """Test that suspicious category has a lower threshold for flagging."""
        suspicious_threshold = CLOTHING_CATEGORY_THRESHOLDS["suspicious"]
        casual_threshold = CLOTHING_CATEGORY_THRESHOLDS["casual"]

        assert suspicious_threshold < casual_threshold, (
            f"Suspicious threshold ({suspicious_threshold}) should be lower than "
            f"casual threshold ({casual_threshold}) to catch more potential threats"
        )

    def test_carrying_has_low_threshold(self):
        """Test that carrying category has a low threshold (important for security)."""
        carrying_threshold = CLOTHING_CATEGORY_THRESHOLDS["carrying"]

        assert carrying_threshold <= 0.35, (
            f"Carrying threshold ({carrying_threshold}) should be low (<= 0.35) "
            "because carrying items is important for threat assessment"
        )

    def test_authority_has_higher_threshold(self):
        """Test that authority category has a higher threshold to avoid misidentification."""
        authority_threshold = CLOTHING_CATEGORY_THRESHOLDS["authority"]
        suspicious_threshold = CLOTHING_CATEGORY_THRESHOLDS["suspicious"]

        assert authority_threshold > suspicious_threshold, (
            f"Authority threshold ({authority_threshold}) should be higher than "
            f"suspicious ({suspicious_threshold}) to avoid misidentifying authority figures"
        )

    def test_all_thresholds_in_valid_range(self):
        """Test that all thresholds are in valid range (0-1)."""
        for category, threshold in CLOTHING_CATEGORY_THRESHOLDS.items():
            assert 0 < threshold < 1, (
                f"Threshold for '{category}' ({threshold}) should be between 0 and 1"
            )

    def test_default_threshold_exists(self):
        """Test that DEFAULT_CLOTHING_THRESHOLD is defined."""
        assert DEFAULT_CLOTHING_THRESHOLD > 0
        assert DEFAULT_CLOTHING_THRESHOLD < 1


class TestGetThresholdForCategory:
    """Tests for get_threshold_for_category function."""

    def test_returns_correct_threshold_for_known_category(self):
        """Test that function returns correct threshold for known categories."""
        assert (
            get_threshold_for_category("suspicious") == CLOTHING_CATEGORY_THRESHOLDS["suspicious"]
        )
        assert get_threshold_for_category("delivery") == CLOTHING_CATEGORY_THRESHOLDS["delivery"]
        assert get_threshold_for_category("authority") == CLOTHING_CATEGORY_THRESHOLDS["authority"]

    def test_returns_default_for_unknown_category(self):
        """Test that function returns default threshold for unknown categories."""
        result = get_threshold_for_category("nonexistent_category")
        assert result == DEFAULT_CLOTHING_THRESHOLD


class TestGetCategoryForPrompt:
    """Tests for get_category_for_prompt function."""

    def test_returns_correct_category_for_suspicious_prompt(self):
        """Test that function returns 'suspicious' for suspicious prompts."""
        suspicious_prompt = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["suspicious"][0]
        assert get_category_for_prompt(suspicious_prompt) == "suspicious"

    def test_returns_correct_category_for_delivery_prompt(self):
        """Test that function returns 'delivery' for delivery prompts."""
        delivery_prompt = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["delivery"][0]
        assert get_category_for_prompt(delivery_prompt) == "delivery"

    def test_returns_correct_category_for_carrying_prompt(self):
        """Test that function returns 'carrying' for carrying prompts."""
        carrying_prompt = SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["carrying"][0]
        assert get_category_for_prompt(carrying_prompt) == "carrying"

    def test_returns_unknown_for_unrecognized_prompt(self):
        """Test that function returns 'unknown' for unrecognized prompts."""
        assert get_category_for_prompt("this is not a real prompt") == "unknown"


# =============================================================================
# Test: Multi-Label Classification (NEM-3030)
# =============================================================================


class TestMultiLabelClassification:
    """Tests for multi-label classification functionality."""

    def test_classify_multilabel_returns_all_categories(
        self, mock_clothing_classifier, dummy_image
    ):
        """Test that classify_multilabel returns results for all categories."""
        import torch

        # Mock the model inference
        num_prompts = len(SECURITY_CLOTHING_PROMPTS)

        mock_clothing_classifier.preprocess.return_value.unsqueeze.return_value.to.return_value = (
            torch.zeros(1, 3, 224, 224)
        )
        mock_clothing_classifier.tokenizer.return_value.to.return_value = torch.zeros(
            num_prompts, 77, dtype=torch.long
        )
        mock_clothing_classifier.model.encode_image.return_value = torch.randn(1, 512)
        mock_clothing_classifier.model.encode_text.return_value = torch.randn(num_prompts, 512)

        result = mock_clothing_classifier.classify_multilabel(dummy_image)

        # Check all categories are present
        expected_categories = set(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.keys())
        actual_categories = set(result["matched_categories"].keys())
        assert expected_categories == actual_categories

    def test_classify_multilabel_returns_required_fields(
        self, mock_clothing_classifier, dummy_image
    ):
        """Test that classify_multilabel returns all required fields."""
        import torch

        # Mock the model inference
        num_prompts = len(SECURITY_CLOTHING_PROMPTS)

        mock_clothing_classifier.preprocess.return_value.unsqueeze.return_value.to.return_value = (
            torch.zeros(1, 3, 224, 224)
        )
        mock_clothing_classifier.tokenizer.return_value.to.return_value = torch.zeros(
            num_prompts, 77, dtype=torch.long
        )
        mock_clothing_classifier.model.encode_image.return_value = torch.randn(1, 512)
        mock_clothing_classifier.model.encode_text.return_value = torch.randn(num_prompts, 512)

        result = mock_clothing_classifier.classify_multilabel(dummy_image)

        # Check required fields
        required_fields = [
            "matched_categories",
            "primary_category",
            "primary_prompt",
            "primary_confidence",
            "is_suspicious",
            "is_service_uniform",
            "is_authority",
            "carrying_item",
            "all_scores",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_classify_multilabel_category_result_structure(
        self, mock_clothing_classifier, dummy_image
    ):
        """Test that each category result has correct structure."""
        import torch

        # Mock the model inference
        num_prompts = len(SECURITY_CLOTHING_PROMPTS)

        mock_clothing_classifier.preprocess.return_value.unsqueeze.return_value.to.return_value = (
            torch.zeros(1, 3, 224, 224)
        )
        mock_clothing_classifier.tokenizer.return_value.to.return_value = torch.zeros(
            num_prompts, 77, dtype=torch.long
        )
        mock_clothing_classifier.model.encode_image.return_value = torch.randn(1, 512)
        mock_clothing_classifier.model.encode_text.return_value = torch.randn(num_prompts, 512)

        result = mock_clothing_classifier.classify_multilabel(dummy_image)

        # Check structure of each category result
        for category, category_result in result["matched_categories"].items():
            assert "prompt" in category_result, f"Category {category} missing 'prompt'"
            assert "confidence" in category_result, f"Category {category} missing 'confidence'"
            assert "threshold" in category_result, f"Category {category} missing 'threshold'"
            assert "above_threshold" in category_result, (
                f"Category {category} missing 'above_threshold'"
            )

            # Confidence should be a number between 0 and 1
            assert 0 <= category_result["confidence"] <= 1, (
                f"Category {category} confidence {category_result['confidence']} out of range"
            )


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing classify() interface."""

    def test_classify_still_works(self, mock_clothing_classifier, dummy_image):
        """Test that classify() method still works."""
        import torch

        # Mock the model inference
        num_prompts = len(SECURITY_CLOTHING_PROMPTS)

        mock_clothing_classifier.preprocess.return_value.unsqueeze.return_value.to.return_value = (
            torch.zeros(1, 3, 224, 224)
        )
        mock_clothing_classifier.tokenizer.return_value.to.return_value = torch.zeros(
            num_prompts, 77, dtype=torch.long
        )
        mock_clothing_classifier.model.encode_image.return_value = torch.randn(1, 512)
        mock_clothing_classifier.model.encode_text.return_value = torch.randn(num_prompts, 512)

        result = mock_clothing_classifier.classify(dummy_image)

        # Check backward-compatible fields
        required_fields = [
            "clothing_type",
            "color",
            "style",
            "confidence",
            "top_category",
            "description",
            "is_suspicious",
            "is_service_uniform",
            "all_scores",
        ]
        for field in required_fields:
            assert field in result, f"Missing backward-compatible field: {field}"

    def test_classify_returns_valid_types(self, mock_clothing_classifier, dummy_image):
        """Test that classify() returns valid types for all fields."""
        import torch

        # Mock the model inference
        num_prompts = len(SECURITY_CLOTHING_PROMPTS)

        mock_clothing_classifier.preprocess.return_value.unsqueeze.return_value.to.return_value = (
            torch.zeros(1, 3, 224, 224)
        )
        mock_clothing_classifier.tokenizer.return_value.to.return_value = torch.zeros(
            num_prompts, 77, dtype=torch.long
        )
        mock_clothing_classifier.model.encode_image.return_value = torch.randn(1, 512)
        mock_clothing_classifier.model.encode_text.return_value = torch.randn(num_prompts, 512)

        result = mock_clothing_classifier.classify(dummy_image)

        # Type checks
        assert isinstance(result["clothing_type"], str)
        assert isinstance(result["color"], str)
        assert isinstance(result["style"], str)
        assert isinstance(result["confidence"], float)
        assert isinstance(result["top_category"], str)
        assert isinstance(result["description"], str)
        assert isinstance(result["is_suspicious"], bool)
        assert isinstance(result["is_service_uniform"], bool)
        assert isinstance(result["all_scores"], dict)


# =============================================================================
# Test: ClothingClassifier Attribute Extraction
# =============================================================================


class TestClothingTypeExtraction:
    """Tests for _extract_clothing_type method."""

    def test_extracts_hoodie(self, mock_clothing_classifier):
        """Test hoodie extraction."""
        assert (
            mock_clothing_classifier._extract_clothing_type("person wearing dark hoodie")
            == "hoodie"
        )

    def test_extracts_jacket(self, mock_clothing_classifier):
        """Test jacket/coat extraction."""
        assert mock_clothing_classifier._extract_clothing_type("person in winter coat") == "jacket"
        assert mock_clothing_classifier._extract_clothing_type("person in rain jacket") == "jacket"

    def test_extracts_vest(self, mock_clothing_classifier):
        """Test vest extraction."""
        assert (
            mock_clothing_classifier._extract_clothing_type("Amazon delivery driver in blue vest")
            == "vest"
        )

    def test_extracts_uniform(self, mock_clothing_classifier):
        """Test uniform extraction."""
        assert (
            mock_clothing_classifier._extract_clothing_type("police officer in uniform")
            == "uniform"
        )

    def test_extracts_formal(self, mock_clothing_classifier):
        """Test formal attire extraction."""
        assert (
            mock_clothing_classifier._extract_clothing_type("person in professional suit")
            == "formal"
        )

    def test_extracts_athletic(self, mock_clothing_classifier):
        """Test athletic wear extraction."""
        assert (
            mock_clothing_classifier._extract_clothing_type("person in athletic wear") == "athletic"
        )

    def test_defaults_to_casual(self, mock_clothing_classifier):
        """Test default to casual for unknown clothing."""
        assert mock_clothing_classifier._extract_clothing_type("person standing") == "casual"


class TestColorExtraction:
    """Tests for _extract_color method."""

    def test_extracts_dark_color(self, mock_clothing_classifier):
        """Test dark color extraction."""
        assert mock_clothing_classifier._extract_color("person wearing dark hoodie") == "dark"
        assert (
            mock_clothing_classifier._extract_color("person wearing all black clothing") == "dark"
        )

    def test_extracts_high_visibility(self, mock_clothing_classifier):
        """Test high-visibility color extraction."""
        assert mock_clothing_classifier._extract_color("high-visibility vest") == "high-visibility"

    def test_defaults_to_unknown(self, mock_clothing_classifier):
        """Test default to unknown for unspecified color."""
        assert mock_clothing_classifier._extract_color("person in casual clothes") == "unknown"


class TestStyleExtraction:
    """Tests for _extract_style method."""

    def test_extracts_suspicious_style(self, mock_clothing_classifier):
        """Test suspicious style extraction."""
        assert mock_clothing_classifier._extract_style("person wearing ski mask") == "suspicious"
        assert mock_clothing_classifier._extract_style("face obscured by hood") == "suspicious"

    def test_extracts_work_style(self, mock_clothing_classifier):
        """Test work style extraction."""
        assert mock_clothing_classifier._extract_style("delivery uniform") == "work"
        assert mock_clothing_classifier._extract_style("utility worker") == "work"

    def test_extracts_active_style(self, mock_clothing_classifier):
        """Test active style extraction."""
        assert mock_clothing_classifier._extract_style("athletic wear") == "active"
        assert mock_clothing_classifier._extract_style("hiking clothing") == "active"

    def test_extracts_formal_style(self, mock_clothing_classifier):
        """Test formal style extraction."""
        assert mock_clothing_classifier._extract_style("business suit") == "formal"

    def test_defaults_to_casual_style(self, mock_clothing_classifier):
        """Test default to casual style."""
        assert mock_clothing_classifier._extract_style("person standing") == "casual"


# =============================================================================
# Test: Model Not Loaded Error Handling
# =============================================================================


class TestModelNotLoadedErrors:
    """Tests for proper error handling when model is not loaded."""

    def test_classify_raises_when_model_not_loaded(self, dummy_image):
        """Test that classify raises RuntimeError when model not loaded."""
        with patch.object(ClothingClassifier, "load_model"):
            classifier = ClothingClassifier(model_path="/fake/path", device="cpu")
            # Model is None by default

            with pytest.raises(RuntimeError, match="Model not loaded"):
                classifier.classify(dummy_image)

    def test_classify_multilabel_raises_when_model_not_loaded(self, dummy_image):
        """Test that classify_multilabel raises RuntimeError when model not loaded."""
        with patch.object(ClothingClassifier, "load_model"):
            classifier = ClothingClassifier(model_path="/fake/path", device="cpu")
            # Model is None by default

            with pytest.raises(RuntimeError, match="Model not loaded"):
                classifier.classify_multilabel(dummy_image)


# =============================================================================
# Test: Unified Enrichment Endpoint Schemas (NEM-3034)
# =============================================================================


# Import schema models for testing
from model import (
    BoundingBox,
    ClothingResult,
    DemographicsResult,
    DepthResult,
    DetailedModelStatus,
    EnrichmentRequest,
    EnrichmentResponse,
    ModelPreloadResponse,
    ModelRegistryEntry,
    ModelRegistryResponse,
    ModelUnloadResponse,
    PetEnrichmentResult,
    PoseResult,
    ReadinessResponse,
    SystemStatus,
    ThreatResult,
    VehicleEnrichmentResult,
)


class TestEnrichmentRequestSchema:
    """Tests for EnrichmentRequest Pydantic model."""

    def test_valid_person_request(self):
        """Test creating a valid person enrichment request."""
        request = EnrichmentRequest(
            image="base64encodedimage",
            detection_type="person",
            bbox=BoundingBox(x1=10.0, y1=20.0, x2=100.0, y2=200.0),
        )
        assert request.detection_type == "person"
        assert request.bbox.x1 == 10.0
        assert request.bbox.y2 == 200.0
        assert request.frames is None
        assert request.options == {}

    def test_valid_vehicle_request(self):
        """Test creating a valid vehicle enrichment request."""
        request = EnrichmentRequest(
            image="base64encodedimage",
            detection_type="vehicle",
            bbox=BoundingBox(x1=0.0, y1=0.0, x2=640.0, y2=480.0),
        )
        assert request.detection_type == "vehicle"

    def test_valid_animal_request(self):
        """Test creating a valid animal enrichment request."""
        request = EnrichmentRequest(
            image="base64encodedimage",
            detection_type="animal",
            bbox=BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=150.0),
        )
        assert request.detection_type == "animal"

    def test_valid_object_request(self):
        """Test creating a valid object enrichment request."""
        request = EnrichmentRequest(
            image="base64encodedimage",
            detection_type="object",
            bbox=BoundingBox(x1=0.0, y1=0.0, x2=100.0, y2=100.0),
        )
        assert request.detection_type == "object"

    def test_request_with_options(self):
        """Test creating a request with options."""
        request = EnrichmentRequest(
            image="base64encodedimage",
            detection_type="person",
            bbox=BoundingBox(x1=0.0, y1=0.0, x2=100.0, y2=100.0),
            options={"include_depth": True, "include_pose": False},
        )
        assert request.options["include_depth"] is True
        assert request.options["include_pose"] is False

    def test_request_with_frames(self):
        """Test creating a request with frames for action recognition."""
        request = EnrichmentRequest(
            image="base64encodedimage",
            detection_type="person",
            bbox=BoundingBox(x1=0.0, y1=0.0, x2=100.0, y2=100.0),
            frames=["frame1base64", "frame2base64", "frame3base64"],
        )
        assert len(request.frames) == 3

    def test_request_requires_image(self):
        """Test that image field is required."""
        with pytest.raises(ValidationError):
            EnrichmentRequest(
                detection_type="person",
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=100.0, y2=100.0),
            )

    def test_request_requires_detection_type(self):
        """Test that detection_type field is required."""
        with pytest.raises(ValidationError):
            EnrichmentRequest(
                image="base64encodedimage",
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=100.0, y2=100.0),
            )

    def test_request_requires_bbox(self):
        """Test that bbox field is required."""
        with pytest.raises(ValidationError):
            EnrichmentRequest(
                image="base64encodedimage",
                detection_type="person",
            )


class TestEnrichmentResponseSchema:
    """Tests for EnrichmentResponse Pydantic model."""

    def test_minimal_response(self):
        """Test creating a minimal response with only required fields."""
        response = EnrichmentResponse(
            inference_time_ms=150.5,
        )
        assert response.inference_time_ms == 150.5
        assert response.pose is None
        assert response.clothing is None
        assert response.vehicle is None
        assert response.pet is None
        assert response.depth is None
        assert response.models_used == []

    def test_response_with_pose_result(self):
        """Test creating a response with pose result."""
        pose = PoseResult(
            keypoints=[{"name": "nose", "x": 0.5, "y": 0.3, "confidence": 0.95}],
            posture="standing",
            alerts=[],
        )
        response = EnrichmentResponse(
            pose=pose,
            models_used=["pose"],
            inference_time_ms=200.0,
        )
        assert response.pose is not None
        assert response.pose.posture == "standing"
        assert len(response.pose.keypoints) == 1

    def test_response_with_clothing_result(self):
        """Test creating a response with clothing result."""
        clothing = ClothingResult(
            clothing_type="hoodie",
            color="dark",
            style="suspicious",
            confidence=0.85,
            top_category="person wearing dark hoodie",
            description="Alert: dark hoodie with hood up",
            is_suspicious=True,
            is_service_uniform=False,
        )
        response = EnrichmentResponse(
            clothing=clothing,
            models_used=["clothing"],
            inference_time_ms=180.0,
        )
        assert response.clothing is not None
        assert response.clothing.is_suspicious is True
        assert response.clothing.clothing_type == "hoodie"

    def test_response_with_vehicle_result(self):
        """Test creating a response with vehicle result."""
        vehicle = VehicleEnrichmentResult(
            vehicle_type="pickup_truck",
            display_name="pickup truck",
            color="white",
            is_commercial=False,
            confidence=0.92,
        )
        response = EnrichmentResponse(
            vehicle=vehicle,
            models_used=["vehicle"],
            inference_time_ms=120.0,
        )
        assert response.vehicle is not None
        assert response.vehicle.vehicle_type == "pickup_truck"
        assert response.vehicle.color == "white"

    def test_response_with_pet_result(self):
        """Test creating a response with pet result."""
        pet = PetEnrichmentResult(
            pet_type="dog",
            breed="unknown",
            confidence=0.88,
            is_household_pet=True,
        )
        response = EnrichmentResponse(
            pet=pet,
            models_used=["pet"],
            inference_time_ms=90.0,
        )
        assert response.pet is not None
        assert response.pet.pet_type == "dog"

    def test_response_with_depth_result(self):
        """Test creating a response with depth result."""
        depth = DepthResult(
            estimated_distance_m=3.5,
            relative_depth=0.25,
            proximity_label="close",
        )
        response = EnrichmentResponse(
            depth=depth,
            models_used=["depth"],
            inference_time_ms=100.0,
        )
        assert response.depth is not None
        assert response.depth.estimated_distance_m == 3.5
        assert response.depth.proximity_label == "close"

    def test_response_with_multiple_results(self):
        """Test creating a response with multiple enrichment results."""
        response = EnrichmentResponse(
            pose=PoseResult(keypoints=[], posture="standing", alerts=[]),
            clothing=ClothingResult(
                clothing_type="casual",
                color="unknown",
                style="casual",
                confidence=0.7,
                top_category="person in casual clothes",
                description="Casual everyday clothes",
                is_suspicious=False,
                is_service_uniform=False,
            ),
            depth=DepthResult(
                estimated_distance_m=5.0,
                relative_depth=0.4,
                proximity_label="moderate distance",
            ),
            models_used=["pose", "clothing", "depth"],
            inference_time_ms=350.0,
        )
        assert response.pose is not None
        assert response.clothing is not None
        assert response.depth is not None
        assert len(response.models_used) == 3


class TestPoseResultSchema:
    """Tests for PoseResult Pydantic model."""

    def test_valid_pose_result(self):
        """Test creating a valid pose result."""
        pose = PoseResult(
            keypoints=[
                {"name": "nose", "x": 0.5, "y": 0.3, "confidence": 0.95},
                {"name": "left_shoulder", "x": 0.4, "y": 0.5, "confidence": 0.92},
            ],
            posture="standing",
            alerts=["hands_raised"],
        )
        assert pose.posture == "standing"
        assert len(pose.keypoints) == 2
        assert "hands_raised" in pose.alerts

    def test_pose_result_with_empty_alerts(self):
        """Test pose result with no alerts."""
        pose = PoseResult(
            keypoints=[],
            posture="unknown",
            alerts=[],
        )
        assert pose.alerts == []


class TestClothingResultSchema:
    """Tests for ClothingResult Pydantic model."""

    def test_suspicious_clothing_result(self):
        """Test clothing result for suspicious attire."""
        clothing = ClothingResult(
            clothing_type="hoodie",
            color="dark",
            style="suspicious",
            confidence=0.85,
            top_category="person wearing dark hoodie with hood up",
            description="Alert: dark hoodie with hood up",
            is_suspicious=True,
            is_service_uniform=False,
        )
        assert clothing.is_suspicious is True
        assert clothing.is_service_uniform is False

    def test_service_uniform_result(self):
        """Test clothing result for service uniform."""
        clothing = ClothingResult(
            clothing_type="uniform",
            color="brown",
            style="work",
            confidence=0.91,
            top_category="UPS driver in brown uniform",
            description="Service worker: UPS driver",
            is_suspicious=False,
            is_service_uniform=True,
        )
        assert clothing.is_suspicious is False
        assert clothing.is_service_uniform is True


class TestVehicleEnrichmentResultSchema:
    """Tests for VehicleEnrichmentResult Pydantic model."""

    def test_commercial_vehicle_result(self):
        """Test vehicle result for commercial vehicle."""
        vehicle = VehicleEnrichmentResult(
            vehicle_type="work_van",
            display_name="work van/delivery van",
            color="white",
            is_commercial=True,
            confidence=0.89,
        )
        assert vehicle.is_commercial is True

    def test_personal_vehicle_result(self):
        """Test vehicle result for personal vehicle."""
        vehicle = VehicleEnrichmentResult(
            vehicle_type="car",
            display_name="car/sedan",
            color=None,
            is_commercial=False,
            confidence=0.94,
        )
        assert vehicle.is_commercial is False
        assert vehicle.color is None


class TestDepthResultSchema:
    """Tests for DepthResult Pydantic model."""

    def test_close_proximity_result(self):
        """Test depth result for close proximity."""
        depth = DepthResult(
            estimated_distance_m=1.5,
            relative_depth=0.1,
            proximity_label="very close",
        )
        assert depth.proximity_label == "very close"

    def test_far_proximity_result(self):
        """Test depth result for far proximity."""
        depth = DepthResult(
            estimated_distance_m=12.0,
            relative_depth=0.85,
            proximity_label="very far",
        )
        assert depth.proximity_label == "very far"


class TestThreatResultSchema:
    """Tests for ThreatResult Pydantic model (placeholder)."""

    def test_no_threat_result(self):
        """Test threat result with no threats detected."""
        threat = ThreatResult(
            threats=[],
            has_threat=False,
        )
        assert threat.has_threat is False
        assert len(threat.threats) == 0

    def test_threat_detected_result(self):
        """Test threat result with threats detected."""
        threat = ThreatResult(
            threats=[
                {"type": "knife", "confidence": 0.87, "bbox": [10, 20, 50, 80], "severity": "high"}
            ],
            has_threat=True,
        )
        assert threat.has_threat is True
        assert len(threat.threats) == 1


class TestDemographicsResultSchema:
    """Tests for DemographicsResult Pydantic model (placeholder)."""

    def test_default_demographics_result(self):
        """Test demographics result with defaults."""
        demographics = DemographicsResult()
        assert demographics.age_range == "unknown"
        assert demographics.gender == "unknown"
        assert demographics.age_confidence == 0.0
        assert demographics.gender_confidence == 0.0

    def test_demographics_with_values(self):
        """Test demographics result with values."""
        demographics = DemographicsResult(
            age_range="25-35",
            age_confidence=0.78,
            gender="male",
            gender_confidence=0.85,
        )
        assert demographics.age_range == "25-35"
        assert demographics.gender == "male"


class TestBoundingBoxSchema:
    """Tests for BoundingBox Pydantic model."""

    def test_valid_bbox(self):
        """Test creating a valid bounding box."""
        bbox = BoundingBox(x1=10.0, y1=20.0, x2=100.0, y2=200.0)
        assert bbox.x1 == 10.0
        assert bbox.y1 == 20.0
        assert bbox.x2 == 100.0
        assert bbox.y2 == 200.0

    def test_bbox_with_floats(self):
        """Test bounding box with floating point coordinates."""
        bbox = BoundingBox(x1=10.5, y1=20.7, x2=100.3, y2=200.9)
        assert bbox.x1 == 10.5
        assert bbox.y2 == 200.9


# =============================================================================
# Test: Health Check and Status Endpoint Schemas (NEM-3046)
# =============================================================================


class TestReadinessResponseSchema:
    """Tests for ReadinessResponse Pydantic model."""

    def test_ready_response(self):
        """Test readiness response when system is ready."""
        response = ReadinessResponse(
            ready=True,
            gpu_available=True,
            model_manager_initialized=True,
        )
        assert response.ready is True
        assert response.gpu_available is True
        assert response.model_manager_initialized is True

    def test_not_ready_no_gpu(self):
        """Test readiness response when GPU is not available."""
        response = ReadinessResponse(
            ready=False,
            gpu_available=False,
            model_manager_initialized=True,
        )
        assert response.ready is False
        assert response.gpu_available is False

    def test_not_ready_no_manager(self):
        """Test readiness response when model manager is not initialized."""
        response = ReadinessResponse(
            ready=False,
            gpu_available=True,
            model_manager_initialized=False,
        )
        assert response.ready is False
        assert response.model_manager_initialized is False


class TestDetailedModelStatusSchema:
    """Tests for DetailedModelStatus Pydantic model."""

    def test_loaded_model_status(self):
        """Test detailed status for a loaded model."""
        status = DetailedModelStatus(
            name="vehicle_classifier",
            loaded=True,
            vram_mb=1500,
            priority="MEDIUM",
            last_used="2024-01-15T12:30:00",
        )
        assert status.name == "vehicle_classifier"
        assert status.loaded is True
        assert status.vram_mb == 1500
        assert status.priority == "MEDIUM"
        assert status.last_used == "2024-01-15T12:30:00"

    def test_model_status_without_last_used(self):
        """Test model status when last_used is not set."""
        status = DetailedModelStatus(
            name="pet_classifier",
            loaded=True,
            vram_mb=200,
            priority="MEDIUM",
        )
        assert status.last_used is None


class TestSystemStatusSchema:
    """Tests for SystemStatus Pydantic model."""

    def test_healthy_system_status(self):
        """Test system status when healthy."""
        status = SystemStatus(
            status="healthy",
            vram_total_mb=8192,
            vram_used_mb=2500,
            vram_available_mb=5692,
            vram_budget_mb=6963,
            loaded_models=[
                DetailedModelStatus(
                    name="vehicle_classifier",
                    loaded=True,
                    vram_mb=1500,
                    priority="MEDIUM",
                )
            ],
            pending_loads=[],
            uptime_seconds=3600.5,
        )
        assert status.status == "healthy"
        assert status.vram_total_mb == 8192
        assert status.vram_used_mb == 2500
        assert status.vram_available_mb == 5692
        assert len(status.loaded_models) == 1
        assert status.uptime_seconds == 3600.5

    def test_degraded_system_status(self):
        """Test system status when degraded (high VRAM usage)."""
        status = SystemStatus(
            status="degraded",
            vram_total_mb=8192,
            vram_used_mb=7900,
            vram_available_mb=292,
            vram_budget_mb=6963,
            loaded_models=[],
            pending_loads=["vehicle_classifier"],
            uptime_seconds=7200.0,
        )
        assert status.status == "degraded"
        assert len(status.pending_loads) == 1
        assert "vehicle_classifier" in status.pending_loads

    def test_unhealthy_system_status(self):
        """Test system status when unhealthy (no GPU)."""
        status = SystemStatus(
            status="unhealthy",
            vram_total_mb=0,
            vram_used_mb=0,
            vram_available_mb=0,
            vram_budget_mb=0,
            loaded_models=[],
            pending_loads=[],
            uptime_seconds=100.0,
        )
        assert status.status == "unhealthy"
        assert status.vram_total_mb == 0


class TestModelPreloadResponseSchema:
    """Tests for ModelPreloadResponse Pydantic model."""

    def test_successful_preload(self):
        """Test response for successful model preload."""
        response = ModelPreloadResponse(
            status="loaded",
            model="vehicle_classifier",
        )
        assert response.status == "loaded"
        assert response.model == "vehicle_classifier"
        assert response.message is None

    def test_failed_preload_unknown_model(self):
        """Test response for preload of unknown model."""
        response = ModelPreloadResponse(
            status="error",
            model="unknown_model",
            message="Unknown model: unknown_model",
        )
        assert response.status == "error"
        assert response.message is not None
        assert "Unknown model" in response.message

    def test_failed_preload_exception(self):
        """Test response for preload that raised an exception."""
        response = ModelPreloadResponse(
            status="error",
            model="vehicle_classifier",
            message="CUDA out of memory",
        )
        assert response.status == "error"
        assert response.message == "CUDA out of memory"


class TestModelUnloadResponseSchema:
    """Tests for ModelUnloadResponse Pydantic model."""

    def test_successful_unload(self):
        """Test response for successful model unload."""
        response = ModelUnloadResponse(
            status="unloaded",
            model="vehicle_classifier",
        )
        assert response.status == "unloaded"
        assert response.model == "vehicle_classifier"

    def test_unload_not_loaded(self):
        """Test response when trying to unload a model that isn't loaded."""
        response = ModelUnloadResponse(
            status="not_loaded",
            model="pet_classifier",
        )
        assert response.status == "not_loaded"
        assert response.model == "pet_classifier"


class TestModelRegistryEntrySchema:
    """Tests for ModelRegistryEntry Pydantic model."""

    def test_loaded_registry_entry(self):
        """Test registry entry for a loaded model."""
        entry = ModelRegistryEntry(
            name="fashion_clip",
            vram_mb=800,
            priority="HIGH",
            loaded=True,
        )
        assert entry.name == "fashion_clip"
        assert entry.vram_mb == 800
        assert entry.priority == "HIGH"
        assert entry.loaded is True

    def test_unloaded_registry_entry(self):
        """Test registry entry for an unloaded model."""
        entry = ModelRegistryEntry(
            name="depth_estimator",
            vram_mb=150,
            priority="LOW",
            loaded=False,
        )
        assert entry.loaded is False


class TestModelRegistryResponseSchema:
    """Tests for ModelRegistryResponse Pydantic model."""

    def test_registry_with_multiple_models(self):
        """Test registry response with multiple models."""
        response = ModelRegistryResponse(
            models=[
                ModelRegistryEntry(
                    name="vehicle_classifier",
                    vram_mb=1500,
                    priority="MEDIUM",
                    loaded=True,
                ),
                ModelRegistryEntry(
                    name="pet_classifier",
                    vram_mb=200,
                    priority="MEDIUM",
                    loaded=False,
                ),
                ModelRegistryEntry(
                    name="fashion_clip",
                    vram_mb=800,
                    priority="HIGH",
                    loaded=True,
                ),
            ]
        )
        assert len(response.models) == 3
        loaded_count = sum(1 for m in response.models if m.loaded)
        assert loaded_count == 2

    def test_empty_registry(self):
        """Test registry response with no models."""
        response = ModelRegistryResponse(models=[])
        assert len(response.models) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
