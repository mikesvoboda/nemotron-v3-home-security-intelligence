"""ViT age classifier model loader.

This module provides async loading and inference for the ViT-based age
classification model, which estimates age ranges from face or person crops.

The model classifies individuals into age groups, enabling better person
descriptions for security context.

Model details:
- Architecture: Vision Transformer (ViT)
- Input: Face crops or person images
- Output: Age group classification with confidence
- VRAM: ~200MB
- Classes: Age ranges (child, teenager, young_adult, adult, middle_aged, senior)

Usage in security context:
- Provides age estimates for person descriptions
- Helps differentiate between adult intruders and lost children
- Supports generating detailed person descriptions for reports
- Combined with gender for comprehensive person profiling
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Age group labels (may vary by model)
# Common age classification schemes
AGE_GROUPS: list[str] = [
    "child",  # 0-12
    "teenager",  # 13-19
    "young_adult",  # 20-35
    "adult",  # 36-50
    "middle_aged",  # 51-65
    "senior",  # 65+
]

# Alternative age range labels some models may use
AGE_RANGES: dict[str, str] = {
    "0-2": "infant",
    "3-9": "child",
    "10-19": "teenager",
    "20-29": "young_adult",
    "30-39": "adult",
    "40-49": "adult",
    "50-59": "middle_aged",
    "60-69": "senior",
    "70+": "senior",
    "more than 70": "senior",
}

# Display-friendly age descriptions
AGE_DISPLAY_NAMES: dict[str, str] = {
    "infant": "infant (0-2 years)",
    "child": "child (3-12 years)",
    "teenager": "teenager (13-19 years)",
    "young_adult": "young adult (20-35 years)",
    "adult": "adult (36-50 years)",
    "middle_aged": "middle-aged (51-65 years)",
    "senior": "senior (65+ years)",
}


@dataclass(slots=True)
class AgeClassificationResult:
    """Result from age classification.

    Attributes:
        age_group: Classified age group (e.g., "adult", "teenager")
        confidence: Classification confidence (0-1)
        display_name: Human-readable age description
        all_scores: Dictionary of all class scores (top 3)
        is_minor: Whether the person is classified as a minor (child/teenager)
    """

    age_group: str
    confidence: float
    display_name: str
    all_scores: dict[str, float]
    is_minor: bool = False

    def __post_init__(self) -> None:
        """Compute derived fields after initialization."""
        self.is_minor = self.age_group in ("infant", "child", "teenager")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "age_group": self.age_group,
            "confidence": self.confidence,
            "display_name": self.display_name,
            "all_scores": self.all_scores,
            "is_minor": self.is_minor,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable age classification for Nemotron context
        """
        conf_str = f"{self.confidence:.0%}"
        base = f"Estimated age: {self.display_name} ({conf_str} confidence)"
        if self.is_minor:
            base += " [MINOR]"
        return base


async def load_age_classifier_model(model_path: str) -> dict[str, Any]:
    """Load ViT age classifier model from local path.

    This function loads the Vision Transformer-based age classification model.

    Args:
        model_path: Local path to the model directory
                   (e.g., "/models/model-zoo/vit-age-classifier")
                   Should contain the model files.

    Returns:
        Dictionary containing:
            - model: The ViT model instance
            - processor: The image processor for preprocessing
            - labels: List of age labels

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info(f"Loading age classifier model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            """Load model and processor synchronously."""
            model_dir = Path(model_path)

            # Load processor and model from local path
            processor = AutoImageProcessor.from_pretrained(str(model_dir))
            model = AutoModelForImageClassification.from_pretrained(str(model_dir))

            # Extract labels from model config
            labels = []
            if hasattr(model.config, "id2label") and model.config.id2label:
                # id2label is usually {0: "label0", 1: "label1", ...}
                labels = [
                    model.config.id2label.get(str(i), model.config.id2label.get(i, f"age_{i}"))
                    for i in range(len(model.config.id2label))
                ]
            else:
                labels = AGE_GROUPS.copy()

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.cuda().half()  # Use fp16 for efficiency
                logger.info("Age classifier model moved to CUDA with fp16")
            else:
                logger.info("Age classifier model using CPU")

            # Set to eval mode
            model.eval()

            return {
                "model": model,
                "processor": processor,
                "labels": labels,
            }

        result = await loop.run_in_executor(None, _load)

        logger.info(
            f"Successfully loaded age classifier model from {model_path} "
            f"({len(result['labels'])} age groups)"
        )
        return result

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "Age classifier requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load age classifier model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load age classifier model: {e}") from e


async def classify_age(
    model_dict: dict[str, Any],
    image: Image.Image,
) -> AgeClassificationResult:
    """Classify age from an image (face or person crop).

    Args:
        model_dict: Dictionary containing model, processor, and labels
                   from load_age_classifier_model
        image: PIL Image (face crop preferred, but full person crop works)

    Returns:
        AgeClassificationResult with age group and confidence

    Raises:
        RuntimeError: If classification fails
    """
    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]
        labels = model_dict["labels"]

        loop = asyncio.get_event_loop()

        def _classify() -> AgeClassificationResult:
            """Run classification synchronously."""
            # Ensure RGB mode
            rgb_image = image.convert("RGB") if image.mode != "RGB" else image

            # Preprocess image
            inputs = processor(images=rgb_image, return_tensors="pt")

            # Move to same device and dtype as model
            device = next(model.parameters()).device
            dtype = next(model.parameters()).dtype
            inputs = {k: v.to(device=device, dtype=dtype) for k, v in inputs.items()}

            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits

            # Get probabilities via softmax
            probs = torch.nn.functional.softmax(logits, dim=-1)[0]

            # Get all scores
            all_scores = {label: float(probs[i].item()) for i, label in enumerate(labels)}

            # Get top prediction
            pred_idx = int(probs.argmax().item())
            confidence = float(probs[pred_idx].item())
            raw_label = labels[pred_idx]

            # Normalize label to standard age group
            age_group = _normalize_age_label(raw_label)

            # Get display name
            display_name = AGE_DISPLAY_NAMES.get(age_group, age_group)

            # Get top 3 scores
            sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
            top_3_scores = dict(sorted_scores[:3])

            return AgeClassificationResult(
                age_group=age_group,
                confidence=confidence,
                display_name=display_name,
                all_scores=top_3_scores,
            )

        return await loop.run_in_executor(None, _classify)

    except Exception as e:
        logger.error("Age classification failed", exc_info=True)
        raise RuntimeError(f"Age classification failed: {e}") from e


async def classify_ages_batch(
    model_dict: dict[str, Any],
    images: list[Image.Image],
) -> list[AgeClassificationResult]:
    """Classify ages for multiple image crops.

    Batch processes multiple images for efficiency.

    Args:
        model_dict: Dictionary containing model, processor, and labels
        images: List of PIL Images (face or person crops)

    Returns:
        List of AgeClassificationResult, one per input image
    """
    if not images:
        return []

    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]
        labels = model_dict["labels"]

        loop = asyncio.get_event_loop()

        def _classify_batch() -> list[AgeClassificationResult]:
            """Run batch classification synchronously."""
            # Ensure all images are RGB
            rgb_images = [img.convert("RGB") if img.mode != "RGB" else img for img in images]

            # Preprocess all images
            inputs = processor(images=rgb_images, return_tensors="pt", padding=True)

            # Move to same device and dtype as model
            device = next(model.parameters()).device
            dtype = next(model.parameters()).dtype
            inputs = {k: v.to(device=device, dtype=dtype) for k, v in inputs.items()}

            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)
                all_logits = outputs.logits

            # Get probabilities for all images
            all_probs = torch.nn.functional.softmax(all_logits, dim=-1)

            results = []
            for probs in all_probs:
                # Get all scores
                all_scores = {label: float(probs[i].item()) for i, label in enumerate(labels)}

                # Get top prediction
                pred_idx = int(probs.argmax().item())
                confidence = float(probs[pred_idx].item())
                raw_label = labels[pred_idx]

                # Normalize and get display name
                age_group = _normalize_age_label(raw_label)
                display_name = AGE_DISPLAY_NAMES.get(age_group, age_group)

                # Get top 3 scores
                sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
                top_3_scores = dict(sorted_scores[:3])

                results.append(
                    AgeClassificationResult(
                        age_group=age_group,
                        confidence=confidence,
                        display_name=display_name,
                        all_scores=top_3_scores,
                    )
                )

            return results

        return await loop.run_in_executor(None, _classify_batch)

    except Exception as e:
        logger.error("Batch age classification failed", exc_info=True)
        raise RuntimeError(f"Batch age classification failed: {e}") from e


def _normalize_age_label(raw_label: str) -> str:  # noqa: PLR0911, PLR0912
    """Normalize raw age label to standard age group.

    Different models may use different labeling schemes. This function
    normalizes them to our standard age groups.

    Args:
        raw_label: Raw label from model (e.g., "20-29", "adult", "0-2")

    Returns:
        Normalized age group string
    """
    label_lower = raw_label.lower().strip()

    # Check if it's already a standard group
    if label_lower in AGE_DISPLAY_NAMES:
        return label_lower

    # Check if it's an age range format
    if label_lower in AGE_RANGES:
        return AGE_RANGES[label_lower]

    # Try to parse numeric ranges
    if "-" in label_lower:
        try:
            parts = label_lower.split("-")
            start_age = int(parts[0])
            if start_age < 3:
                return "infant"
            elif start_age < 13:
                return "child"
            elif start_age < 20:
                return "teenager"
            elif start_age < 36:
                return "young_adult"
            elif start_age < 51:
                return "adult"
            elif start_age < 66:
                return "middle_aged"
            else:
                return "senior"
        except (ValueError, IndexError):
            pass

    # Check for keyword matches
    if "child" in label_lower or "kid" in label_lower:
        return "child"
    elif "teen" in label_lower or "adolesc" in label_lower:
        return "teenager"
    elif "young" in label_lower:
        return "young_adult"
    elif "middle" in label_lower:
        return "middle_aged"
    elif "senior" in label_lower or "elder" in label_lower or "old" in label_lower:
        return "senior"
    elif "adult" in label_lower:
        return "adult"
    elif "infant" in label_lower or "baby" in label_lower:
        return "infant"

    # Default to adult if unknown
    return "adult"


def format_age_context(
    age_result: AgeClassificationResult | None,
    detection_id: str | None = None,
) -> str:
    """Format age classification for prompt context.

    Args:
        age_result: AgeClassificationResult from classify_age, or None
        detection_id: Optional detection identifier

    Returns:
        Formatted string for inclusion in risk analysis prompt
    """
    if age_result is None:
        return "Age estimation: Not available"

    prefix = f"Person {detection_id}: " if detection_id else ""
    lines = [f"{prefix}Age: {age_result.display_name} ({age_result.confidence:.0%})"]

    if age_result.is_minor:
        lines.append("  **NOTE**: Minor detected - may indicate lost child if unaccompanied")

    # Add confidence qualifier
    if age_result.confidence < 0.5:
        lines.append("  (Low confidence - age estimate may be unreliable)")
    elif age_result.confidence < 0.7:
        lines.append("  (Medium confidence)")

    return "\n".join(lines)
