"""Image quality assessment model loader using PyIQA/BRISQUE.

This module provides CPU-based image quality assessment using the BRISQUE
(Blind/Referenceless Image Spatial Quality Evaluator) metric via the pyiqa library.

BRISQUE is a no-reference image quality metric that analyzes natural scene statistics
to detect quality degradations like blur, noise, and compression artifacts.

VRAM Usage: 0 MB (CPU-based)
Library: pyiqa
Metric: BRISQUE

Security Use Cases:
    - Detect camera obstruction/tampering (sudden quality drop)
    - Identify blurry frames from fast movement (running person)
    - Filter low-quality frames before AI processing
    - Monitor camera health over time
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# BRISQUE score thresholds
# Lower scores = better quality (0 is perfect, 100+ is very poor)
BRISQUE_BLUR_THRESHOLD = 50.0  # Above this indicates significant blur
BRISQUE_NOISE_THRESHOLD = 60.0  # Above this indicates significant noise
BRISQUE_LOW_QUALITY_THRESHOLD = 40.0  # Above this is generally low quality


@dataclass
class ImageQualityResult:
    """Result from BRISQUE image quality assessment.

    Attributes:
        quality_score: Quality score 0-100 (higher is better, inverted from BRISQUE)
        brisque_score: Raw BRISQUE score (lower is better, 0-100+)
        is_blurry: Whether the image shows significant blur
        is_noisy: Whether the image shows significant noise
        is_low_quality: Whether the image is generally low quality
        quality_issues: List of detected quality issues
    """

    quality_score: float
    brisque_score: float
    is_blurry: bool
    is_noisy: bool
    is_low_quality: bool
    quality_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "quality_score": self.quality_score,
            "brisque_score": self.brisque_score,
            "is_blurry": self.is_blurry,
            "is_noisy": self.is_noisy,
            "is_low_quality": self.is_low_quality,
            "quality_issues": self.quality_issues,
        }

    @property
    def is_good_quality(self) -> bool:
        """Check if image has good quality (no major issues)."""
        return not self.is_low_quality and not self.is_blurry and not self.is_noisy

    def format_context(self) -> str:
        """Format quality assessment for LLM context.

        Returns:
            Formatted string describing image quality
        """
        if self.is_good_quality:
            return f"Good image quality (score: {self.quality_score:.0f}/100)"

        issues_str = (
            ", ".join(self.quality_issues) if self.quality_issues else "general degradation"
        )
        return f"Image quality issues detected: {issues_str} (score: {self.quality_score:.0f}/100)"


async def load_brisque_model(model_path: str) -> Any:  # noqa: ARG001
    """Load the BRISQUE metric from pyiqa.

    This function initializes the BRISQUE metric using pyiqa library.
    BRISQUE is CPU-based and requires no GPU memory.

    Args:
        model_path: Ignored for pyiqa (uses built-in metric)

    Returns:
        Dictionary containing:
            - metric: The pyiqa BRISQUE metric instance

    Raises:
        ImportError: If pyiqa is not installed
        RuntimeError: If metric initialization fails
    """
    try:
        import pyiqa

        logger.info("Loading BRISQUE quality metric from pyiqa")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            # Create BRISQUE metric (CPU-based)
            # pyiqa supports various metrics; brisque is widely used for no-reference IQA
            metric = pyiqa.create_metric("brisque", device="cpu")

            logger.info("BRISQUE metric initialized on CPU")
            return {"metric": metric}

        result = await loop.run_in_executor(None, _load)

        logger.info("Successfully loaded BRISQUE quality metric")
        return result

    except ImportError as e:
        logger.warning("pyiqa package not installed. Install with: pip install pyiqa")
        raise ImportError(
            "pyiqa package required for image quality assessment. Install with: pip install pyiqa"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load BRISQUE metric: {e}")
        raise RuntimeError(f"Failed to load BRISQUE metric: {e}") from e


async def assess_image_quality(
    model_data: dict[str, Any],
    image: Image.Image,
    blur_threshold: float = BRISQUE_BLUR_THRESHOLD,
    noise_threshold: float = BRISQUE_NOISE_THRESHOLD,
    low_quality_threshold: float = BRISQUE_LOW_QUALITY_THRESHOLD,
) -> ImageQualityResult:
    """Assess the quality of an image using BRISQUE.

    BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator) computes
    a no-reference quality score based on natural scene statistics.

    Lower BRISQUE scores indicate better quality:
    - 0-20: Excellent quality
    - 20-40: Good quality
    - 40-60: Fair quality (some degradation visible)
    - 60-80: Poor quality (significant degradation)
    - 80+: Very poor quality

    The output quality_score is inverted (100 - brisque) so higher = better.

    Args:
        model_data: Dictionary containing 'metric' from load_brisque_model
        image: PIL Image to assess
        blur_threshold: BRISQUE score above which image is considered blurry
        noise_threshold: BRISQUE score above which image is considered noisy
        low_quality_threshold: BRISQUE score above which image is low quality

    Returns:
        ImageQualityResult with quality assessment

    Raises:
        RuntimeError: If quality assessment fails
    """
    try:
        import torch
        from torchvision import transforms

        metric = model_data["metric"]

        loop = asyncio.get_event_loop()

        def _assess() -> ImageQualityResult:
            # Convert PIL Image to tensor
            # pyiqa expects tensor in [0, 1] range, shape [B, C, H, W]
            transform = transforms.Compose(
                [
                    transforms.ToTensor(),
                ]
            )

            # Ensure RGB mode
            rgb_image = image.convert("RGB") if image.mode != "RGB" else image

            img_tensor = transform(rgb_image).unsqueeze(0)  # Add batch dimension

            # Compute BRISQUE score
            with torch.no_grad():
                brisque_score = metric(img_tensor).item()

            # Clamp BRISQUE score to reasonable range
            # BRISQUE typically ranges 0-100 but can exceed in extreme cases
            brisque_score = max(0.0, min(100.0, brisque_score))

            # Invert to get quality score (higher = better)
            quality_score = 100.0 - brisque_score

            # Detect quality issues
            quality_issues: list[str] = []

            # BRISQUE doesn't directly distinguish blur vs noise, but high scores
            # often indicate blur (common in motion blur scenarios)
            is_blurry = brisque_score >= blur_threshold
            is_noisy = brisque_score >= noise_threshold
            is_low_quality = brisque_score >= low_quality_threshold

            if is_blurry:
                quality_issues.append("blur detected")
            if is_noisy and brisque_score >= noise_threshold:
                quality_issues.append("noise/artifacts detected")
            if is_low_quality and not is_blurry and not is_noisy:
                quality_issues.append("general quality degradation")

            return ImageQualityResult(
                quality_score=quality_score,
                brisque_score=brisque_score,
                is_blurry=is_blurry,
                is_noisy=is_noisy,
                is_low_quality=is_low_quality,
                quality_issues=quality_issues,
            )

        return await loop.run_in_executor(None, _assess)

    except ImportError as e:
        logger.error("torch/torchvision required for image quality assessment")
        raise RuntimeError("torch and torchvision required for image quality assessment") from e

    except Exception as e:
        logger.error(f"Image quality assessment failed: {e}")
        raise RuntimeError(f"Image quality assessment failed: {e}") from e


def detect_quality_change(
    current_quality: ImageQualityResult,
    previous_quality: ImageQualityResult | None,
    drop_threshold: float = 30.0,
) -> tuple[bool, str]:
    """Detect sudden quality changes between frames.

    Used to identify potential camera obstruction or tampering when
    quality drops significantly between frames.

    Args:
        current_quality: Current frame quality assessment
        previous_quality: Previous frame quality assessment (None if first frame)
        drop_threshold: Quality score drop that triggers alert

    Returns:
        Tuple of (change_detected: bool, description: str)
    """
    if previous_quality is None:
        return False, "First frame, no comparison available"

    quality_drop = previous_quality.quality_score - current_quality.quality_score

    if quality_drop >= drop_threshold:
        return True, (
            f"Sudden quality drop detected: {previous_quality.quality_score:.0f} -> "
            f"{current_quality.quality_score:.0f} (drop: {quality_drop:.0f}). "
            "Possible camera obstruction or tampering."
        )

    return False, "Quality stable"


def interpret_blur_with_motion(
    quality_result: ImageQualityResult,
    has_person: bool,
    person_speed_estimate: str | None = None,
) -> str:
    """Interpret blur in context of detected motion.

    High blur + person detection may indicate fast movement (running).

    Args:
        quality_result: Image quality assessment result
        has_person: Whether a person was detected in the frame
        person_speed_estimate: Optional speed estimate ("slow", "medium", "fast")

    Returns:
        Interpretation string for LLM context
    """
    if not quality_result.is_blurry:
        return "Clear image, no motion blur"

    if has_person:
        if person_speed_estimate == "fast":
            return (
                "Significant motion blur detected with person - indicates fast movement "
                "(possibly running). BRISQUE score suggests rapid motion capture."
            )
        else:
            return (
                "Motion blur detected with person in frame - may indicate movement. "
                "Consider checking for running or quick movements."
            )

    return (
        "Image blur detected without clear motion source. "
        "May indicate camera issue, obstruction, or environmental factor."
    )
