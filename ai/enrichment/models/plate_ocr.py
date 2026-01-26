"""PaddleOCR-based License Plate Text Recognition Module.

This module provides the PlateOCR class for extracting text from license plate
images using PaddleOCR with specialized processing for plate recognition.

Features:
- Angle correction for tilted plates
- Low-light enhancement using CLAHE
- Motion blur detection and image quality assessment
- Alphanumeric character filtering
- Confidence-weighted text extraction

Model Details:
- Model: PaddleOCR English model with angle classification
- VRAM: ~500MB (GPU mode)
- Output: Text strings with per-character and aggregate confidence scores

Environment Variables:
- PLATE_OCR_USE_GPU: Enable GPU acceleration (default: true if CUDA available)
- PLATE_OCR_LANG: OCR language (default: en)

Reference: https://github.com/PaddlePaddle/PaddleOCR
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Valid license plate characters (alphanumeric only)
VALID_CHARS: frozenset[str] = frozenset("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Image quality thresholds
MIN_QUALITY_SCORE = 0.3  # Below this, image is likely too blurry/dark
MOTION_BLUR_THRESHOLD = 100.0  # Laplacian variance threshold for motion blur
LOW_LIGHT_THRESHOLD = 50.0  # Mean brightness threshold for low-light detection


def _get_gpu_enabled() -> bool:
    """Check if GPU should be used for OCR inference.

    Returns:
        True if PLATE_OCR_USE_GPU is set to 'true' or CUDA is available.
    """
    value = os.environ.get("PLATE_OCR_USE_GPU", "").lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False

    # Auto-detect CUDA availability
    try:
        import paddle

        return bool(paddle.is_compiled_with_cuda())
    except ImportError:
        return False


def _get_ocr_language() -> str:
    """Get the OCR language from environment.

    Returns:
        Language code for PaddleOCR (default: 'en').
    """
    return os.environ.get("PLATE_OCR_LANG", "en")


@dataclass
class PlateOCRResult:
    """Result from license plate OCR processing.

    Attributes:
        plate_text: Filtered plate text (alphanumeric only)
        raw_text: Original OCR output before filtering
        ocr_confidence: Aggregate OCR confidence (0-1)
        char_confidences: Per-character confidence scores
        image_quality_score: Quality assessment score (0-1)
        is_enhanced: Whether low-light enhancement was applied
        is_blurry: Whether motion blur was detected
    """

    plate_text: str
    raw_text: str
    ocr_confidence: float
    char_confidences: list[float]
    image_quality_score: float
    is_enhanced: bool
    is_blurry: bool


class PlateOCR:
    """PaddleOCR-based license plate text recognition.

    This class provides text extraction from cropped license plate images
    with specialized preprocessing for plate recognition scenarios.

    Features:
    - Automatic angle correction for tilted plates
    - CLAHE-based enhancement for low-light conditions
    - Motion blur detection and quality assessment
    - Alphanumeric character filtering

    Attributes:
        use_gpu: Whether GPU acceleration is enabled
        lang: OCR language (e.g., 'en')
        ocr: The PaddleOCR instance

    Example:
        >>> ocr = PlateOCR()
        >>> ocr.load_model()
        >>> result = ocr.recognize_text(plate_crop)
        >>> print(f"Plate: {result.plate_text}, Confidence: {result.ocr_confidence}")
    """

    def __init__(
        self,
        use_gpu: bool | None = None,
        lang: str | None = None,
    ) -> None:
        """Initialize PlateOCR.

        Args:
            use_gpu: Whether to use GPU acceleration. If None, auto-detected.
            lang: OCR language code. If None, uses PLATE_OCR_LANG env var or 'en'.
        """
        self.use_gpu = use_gpu if use_gpu is not None else _get_gpu_enabled()
        self.lang = lang if lang is not None else _get_ocr_language()
        self.ocr: Any = None

        logger.info(f"Initializing PlateOCR (GPU: {self.use_gpu}, lang: {self.lang})")

    def load_model(self) -> PlateOCR:
        """Load the PaddleOCR model into memory.

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If paddleocr is not installed.
        """
        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            logger.error(
                "paddleocr package not installed. Install with: pip install paddleocr paddlepaddle"
            )
            raise ImportError(
                "paddleocr package required for license plate OCR. "
                "Install with: pip install paddleocr paddlepaddle"
            ) from e

        logger.info("Loading PaddleOCR model...")
        self.ocr = PaddleOCR(
            use_angle_cls=True,  # Enable angle classification for tilted plates
            lang=self.lang,
            use_gpu=self.use_gpu,
            show_log=False,  # Suppress verbose logging
        )

        logger.info("PlateOCR model loaded successfully")
        return self

    def unload(self) -> None:
        """Unload the model from memory."""
        if self.ocr is not None:
            del self.ocr
            self.ocr = None
            logger.info("PlateOCR model unloaded")

    def recognize_text(
        self,
        plate_crop: NDArray[np.uint8],
        auto_enhance: bool = True,
    ) -> PlateOCRResult:
        """Extract text from a cropped license plate image.

        This method performs OCR on a cropped plate image with optional
        preprocessing for low-light and blur conditions.

        Args:
            plate_crop: Cropped license plate image (BGR or RGB numpy array)
            auto_enhance: Whether to automatically enhance low-light images

        Returns:
            PlateOCRResult with extracted text and confidence scores

        Raises:
            RuntimeError: If model is not loaded
        """
        if self.ocr is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Assess image quality
        quality_score = self.assess_quality(plate_crop)
        is_blurry = self._detect_motion_blur(plate_crop)
        is_enhanced = False

        # Apply enhancement if needed and enabled
        processed_image = plate_crop.copy()
        if auto_enhance:
            if self._is_low_light(plate_crop):
                processed_image = self.enhance_image(processed_image)
                is_enhanced = True

        # Run OCR
        try:
            results = self.ocr.ocr(processed_image, cls=True)
        except Exception as e:
            logger.warning(f"OCR inference failed: {e}")
            return PlateOCRResult(
                plate_text="",
                raw_text="",
                ocr_confidence=0.0,
                char_confidences=[],
                image_quality_score=quality_score,
                is_enhanced=is_enhanced,
                is_blurry=is_blurry,
            )

        # Process OCR results
        if not results or not results[0]:
            return PlateOCRResult(
                plate_text="",
                raw_text="",
                ocr_confidence=0.0,
                char_confidences=[],
                image_quality_score=quality_score,
                is_enhanced=is_enhanced,
                is_blurry=is_blurry,
            )

        # Extract text and confidence from results
        raw_text, ocr_confidence, char_confidences = self._process_ocr_results(results)

        # Filter to valid plate characters
        plate_text = self.filter_plate_text(raw_text)

        return PlateOCRResult(
            plate_text=plate_text,
            raw_text=raw_text,
            ocr_confidence=ocr_confidence,
            char_confidences=char_confidences,
            image_quality_score=quality_score,
            is_enhanced=is_enhanced,
            is_blurry=is_blurry,
        )

    def recognize_text_batch(
        self,
        plate_crops: list[NDArray[np.uint8]],
        auto_enhance: bool = True,
    ) -> list[PlateOCRResult]:
        """Extract text from multiple cropped license plate images.

        Args:
            plate_crops: List of cropped plate images
            auto_enhance: Whether to automatically enhance low-light images

        Returns:
            List of PlateOCRResult, one per input image
        """
        return [self.recognize_text(crop, auto_enhance=auto_enhance) for crop in plate_crops]

    def enhance_image(self, plate_crop: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Enhance a plate image for low-light conditions using CLAHE.

        Contrast Limited Adaptive Histogram Equalization (CLAHE) improves
        local contrast while limiting noise amplification, making it ideal
        for enhancing license plates in poor lighting.

        Args:
            plate_crop: Input plate image (BGR or RGB)

        Returns:
            Enhanced image with improved contrast
        """
        # Convert to LAB color space for better enhancement
        enhanced: NDArray[np.uint8]
        if len(plate_crop.shape) == 3 and plate_crop.shape[2] == 3:
            lab = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2LAB)

            # Apply CLAHE to the L channel (luminance)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])

            # Convert back to BGR
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR).astype(np.uint8)
        else:
            # Grayscale image
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(plate_crop).astype(np.uint8)

        logger.debug("Applied CLAHE enhancement for low-light plate image")
        return enhanced

    def filter_plate_text(self, text: str) -> str:
        """Filter text to valid license plate characters only.

        Removes any characters that are not alphanumeric (0-9, A-Z).
        Commonly confused characters are standardized:
        - 'O' and '0' are kept as-is (ambiguity handled by application)
        - 'I' and '1' are kept as-is

        Args:
            text: Raw OCR text output

        Returns:
            Filtered text with only valid plate characters
        """
        # Convert to uppercase and filter
        filtered = "".join(c for c in text.upper() if c in VALID_CHARS)
        return filtered

    def assess_quality(self, plate_crop: NDArray[np.uint8]) -> float:
        """Assess the quality of a plate image for OCR reliability.

        Quality assessment considers:
        - Blur level (Laplacian variance)
        - Brightness (mean pixel value)
        - Contrast (standard deviation)

        Args:
            plate_crop: Input plate image

        Returns:
            Quality score from 0.0 (poor) to 1.0 (excellent)
        """
        # Convert to grayscale if needed
        if len(plate_crop.shape) == 3:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_crop

        # Calculate blur metric (Laplacian variance)
        # Higher values indicate sharper images
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Normalize blur score (typical range 0-1000)
        blur_score = min(laplacian_var / 500.0, 1.0)

        # Calculate brightness (mean pixel value)
        mean_brightness = float(np.mean(gray))
        # Optimal brightness around 128, penalize extreme values
        brightness_score = 1.0 - abs(mean_brightness - 128) / 128.0
        brightness_score = max(0.0, brightness_score)

        # Calculate contrast (standard deviation)
        std_dev = float(np.std(gray))
        # Good contrast typically has std > 50
        contrast_score = min(std_dev / 80.0, 1.0)

        # Combined quality score (weighted average)
        quality_score = 0.5 * blur_score + 0.25 * brightness_score + 0.25 * contrast_score

        return round(quality_score, 3)

    def _is_low_light(self, plate_crop: NDArray[np.uint8]) -> bool:
        """Check if the image is in low-light conditions.

        Args:
            plate_crop: Input plate image

        Returns:
            True if the image appears to be in low-light conditions
        """
        # Convert to grayscale if needed
        if len(plate_crop.shape) == 3:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_crop

        mean_brightness = float(np.mean(gray))
        return mean_brightness < LOW_LIGHT_THRESHOLD

    def _detect_motion_blur(self, plate_crop: NDArray[np.uint8]) -> bool:
        """Detect if the image has significant motion blur.

        Uses Laplacian variance as a blur metric. Low variance indicates
        blur (edges are smoothed out).

        Args:
            plate_crop: Input plate image

        Returns:
            True if motion blur is detected
        """
        # Convert to grayscale if needed
        if len(plate_crop.shape) == 3:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_crop

        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return laplacian_var < MOTION_BLUR_THRESHOLD

    def _process_ocr_results(
        self,
        results: list,
    ) -> tuple[str, float, list[float]]:
        """Process PaddleOCR results to extract text and confidence.

        PaddleOCR returns results in format:
        [[[box], (text, confidence)], ...]

        Args:
            results: Raw PaddleOCR output

        Returns:
            Tuple of (combined_text, average_confidence, char_confidences)
        """
        texts: list[str] = []
        confidences: list[float] = []

        for line in results[0]:
            if len(line) >= 2:
                text_info = line[1]
                if isinstance(text_info, tuple) and len(text_info) >= 2:
                    text, confidence = text_info[0], text_info[1]
                    texts.append(str(text))
                    confidences.append(float(confidence))

        if not texts:
            return "", 0.0, []

        # Combine all text lines
        combined_text = "".join(texts)

        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Distribute confidence to characters (approximation)
        char_confidences = []
        for text, conf in zip(texts, confidences, strict=True):
            char_confidences.extend([conf] * len(text))

        return combined_text, round(avg_confidence, 4), char_confidences


def load_plate_ocr(
    use_gpu: bool | None = None,
    lang: str | None = None,
) -> PlateOCR:
    """Factory function to create and load a PlateOCR instance.

    Args:
        use_gpu: Whether to use GPU. If None, auto-detected.
        lang: OCR language code. If None, uses environment variable.

    Returns:
        Loaded PlateOCR instance ready for inference.
    """
    ocr = PlateOCR(use_gpu=use_gpu, lang=lang)
    ocr.load_model()
    return ocr
