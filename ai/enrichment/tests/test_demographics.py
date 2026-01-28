"""Unit tests for Demographics Estimator (Age-Gender Model).

Tests cover:
- DemographicsEstimator initialization and validation
- DemographicsResult dataclass functionality
- Age label normalization for various model formats
- Gender label normalization
- Model loading and unloading behavior
- Image preprocessing (RGB conversion, numpy array handling)
- Confidence thresholds and standard age ranges

Note: These tests use mocked models to avoid requiring actual model files.
For integration tests with real models, see ai/enrichment/tests/integration/.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# Add the ai/enrichment directory to sys.path to enable imports
_enrichment_dir = Path(__file__).parent.parent
if str(_enrichment_dir) not in sys.path:
    sys.path.insert(0, str(_enrichment_dir))

# Now import from the local models module
from models.demographics import (
    AGE_RANGES,
    DEFAULT_AGE_CONFIDENCE_THRESHOLD,
    DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
    GENDER_LABELS,
    DemographicsEstimator,
    DemographicsResult,
    load_demographics,
    validate_model_path,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def dummy_face_image():
    """Create a dummy PIL image for face testing (224x224)."""
    return Image.new("RGB", (224, 224), color="beige")


@pytest.fixture
def dummy_face_image_grayscale():
    """Create a grayscale dummy image to test RGB conversion."""
    return Image.new("L", (224, 224), color=128)


@pytest.fixture
def dummy_face_image_numpy():
    """Create a numpy array image for testing numpy conversion."""
    return np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)


@pytest.fixture
def mock_age_model():
    """Create a mock age classification model."""
    model = MagicMock()
    model.config = MagicMock()
    model.config.num_labels = 9
    model.config.id2label = {
        "0": "0-2",
        "1": "3-9",
        "2": "10-19",
        "3": "20-29",
        "4": "30-39",
        "5": "40-49",
        "6": "50-59",
        "7": "60-69",
        "8": "more than 70",
    }
    return model


@pytest.fixture
def mock_gender_model():
    """Create a mock gender classification model."""
    model = MagicMock()
    model.config = MagicMock()
    model.config.num_labels = 2
    model.config.id2label = {
        "0": "female",
        "1": "male",
    }
    return model


@pytest.fixture
def mock_demographics_estimator(mock_age_model, mock_gender_model):
    """Create a mock DemographicsEstimator for testing without loading models."""
    estimator = DemographicsEstimator(
        age_model_path="/fake/age/model",
        gender_model_path="/fake/gender/model",
        device="cpu",
    )
    # Set up mock models
    estimator.age_model = mock_age_model
    estimator.age_processor = MagicMock()
    estimator.gender_model = mock_gender_model
    estimator.gender_processor = MagicMock()
    estimator._age_labels = list(mock_age_model.config.id2label.values())
    estimator._gender_labels = list(mock_gender_model.config.id2label.values())
    return estimator


class TestDemographicsConstants:
    """Tests for demographics module constants."""

    def test_age_ranges_has_six_ranges(self):
        """Test that AGE_RANGES contains exactly 6 age ranges as per spec."""
        assert len(AGE_RANGES) == 6
        assert AGE_RANGES == ["0-10", "11-20", "21-35", "36-50", "51-65", "65+"]

    def test_gender_labels_has_two_values(self):
        """Test that GENDER_LABELS contains female and male."""
        assert len(GENDER_LABELS) == 2
        assert "female" in GENDER_LABELS
        assert "male" in GENDER_LABELS

    def test_confidence_thresholds_are_valid(self):
        """Test that confidence thresholds are between 0 and 1."""
        assert 0.0 <= DEFAULT_AGE_CONFIDENCE_THRESHOLD <= 1.0
        assert 0.0 <= DEFAULT_GENDER_CONFIDENCE_THRESHOLD <= 1.0


# =============================================================================
# Test: DemographicsResult Dataclass
# =============================================================================


class TestDemographicsResult:
    """Tests for DemographicsResult dataclass."""

    def test_create_result(self):
        """Test creating a DemographicsResult with valid values."""
        result = DemographicsResult(
            age_range="21-35",
            age_confidence=0.85,
            gender="male",
            gender_confidence=0.92,
        )
        assert result.age_range == "21-35"
        assert result.age_confidence == 0.85
        assert result.gender == "male"
        assert result.gender_confidence == 0.92

    def test_result_to_dict(self):
        """Test converting DemographicsResult to dictionary."""
        result = DemographicsResult(
            age_range="36-50",
            age_confidence=0.7123456789,
            gender="female",
            gender_confidence=0.8765432,
        )
        result_dict = result.to_dict()

        assert result_dict["age_range"] == "36-50"
        assert result_dict["age_confidence"] == 0.7123  # Rounded to 4 decimal places
        assert result_dict["gender"] == "female"
        assert result_dict["gender_confidence"] == 0.8765  # Rounded to 4 decimal places

    def test_result_with_unknown_gender(self):
        """Test DemographicsResult with unknown gender."""
        result = DemographicsResult(
            age_range="51-65",
            age_confidence=0.65,
            gender="unknown",
            gender_confidence=0.0,
        )
        assert result.gender == "unknown"
        assert result.gender_confidence == 0.0


# =============================================================================
# Test: Model Path Validation
# =============================================================================


class TestModelPathValidation:
    """Tests for model path validation security."""

    def test_valid_local_path(self):
        """Test that valid local paths are accepted."""
        path = "/models/vit-age-classifier"
        assert validate_model_path(path) == path

    def test_valid_huggingface_path(self):
        """Test that valid HuggingFace model IDs are accepted."""
        path = "nateraw/vit-age-classifier"
        assert validate_model_path(path) == path

    def test_path_traversal_rejected(self):
        """Test that path traversal sequences are rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_model_path("/models/../etc/passwd")

    def test_path_traversal_in_middle_rejected(self):
        """Test that path traversal in middle of path is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_model_path("/models/good/../../bad")


# =============================================================================
# Test: DemographicsEstimator Initialization
# =============================================================================


class TestDemographicsEstimatorInit:
    """Tests for DemographicsEstimator initialization."""

    def test_init_with_age_model_only(self):
        """Test initialization with only age model path."""
        estimator = DemographicsEstimator(
            age_model_path="/models/age-model",
            device="cpu",
        )
        assert estimator.age_model_path == "/models/age-model"
        assert estimator.gender_model_path is None
        assert estimator.device == "cpu"
        assert estimator.age_model is None  # Not loaded yet
        assert estimator.gender_model is None

    def test_init_with_both_models(self):
        """Test initialization with both age and gender model paths."""
        estimator = DemographicsEstimator(
            age_model_path="/models/age-model",
            gender_model_path="/models/gender-model",
            device="cuda:0",
        )
        assert estimator.age_model_path == "/models/age-model"
        assert estimator.gender_model_path == "/models/gender-model"
        assert estimator.device == "cuda:0"

    def test_init_rejects_invalid_age_path(self):
        """Test that invalid age model path is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            DemographicsEstimator(
                age_model_path="../../../etc/passwd",
            )

    def test_init_rejects_invalid_gender_path(self):
        """Test that invalid gender model path is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            DemographicsEstimator(
                age_model_path="/valid/path",
                gender_model_path="../../../etc/passwd",
            )

    def test_is_loaded_property_false_initially(self):
        """Test that is_loaded is False before loading."""
        estimator = DemographicsEstimator(
            age_model_path="/models/age-model",
        )
        assert estimator.is_loaded is False


# =============================================================================
# Test: Age Label Normalization
# =============================================================================


class TestAgeLabelNormalization:
    """Tests for age label normalization from various model formats."""

    @pytest.fixture
    def estimator(self):
        """Create an estimator instance for testing normalization."""
        return DemographicsEstimator(
            age_model_path="/fake/path",
            device="cpu",
        )

    # Test nateraw/vit-age-classifier format
    @pytest.mark.parametrize(
        "model_label,expected_range",
        [
            ("0-2", "0-10"),
            ("3-9", "0-10"),
            ("10-19", "11-20"),
            ("20-29", "21-35"),
            ("30-39", "21-35"),
            ("40-49", "36-50"),
            ("50-59", "51-65"),
            ("60-69", "51-65"),
            ("more than 70", "65+"),
            ("70+", "65+"),
        ],
    )
    def test_nateraw_model_labels(self, estimator, model_label, expected_range):
        """Test normalization of nateraw/vit-age-classifier labels."""
        result = estimator._normalize_age_label(model_label)
        assert result == expected_range

    # Test semantic labels
    @pytest.mark.parametrize(
        "model_label,expected_range",
        [
            ("baby", "0-10"),
            ("toddler", "0-10"),
            ("child", "0-10"),
            ("kid", "0-10"),
            ("teenager", "11-20"),
            ("teen", "11-20"),
            ("young_adult", "21-35"),
            ("young adult", "21-35"),
            ("adult", "36-50"),
            ("middle_aged", "51-65"),
            ("middle aged", "51-65"),
            ("senior", "65+"),
            ("elderly", "65+"),
        ],
    )
    def test_semantic_age_labels(self, estimator, model_label, expected_range):
        """Test normalization of semantic age labels."""
        result = estimator._normalize_age_label(model_label)
        assert result == expected_range

    # Test case insensitivity
    def test_case_insensitive_normalization(self, estimator):
        """Test that normalization is case insensitive."""
        assert estimator._normalize_age_label("TEENAGER") == "11-20"
        assert estimator._normalize_age_label("Senior") == "65+"
        assert estimator._normalize_age_label("ADULT") == "36-50"

    # Test numeric range parsing
    @pytest.mark.parametrize(
        "model_label,expected_range",
        [
            ("5-10", "0-10"),
            ("15-20", "11-20"),
            ("25-30", "21-35"),
            ("45-55", "36-50"),
            ("55-60", "51-65"),
            ("70-80", "65+"),
        ],
    )
    def test_numeric_range_parsing(self, estimator, model_label, expected_range):
        """Test parsing of arbitrary numeric ranges."""
        result = estimator._normalize_age_label(model_label)
        assert result == expected_range

    def test_unknown_label_returns_unknown(self, estimator):
        """Test that unrecognized labels return 'unknown'."""
        result = estimator._normalize_age_label("some_random_label_xyz")
        assert result == "unknown"


# =============================================================================
# Test: Gender Label Normalization
# =============================================================================


class TestGenderLabelNormalization:
    """Tests for gender label normalization."""

    @pytest.fixture
    def estimator(self):
        """Create an estimator instance for testing normalization."""
        return DemographicsEstimator(
            age_model_path="/fake/path",
            device="cpu",
        )

    @pytest.mark.parametrize(
        "model_label,expected",
        [
            ("male", "male"),
            ("Male", "male"),
            ("MALE", "male"),
            ("man", "male"),
            ("Man", "male"),
            ("m", "male"),
            ("M", "male"),
            ("boy", "male"),
        ],
    )
    def test_male_label_variations(self, estimator, model_label, expected):
        """Test normalization of male label variations."""
        result = estimator._normalize_gender_label(model_label)
        assert result == expected

    @pytest.mark.parametrize(
        "model_label,expected",
        [
            ("female", "female"),
            ("Female", "female"),
            ("FEMALE", "female"),
            ("woman", "female"),
            ("Woman", "female"),
            ("f", "female"),
            ("F", "female"),
            ("girl", "female"),
        ],
    )
    def test_female_label_variations(self, estimator, model_label, expected):
        """Test normalization of female label variations."""
        result = estimator._normalize_gender_label(model_label)
        assert result == expected

    def test_unknown_gender_label(self, estimator):
        """Test that unrecognized gender labels return 'unknown'."""
        assert estimator._normalize_gender_label("other") == "unknown"
        assert estimator._normalize_gender_label("nonbinary") == "unknown"
        assert estimator._normalize_gender_label("xyz") == "unknown"


# =============================================================================
# Test: Image Preprocessing
# =============================================================================


class TestImagePreprocessing:
    """Tests for image input handling."""

    def test_accepts_rgb_image(self, mock_demographics_estimator, dummy_face_image):
        """Test that RGB PIL images are accepted."""
        import torch

        # Setup mock to return tensor output
        mock_demographics_estimator.age_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.age_model.return_value = MagicMock(logits=torch.randn(1, 9))
        mock_demographics_estimator.gender_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.gender_model.return_value = MagicMock(logits=torch.randn(1, 2))

        result = mock_demographics_estimator.estimate_demographics(dummy_face_image)
        assert isinstance(result, DemographicsResult)

    def test_converts_grayscale_to_rgb(
        self, mock_demographics_estimator, dummy_face_image_grayscale
    ):
        """Test that grayscale images are converted to RGB."""
        import torch

        # Setup mock to return tensor output
        mock_demographics_estimator.age_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.age_model.return_value = MagicMock(logits=torch.randn(1, 9))
        mock_demographics_estimator.gender_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.gender_model.return_value = MagicMock(logits=torch.randn(1, 2))

        # Should not raise, even with grayscale input
        result = mock_demographics_estimator.estimate_demographics(dummy_face_image_grayscale)
        assert isinstance(result, DemographicsResult)

    def test_accepts_numpy_array(self, mock_demographics_estimator, dummy_face_image_numpy):
        """Test that numpy arrays are accepted and converted."""
        import torch

        # Setup mock to return tensor output
        mock_demographics_estimator.age_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.age_model.return_value = MagicMock(logits=torch.randn(1, 9))
        mock_demographics_estimator.gender_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.gender_model.return_value = MagicMock(logits=torch.randn(1, 2))

        result = mock_demographics_estimator.estimate_demographics(dummy_face_image_numpy)
        assert isinstance(result, DemographicsResult)

    def test_rejects_invalid_type(self, mock_demographics_estimator):
        """Test that invalid input types raise TypeError."""
        with pytest.raises(TypeError, match=r"Expected PIL\.Image\.Image or numpy array"):
            mock_demographics_estimator.estimate_demographics("not an image")

        with pytest.raises(TypeError, match=r"Expected PIL\.Image\.Image or numpy array"):
            mock_demographics_estimator.estimate_demographics([1, 2, 3])


# =============================================================================
# Test: Model Loading and Unloading
# =============================================================================


class TestModelLoadingUnloading:
    """Tests for model load/unload behavior."""

    def test_estimate_raises_if_not_loaded(self, dummy_face_image):
        """Test that estimation raises RuntimeError if model not loaded."""
        estimator = DemographicsEstimator(
            age_model_path="/fake/path",
            device="cpu",
        )
        with pytest.raises(RuntimeError, match="not loaded"):
            estimator.estimate_demographics(dummy_face_image)

    def test_unload_safe_when_not_loaded(self):
        """Test that unload is safe to call even when not loaded."""
        estimator = DemographicsEstimator(
            age_model_path="/fake/path",
            device="cpu",
        )
        # Should not raise
        estimator.unload()
        assert estimator.age_model is None

    def test_unload_clears_all_components(self, mock_demographics_estimator):
        """Test that unload clears all model components."""
        # Verify models are set
        assert mock_demographics_estimator.age_model is not None
        assert mock_demographics_estimator.gender_model is not None

        # Unload
        with patch("torch.cuda.is_available", return_value=False):
            mock_demographics_estimator.unload()

        # Verify all cleared
        assert mock_demographics_estimator.age_model is None
        assert mock_demographics_estimator.age_processor is None
        assert mock_demographics_estimator.gender_model is None
        assert mock_demographics_estimator.gender_processor is None

    def test_is_loaded_property_after_load(self, mock_demographics_estimator):
        """Test that is_loaded returns True after loading."""
        assert mock_demographics_estimator.is_loaded is True

    def test_load_model_signature_returns_self(self):
        """Test that load_model is designed to return self for method chaining.

        Since load_model makes external calls to HuggingFace, we verify the
        return type annotation indicates self-return pattern. This is validated
        by the mock_demographics_estimator fixture which manually sets up the
        models, demonstrating that after load_model the instance is usable.
        """
        import inspect

        from models.demographics import DemographicsEstimator

        # Verify the return type annotation shows self-return pattern
        load_method = DemographicsEstimator.load_model
        sig = inspect.signature(load_method)
        return_annotation = sig.return_annotation

        # The return annotation should contain "DemographicsEstimator"
        # (it could be a string forward reference or the class)
        annotation_str = str(return_annotation)
        assert "DemographicsEstimator" in annotation_str, (
            f"Expected return annotation to indicate self, got {return_annotation}"
        )

        # Additional verification: check the docstring mentions returning self
        docstring_lower = load_method.__doc__.lower()
        assert "self" in docstring_lower or "chaining" in docstring_lower, (
            "Expected docstring to mention self or method chaining"
        )


# =============================================================================
# Test: Factory Function
# =============================================================================


class TestLoadDemographicsFactory:
    """Tests for the load_demographics factory function."""

    @patch.object(DemographicsEstimator, "load_model")
    def test_factory_creates_and_loads(self, mock_load):
        """Test that factory creates estimator and calls load_model."""
        mock_load.return_value = MagicMock()

        result = load_demographics(
            age_model_path="/models/age",
            gender_model_path="/models/gender",
            device="cuda:0",
        )

        assert isinstance(result, DemographicsEstimator)
        mock_load.assert_called_once()

    @patch.object(DemographicsEstimator, "load_model")
    def test_factory_without_gender_model(self, mock_load):
        """Test that factory works without gender model."""
        mock_load.return_value = MagicMock()

        result = load_demographics(
            age_model_path="/models/age",
            device="cpu",
        )

        assert isinstance(result, DemographicsEstimator)
        assert result.gender_model_path is None


# =============================================================================
# Test: Estimation Without Gender Model
# =============================================================================


class TestEstimationWithoutGenderModel:
    """Tests for demographics estimation when gender model is not loaded."""

    def test_returns_unknown_gender_when_no_gender_model(self, dummy_face_image):
        """Test that unknown gender is returned when gender model is absent."""
        import torch

        estimator = DemographicsEstimator(
            age_model_path="/fake/path",
            device="cpu",
        )
        # Only set up age model
        estimator.age_model = MagicMock()
        estimator.age_processor = MagicMock()
        estimator.age_processor.return_value = {"pixel_values": torch.randn(1, 3, 224, 224)}
        estimator.age_model.return_value = MagicMock(logits=torch.randn(1, 6))
        estimator._age_labels = AGE_RANGES

        result = estimator.estimate_demographics(dummy_face_image)

        assert result.gender == "unknown"
        assert result.gender_confidence == 0.0
        # Age should still be estimated
        assert result.age_range in AGE_RANGES or result.age_range == "unknown"


# =============================================================================
# Test: Diverse Face Image Scenarios
# =============================================================================


class TestDiverseFaceScenarios:
    """Tests for demographics estimation with diverse test images.

    Note: These are unit tests with mocked models. For actual accuracy
    testing with real models and diverse images, use integration tests.
    """

    @pytest.fixture
    def estimator_with_deterministic_output(self):
        """Create an estimator that returns predictable outputs."""

        estimator = DemographicsEstimator(
            age_model_path="/fake/path",
            gender_model_path="/fake/gender/path",
            device="cpu",
        )

        # Mock age model to return specific logits
        estimator.age_model = MagicMock()
        estimator.age_processor = MagicMock()
        estimator._age_labels = ["0-2", "10-19", "20-29", "40-49", "60-69", "more than 70"]

        # Mock gender model
        estimator.gender_model = MagicMock()
        estimator.gender_processor = MagicMock()
        estimator._gender_labels = ["female", "male"]

        return estimator

    def test_young_adult_prediction(self, estimator_with_deterministic_output):
        """Test prediction for young adult age range."""
        import torch

        # Setup to predict age index 2 (20-29 -> 21-35)
        logits = torch.zeros(1, 6)
        logits[0, 2] = 10.0  # High score for index 2

        estimator_with_deterministic_output.age_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        estimator_with_deterministic_output.age_model.return_value = MagicMock(logits=logits)
        estimator_with_deterministic_output.gender_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        estimator_with_deterministic_output.gender_model.return_value = MagicMock(
            logits=torch.tensor([[0.0, 5.0]])  # Male
        )

        result = estimator_with_deterministic_output.estimate_demographics(
            Image.new("RGB", (224, 224))
        )

        assert result.age_range == "21-35"
        assert result.gender == "male"

    def test_senior_prediction(self, estimator_with_deterministic_output):
        """Test prediction for senior age range."""
        import torch

        # Setup to predict age index 5 (more than 70 -> 65+)
        logits = torch.zeros(1, 6)
        logits[0, 5] = 10.0

        estimator_with_deterministic_output.age_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        estimator_with_deterministic_output.age_model.return_value = MagicMock(logits=logits)
        estimator_with_deterministic_output.gender_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        estimator_with_deterministic_output.gender_model.return_value = MagicMock(
            logits=torch.tensor([[5.0, 0.0]])  # Female
        )

        result = estimator_with_deterministic_output.estimate_demographics(
            Image.new("RGB", (224, 224))
        )

        assert result.age_range == "65+"
        assert result.gender == "female"


# =============================================================================
# Test: Confidence Thresholds
# =============================================================================


class TestConfidenceThresholds:
    """Tests for confidence value behavior."""

    def test_confidence_is_valid_probability(self, mock_demographics_estimator):
        """Test that confidence values are valid probabilities (0-1)."""
        import torch

        # Setup mock to return specific logits
        mock_demographics_estimator.age_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.age_model.return_value = MagicMock(
            logits=torch.tensor([[1.0, 2.0, 3.0, 2.0, 1.0, 0.5, 0.3, 0.2, 0.1]])
        )
        mock_demographics_estimator.gender_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.gender_model.return_value = MagicMock(
            logits=torch.tensor([[2.0, 3.0]])
        )

        result = mock_demographics_estimator.estimate_demographics(Image.new("RGB", (224, 224)))

        assert 0.0 <= result.age_confidence <= 1.0
        assert 0.0 <= result.gender_confidence <= 1.0

    def test_high_confidence_with_clear_prediction(self, mock_demographics_estimator):
        """Test that clear predictions result in high confidence."""
        import torch

        # Setup mock with very high logit for one class
        mock_demographics_estimator.age_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        # One class has much higher logit
        logits = torch.tensor([[-10.0, -10.0, 100.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0]])
        mock_demographics_estimator.age_model.return_value = MagicMock(logits=logits)
        mock_demographics_estimator.gender_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }
        mock_demographics_estimator.gender_model.return_value = MagicMock(
            logits=torch.tensor([[-10.0, 100.0]])
        )

        result = mock_demographics_estimator.estimate_demographics(Image.new("RGB", (224, 224)))

        # With such extreme logits, softmax should give ~1.0
        assert result.age_confidence > 0.99
        assert result.gender_confidence > 0.99
