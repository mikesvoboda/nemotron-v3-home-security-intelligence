"""Unit tests for PaddleOCR-based PlateOCR license plate text recognition.

Tests cover:
- PlateOCRResult dataclass and quality metrics
- PlateOCR initialization and environment variable handling
- Image quality assessment (blur, brightness, contrast)
- Low-light detection and CLAHE enhancement
- Plate text filtering (alphanumeric characters)
- OCR result processing
- Model loading/unloading lifecycle
- Integration with PaddleOCR (mocked)

NEM-5372: Install PaddleOCR Package for Text Recognition
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

# Add the ai/enrichment directory to sys.path to enable imports
# This must happen before importing the local module
_enrichment_dir = Path(__file__).parent.parent
if str(_enrichment_dir) not in sys.path:
    sys.path.insert(0, str(_enrichment_dir))

from models.plate_ocr import (
    LOW_LIGHT_THRESHOLD,
    MIN_QUALITY_SCORE,
    MOTION_BLUR_THRESHOLD,
    VALID_CHARS,
    PlateOCR,
    PlateOCRResult,
    _get_gpu_enabled,
    _get_ocr_language,
    load_plate_ocr,
)

# =============================================================================
# Helper: Mock PaddleOCR Context Manager
# =============================================================================


@contextmanager
def mock_paddleocr_module(mock_model):
    """Context manager that mocks the paddleocr module for testing.

    Since PaddleOCR is imported inside the load_model() function,
    we need to patch sys.modules to provide a mock paddleocr module.

    Args:
        mock_model: The mock model instance to return from PaddleOCR()

    Yields:
        The mock PaddleOCR class for assertions
    """
    mock_paddleocr_class = MagicMock(return_value=mock_model)
    mock_module = MagicMock()
    mock_module.PaddleOCR = mock_paddleocr_class

    with patch.dict("sys.modules", {"paddleocr": mock_module}):
        yield mock_paddleocr_class


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def dummy_plate_image() -> np.ndarray:
    """Create a dummy BGR plate image for testing."""
    # Create a white plate with some dark text-like patterns
    img = np.ones((100, 300, 3), dtype=np.uint8) * 255
    # Add some dark rectangles to simulate text
    cv2.rectangle(img, (50, 30), (80, 70), (0, 0, 0), -1)
    cv2.rectangle(img, (100, 30), (130, 70), (0, 0, 0), -1)
    cv2.rectangle(img, (150, 30), (180, 70), (0, 0, 0), -1)
    return img


@pytest.fixture
def dark_plate_image() -> np.ndarray:
    """Create a dark/low-light plate image for testing."""
    # Mean brightness below LOW_LIGHT_THRESHOLD (50)
    img = np.ones((100, 300, 3), dtype=np.uint8) * 30
    return img


@pytest.fixture
def blurry_plate_image() -> np.ndarray:
    """Create a blurry plate image for testing."""
    # Create an image with low Laplacian variance (blurry)
    img = np.ones((100, 300, 3), dtype=np.uint8) * 128
    # Apply heavy Gaussian blur
    img = cv2.GaussianBlur(img, (31, 31), 0)
    return img


@pytest.fixture
def grayscale_plate_image() -> np.ndarray:
    """Create a grayscale plate image for testing."""
    img = np.ones((100, 300), dtype=np.uint8) * 200
    return img


@pytest.fixture
def mock_paddleocr_result():
    """Create a mock PaddleOCR result."""
    # PaddleOCR format: [[[box], (text, confidence)], ...]
    return [
        [
            [[[0, 0], [100, 0], [100, 50], [0, 50]], ("ABC", 0.95)],
            [[[100, 0], [200, 0], [200, 50], [100, 50]], ("123", 0.92)],
        ]
    ]


@pytest.fixture
def mock_paddleocr_model(mock_paddleocr_result):
    """Create a mock PaddleOCR model."""
    mock = MagicMock()
    mock.ocr.return_value = mock_paddleocr_result
    return mock


# =============================================================================
# Test: Constants and Environment Variables
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_valid_chars_contains_alphanumeric(self):
        """Test that VALID_CHARS contains all alphanumeric characters."""
        for char in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert char in VALID_CHARS

    def test_valid_chars_excludes_special(self):
        """Test that VALID_CHARS excludes special characters."""
        for char in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`":
            assert char not in VALID_CHARS

    def test_min_quality_score_is_positive(self):
        """Test that MIN_QUALITY_SCORE is a positive value."""
        assert MIN_QUALITY_SCORE > 0
        assert MIN_QUALITY_SCORE < 1

    def test_motion_blur_threshold_is_positive(self):
        """Test that MOTION_BLUR_THRESHOLD is a positive value."""
        assert MOTION_BLUR_THRESHOLD > 0

    def test_low_light_threshold_is_reasonable(self):
        """Test that LOW_LIGHT_THRESHOLD is in valid range."""
        assert 0 < LOW_LIGHT_THRESHOLD < 128


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_get_gpu_enabled_default_false(self):
        """Test that GPU is disabled when env var not set and CUDA unavailable."""
        # Mock paddle import to simulate import failure (CUDA unavailable)
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.dict("sys.modules", {"paddle": None}),
        ):
            result = _get_gpu_enabled()
            assert result is False

    def test_get_gpu_enabled_true(self):
        """Test that GPU is enabled when env var is 'true'."""
        with patch.dict("os.environ", {"PLATE_OCR_USE_GPU": "true"}):
            result = _get_gpu_enabled()
            assert result is True

    def test_get_gpu_enabled_false(self):
        """Test that GPU is disabled when env var is 'false'."""
        with patch.dict("os.environ", {"PLATE_OCR_USE_GPU": "false"}):
            result = _get_gpu_enabled()
            assert result is False

    def test_get_ocr_language_default(self):
        """Test that default language is 'en'."""
        with patch.dict("os.environ", {}, clear=True):
            result = _get_ocr_language()
            assert result == "en"

    def test_get_ocr_language_custom(self):
        """Test that custom language is respected."""
        with patch.dict("os.environ", {"PLATE_OCR_LANG": "ch"}):
            result = _get_ocr_language()
            assert result == "ch"


# =============================================================================
# Test: PlateOCRResult Dataclass
# =============================================================================


class TestPlateOCRResultDataclass:
    """Tests for the PlateOCRResult dataclass."""

    def test_result_creation(self):
        """Test creating a PlateOCRResult instance."""
        result = PlateOCRResult(
            plate_text="ABC123",
            raw_text="ABC 123",
            ocr_confidence=0.95,
            char_confidences=[0.95, 0.94, 0.96, 0.93, 0.95, 0.94],
            image_quality_score=0.85,
            is_enhanced=False,
            is_blurry=False,
        )
        assert result.plate_text == "ABC123"
        assert result.raw_text == "ABC 123"
        assert result.ocr_confidence == 0.95
        assert len(result.char_confidences) == 6
        assert result.image_quality_score == 0.85
        assert not result.is_enhanced
        assert not result.is_blurry

    def test_result_with_enhancement(self):
        """Test PlateOCRResult with enhancement applied."""
        result = PlateOCRResult(
            plate_text="XYZ789",
            raw_text="XYZ789",
            ocr_confidence=0.88,
            char_confidences=[0.88] * 6,
            image_quality_score=0.45,
            is_enhanced=True,
            is_blurry=False,
        )
        assert result.is_enhanced
        assert result.image_quality_score < 0.5

    def test_result_with_blur_detected(self):
        """Test PlateOCRResult with blur detected."""
        result = PlateOCRResult(
            plate_text="",
            raw_text="",
            ocr_confidence=0.0,
            char_confidences=[],
            image_quality_score=0.2,
            is_enhanced=False,
            is_blurry=True,
        )
        assert result.is_blurry
        assert result.plate_text == ""


# =============================================================================
# Test: PlateOCR Initialization
# =============================================================================


class TestPlateOCRInit:
    """Tests for PlateOCR initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("models.plate_ocr._get_gpu_enabled", return_value=False),
        ):
            ocr = PlateOCR()
            assert ocr.use_gpu is False
            assert ocr.lang == "en"
            assert ocr.ocr is None

    def test_init_with_gpu_enabled(self):
        """Test initialization with GPU enabled."""
        ocr = PlateOCR(use_gpu=True, lang="en")
        assert ocr.use_gpu is True
        assert ocr.lang == "en"

    def test_init_with_custom_language(self):
        """Test initialization with custom language."""
        ocr = PlateOCR(use_gpu=False, lang="ch")
        assert ocr.lang == "ch"


# =============================================================================
# Test: Image Quality Assessment
# =============================================================================


class TestImageQualityAssessment:
    """Tests for image quality assessment functions."""

    def test_assess_quality_good_image(self, dummy_plate_image):
        """Test quality assessment of a good image."""
        ocr = PlateOCR(use_gpu=False)
        quality = ocr.assess_quality(dummy_plate_image)
        assert 0.0 <= quality <= 1.0
        # Good quality image should have higher score
        assert quality > MIN_QUALITY_SCORE

    def test_assess_quality_blurry_image(self, blurry_plate_image):
        """Test quality assessment of a blurry image."""
        ocr = PlateOCR(use_gpu=False)
        quality = ocr.assess_quality(blurry_plate_image)
        assert 0.0 <= quality <= 1.0
        # Blurry image should have lower score
        assert quality < 0.5

    def test_assess_quality_grayscale(self, grayscale_plate_image):
        """Test quality assessment of a grayscale image."""
        ocr = PlateOCR(use_gpu=False)
        quality = ocr.assess_quality(grayscale_plate_image)
        assert 0.0 <= quality <= 1.0

    def test_detect_motion_blur_clear_image(self, dummy_plate_image):
        """Test motion blur detection on a clear image."""
        ocr = PlateOCR(use_gpu=False)
        is_blurry = ocr._detect_motion_blur(dummy_plate_image)
        assert is_blurry is False

    def test_detect_motion_blur_blurry_image(self, blurry_plate_image):
        """Test motion blur detection on a blurry image."""
        ocr = PlateOCR(use_gpu=False)
        is_blurry = ocr._detect_motion_blur(blurry_plate_image)
        assert is_blurry is True

    def test_is_low_light_normal_image(self, dummy_plate_image):
        """Test low-light detection on a normal image."""
        ocr = PlateOCR(use_gpu=False)
        is_dark = ocr._is_low_light(dummy_plate_image)
        assert is_dark is False

    def test_is_low_light_dark_image(self, dark_plate_image):
        """Test low-light detection on a dark image."""
        ocr = PlateOCR(use_gpu=False)
        is_dark = ocr._is_low_light(dark_plate_image)
        assert is_dark is True


# =============================================================================
# Test: Image Enhancement
# =============================================================================


class TestImageEnhancement:
    """Tests for CLAHE image enhancement."""

    def test_enhance_image_color(self, dark_plate_image):
        """Test CLAHE enhancement on a color image."""
        ocr = PlateOCR(use_gpu=False)
        enhanced = ocr.enhance_image(dark_plate_image)
        assert enhanced.shape == dark_plate_image.shape
        # Enhanced image should be brighter
        assert np.mean(enhanced) > np.mean(dark_plate_image)

    def test_enhance_image_grayscale(self, grayscale_plate_image):
        """Test CLAHE enhancement on a grayscale image."""
        # Make it dark first
        dark_gray = (grayscale_plate_image * 0.2).astype(np.uint8)
        ocr = PlateOCR(use_gpu=False)
        enhanced = ocr.enhance_image(dark_gray)
        assert enhanced.shape == dark_gray.shape
        # Enhanced should be brighter
        assert np.mean(enhanced) > np.mean(dark_gray)


# =============================================================================
# Test: Plate Text Filtering
# =============================================================================


class TestPlateTextFiltering:
    """Tests for plate text filtering."""

    def test_filter_basic_text(self):
        """Test filtering basic plate text."""
        ocr = PlateOCR(use_gpu=False)
        result = ocr.filter_plate_text("ABC 123")
        assert result == "ABC123"

    def test_filter_lowercase_text(self):
        """Test that lowercase is converted to uppercase."""
        ocr = PlateOCR(use_gpu=False)
        result = ocr.filter_plate_text("abc123")
        assert result == "ABC123"

    def test_filter_removes_special_chars(self):
        """Test that special characters are removed."""
        ocr = PlateOCR(use_gpu=False)
        result = ocr.filter_plate_text("ABC-123!")
        assert result == "ABC123"

    def test_filter_empty_string(self):
        """Test filtering empty string."""
        ocr = PlateOCR(use_gpu=False)
        result = ocr.filter_plate_text("")
        assert result == ""

    def test_filter_special_chars_only(self):
        """Test filtering string with only special characters."""
        ocr = PlateOCR(use_gpu=False)
        result = ocr.filter_plate_text("!@#$%")
        assert result == ""

    def test_filter_mixed_case_with_numbers(self):
        """Test filtering mixed case with numbers."""
        ocr = PlateOCR(use_gpu=False)
        result = ocr.filter_plate_text("AbC 1a2B 3c")
        assert result == "ABC1A2B3C"


# =============================================================================
# Test: OCR Result Processing
# =============================================================================


class TestOCRResultProcessing:
    """Tests for OCR result processing."""

    def test_process_ocr_results_normal(self, mock_paddleocr_result):
        """Test processing normal OCR results."""
        ocr = PlateOCR(use_gpu=False)
        text, confidence, char_confs = ocr._process_ocr_results(mock_paddleocr_result)
        assert text == "ABC123"
        assert 0.92 <= confidence <= 0.95
        assert len(char_confs) == 6

    def test_process_ocr_results_empty(self):
        """Test processing empty OCR results."""
        ocr = PlateOCR(use_gpu=False)
        empty_result = [[]]
        text, confidence, char_confs = ocr._process_ocr_results(empty_result)
        assert text == ""
        assert confidence == 0.0
        assert char_confs == []

    def test_process_ocr_results_single_line(self):
        """Test processing single-line OCR results."""
        ocr = PlateOCR(use_gpu=False)
        single_line_result = [
            [
                [[[0, 0], [100, 0], [100, 50], [0, 50]], ("TEST", 0.90)],
            ]
        ]
        text, confidence, char_confs = ocr._process_ocr_results(single_line_result)
        assert text == "TEST"
        assert confidence == 0.90
        assert len(char_confs) == 4


# =============================================================================
# Test: Model Loading/Unloading
# =============================================================================


class TestModelLifecycle:
    """Tests for model loading and unloading."""

    def test_load_model_sets_ocr(self, mock_paddleocr_model):
        """Test that load_model sets the OCR model."""
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            result = ocr.load_model()
            assert ocr.ocr is not None
            assert result is ocr  # Returns self

    def test_load_model_raises_import_error(self):
        """Test that load_model raises ImportError when paddleocr not installed."""
        # Remove paddleocr from sys.modules to simulate missing package
        with patch.dict("sys.modules", {"paddleocr": None}):
            ocr = PlateOCR(use_gpu=False)
            with pytest.raises(ImportError, match="paddleocr"):
                ocr.load_model()

    def test_unload_clears_model(self, mock_paddleocr_model):
        """Test that unload clears the model."""
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            assert ocr.ocr is not None
            ocr.unload()
            assert ocr.ocr is None


# =============================================================================
# Test: Full Recognition Pipeline
# =============================================================================


class TestRecognitionPipeline:
    """Tests for the full OCR recognition pipeline."""

    def test_recognize_text_returns_result(
        self, dummy_plate_image, mock_paddleocr_model, mock_paddleocr_result
    ):
        """Test that recognize_text returns a PlateOCRResult."""
        mock_paddleocr_model.ocr.return_value = mock_paddleocr_result
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(dummy_plate_image)
            assert isinstance(result, PlateOCRResult)
            assert result.plate_text == "ABC123"

    def test_recognize_text_without_model_raises_error(self, dummy_plate_image):
        """Test that recognize_text raises error if model not loaded."""
        ocr = PlateOCR(use_gpu=False)
        with pytest.raises(RuntimeError, match="Model not loaded"):
            ocr.recognize_text(dummy_plate_image)

    def test_recognize_text_with_enhancement(
        self, dark_plate_image, mock_paddleocr_model, mock_paddleocr_result
    ):
        """Test recognition with auto-enhancement on dark image."""
        mock_paddleocr_model.ocr.return_value = mock_paddleocr_result
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(dark_plate_image, auto_enhance=True)
            assert isinstance(result, PlateOCRResult)
            assert result.is_enhanced is True

    def test_recognize_text_without_enhancement(
        self, dark_plate_image, mock_paddleocr_model, mock_paddleocr_result
    ):
        """Test recognition without auto-enhancement."""
        mock_paddleocr_model.ocr.return_value = mock_paddleocr_result
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(dark_plate_image, auto_enhance=False)
            assert isinstance(result, PlateOCRResult)
            assert result.is_enhanced is False

    def test_recognize_text_handles_ocr_exception(self, dummy_plate_image, mock_paddleocr_model):
        """Test that OCR exceptions are handled gracefully."""
        mock_paddleocr_model.ocr.side_effect = RuntimeError("OCR failed")
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(dummy_plate_image)
            assert isinstance(result, PlateOCRResult)
            assert result.plate_text == ""
            assert result.ocr_confidence == 0.0

    def test_recognize_text_no_results(self, dummy_plate_image, mock_paddleocr_model):
        """Test recognition when OCR finds no text."""
        mock_paddleocr_model.ocr.return_value = [[]]
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(dummy_plate_image)
            assert result.plate_text == ""
            assert result.ocr_confidence == 0.0


# =============================================================================
# Test: Batch Recognition
# =============================================================================


class TestBatchRecognition:
    """Tests for batch plate recognition."""

    def test_recognize_text_batch(
        self, dummy_plate_image, mock_paddleocr_model, mock_paddleocr_result
    ):
        """Test batch recognition of multiple plates."""
        mock_paddleocr_model.ocr.return_value = mock_paddleocr_result
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            plates = [dummy_plate_image, dummy_plate_image, dummy_plate_image]
            results = ocr.recognize_text_batch(plates)
            assert len(results) == 3
            assert all(isinstance(r, PlateOCRResult) for r in results)

    def test_recognize_text_batch_empty(self, mock_paddleocr_model):
        """Test batch recognition with empty list."""
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            results = ocr.recognize_text_batch([])
            assert results == []


# =============================================================================
# Test: Factory Function
# =============================================================================


class TestFactoryFunction:
    """Tests for the load_plate_ocr factory function."""

    def test_load_plate_ocr_creates_and_loads(self, mock_paddleocr_model):
        """Test that load_plate_ocr creates and loads model."""
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = load_plate_ocr(use_gpu=False, lang="en")
            assert isinstance(ocr, PlateOCR)
            assert ocr.ocr is not None

    def test_load_plate_ocr_with_custom_options(self, mock_paddleocr_model):
        """Test factory function with custom options."""
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = load_plate_ocr(use_gpu=True, lang="ch")
            assert ocr.use_gpu is True
            assert ocr.lang == "ch"


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_small_image(self, mock_paddleocr_model, mock_paddleocr_result):
        """Test recognition with very small image."""
        small_img = np.ones((10, 30, 3), dtype=np.uint8) * 200
        mock_paddleocr_model.ocr.return_value = mock_paddleocr_result
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(small_img)
            assert isinstance(result, PlateOCRResult)

    def test_high_contrast_image(self, mock_paddleocr_model, mock_paddleocr_result):
        """Test recognition with high contrast image."""
        img = np.zeros((100, 300, 3), dtype=np.uint8)
        img[30:70, 50:250] = 255  # White rectangle on black
        mock_paddleocr_model.ocr.return_value = mock_paddleocr_result
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(img)
            assert isinstance(result, PlateOCRResult)

    def test_all_zeros_image(self, mock_paddleocr_model):
        """Test recognition with all-black image."""
        black_img = np.zeros((100, 300, 3), dtype=np.uint8)
        mock_paddleocr_model.ocr.return_value = [[]]
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(black_img)
            assert result.plate_text == ""
            assert result.is_blurry is True  # Should detect as low contrast/blurry

    def test_null_ocr_result(self, dummy_plate_image, mock_paddleocr_model):
        """Test handling of null OCR result."""
        mock_paddleocr_model.ocr.return_value = None
        with mock_paddleocr_module(mock_paddleocr_model):
            ocr = PlateOCR(use_gpu=False)
            ocr.load_model()
            result = ocr.recognize_text(dummy_plate_image)
            assert result.plate_text == ""
