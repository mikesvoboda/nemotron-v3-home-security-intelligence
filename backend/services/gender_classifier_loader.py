"""ViT gender classifier model loader.

This module provides async loading and inference for the ViT-based gender
classification model, which classifies individuals as male or female from
face or person crops.

The model performs binary classification to assist with person descriptions
for security context.

Model details:
- Architecture: Vision Transformer (ViT)
- Input: Face crops or person images
- Output: Gender classification (male/female) with confidence
- VRAM: ~200MB
- Classes: male, female

Usage in security context:
- Provides gender for person descriptions in security reports
- Supports generating comprehensive person profiles
- Combined with age for detailed person characterization
- Helps match person descriptions to suspect reports
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

# Gender labels
GENDER_LABELS: list[str] = ["male", "female"]


@dataclass(slots=True)
class GenderClassificationResult:
    """Result from gender classification.

    Attributes:
        gender: Classified gender ("male" or "female")
        confidence: Classification confidence (0-1)
        male_score: Raw score for male class (0-1)
        female_score: Raw score for female class (0-1)
    """

    gender: str
    confidence: float
    male_score: float
    female_score: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "gender": self.gender,
            "confidence": self.confidence,
            "male_score": self.male_score,
            "female_score": self.female_score,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable gender classification for Nemotron context
        """
        return f"Gender: {self.gender} ({self.confidence:.0%} confidence)"


async def load_gender_classifier_model(model_path: str) -> dict[str, Any]:
    """Load ViT gender classifier model from local path.

    This function loads the Vision Transformer-based gender classification model.

    Args:
        model_path: Local path to the model directory
                   (e.g., "/models/model-zoo/vit-gender-classifier")
                   Should contain the model files.

    Returns:
        Dictionary containing:
            - model: The ViT model instance
            - processor: The image processor for preprocessing
            - labels: List of gender labels

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info(f"Loading gender classifier model from {model_path}")

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
                    model.config.id2label.get(str(i), model.config.id2label.get(i, f"gender_{i}"))
                    for i in range(len(model.config.id2label))
                ]
                # Normalize labels to lowercase
                labels = [label.lower() for label in labels]
            else:
                labels = GENDER_LABELS.copy()

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.cuda().half()  # Use fp16 for efficiency
                logger.info("Gender classifier model moved to CUDA with fp16")
            else:
                logger.info("Gender classifier model using CPU")

            # Set to eval mode
            model.eval()

            return {
                "model": model,
                "processor": processor,
                "labels": labels,
            }

        result = await loop.run_in_executor(None, _load)

        logger.info(
            f"Successfully loaded gender classifier model from {model_path} "
            f"(labels: {result['labels']})"
        )
        return result

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "Gender classifier requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load gender classifier model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load gender classifier model: {e}") from e


async def classify_gender(
    model_dict: dict[str, Any],
    image: Image.Image,
) -> GenderClassificationResult:
    """Classify gender from an image (face or person crop).

    Args:
        model_dict: Dictionary containing model, processor, and labels
                   from load_gender_classifier_model
        image: PIL Image (face crop preferred, but full person crop works)

    Returns:
        GenderClassificationResult with gender and confidence

    Raises:
        RuntimeError: If classification fails
    """
    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]
        labels = model_dict["labels"]

        loop = asyncio.get_event_loop()

        def _classify() -> GenderClassificationResult:
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

            # Get predicted class
            pred_idx = int(probs.argmax().item())
            confidence = float(probs[pred_idx].item())
            gender = labels[pred_idx] if pred_idx < len(labels) else "unknown"

            # Normalize gender label
            gender = _normalize_gender_label(gender)

            # Get male/female scores
            male_idx = _find_label_index(labels, "male")
            female_idx = _find_label_index(labels, "female")

            male_score = float(probs[male_idx].item()) if male_idx is not None else 0.0
            female_score = float(probs[female_idx].item()) if female_idx is not None else 0.0

            # If indices not found, infer from binary classification
            if male_idx is None and female_idx is None and len(probs) == 2:
                # Assume index 0 = male, index 1 = female (common convention)
                male_score = float(probs[0].item())
                female_score = float(probs[1].item())

            return GenderClassificationResult(
                gender=gender,
                confidence=confidence,
                male_score=male_score,
                female_score=female_score,
            )

        return await loop.run_in_executor(None, _classify)

    except Exception as e:
        logger.error("Gender classification failed", exc_info=True)
        raise RuntimeError(f"Gender classification failed: {e}") from e


async def classify_genders_batch(
    model_dict: dict[str, Any],
    images: list[Image.Image],
) -> list[GenderClassificationResult]:
    """Classify genders for multiple image crops.

    Batch processes multiple images for efficiency.

    Args:
        model_dict: Dictionary containing model, processor, and labels
        images: List of PIL Images (face or person crops)

    Returns:
        List of GenderClassificationResult, one per input image
    """
    if not images:
        return []

    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]
        labels = model_dict["labels"]

        loop = asyncio.get_event_loop()

        def _classify_batch() -> list[GenderClassificationResult]:
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

            # Find male/female indices once
            male_idx = _find_label_index(labels, "male")
            female_idx = _find_label_index(labels, "female")

            results = []
            for probs in all_probs:
                # Get predicted class
                pred_idx = int(probs.argmax().item())
                confidence = float(probs[pred_idx].item())
                gender = labels[pred_idx] if pred_idx < len(labels) else "unknown"
                gender = _normalize_gender_label(gender)

                # Get scores
                if male_idx is not None:
                    male_score = float(probs[male_idx].item())
                else:
                    male_score = float(probs[0].item()) if len(probs) >= 2 else 0.0

                if female_idx is not None:
                    female_score = float(probs[female_idx].item())
                else:
                    female_score = float(probs[1].item()) if len(probs) >= 2 else 0.0

                results.append(
                    GenderClassificationResult(
                        gender=gender,
                        confidence=confidence,
                        male_score=male_score,
                        female_score=female_score,
                    )
                )

            return results

        return await loop.run_in_executor(None, _classify_batch)

    except Exception as e:
        logger.error("Batch gender classification failed", exc_info=True)
        raise RuntimeError(f"Batch gender classification failed: {e}") from e


def _normalize_gender_label(raw_label: str) -> str:
    """Normalize raw gender label to standard format.

    Args:
        raw_label: Raw label from model (e.g., "Male", "FEMALE", "man")

    Returns:
        Normalized gender string ("male" or "female")
    """
    label_lower = raw_label.lower().strip()

    if label_lower in ("male", "man", "boy", "m"):
        return "male"
    elif label_lower in ("female", "woman", "girl", "f"):
        return "female"
    else:
        # Default to the raw label if unrecognized
        return label_lower


def _find_label_index(labels: list[str], target: str) -> int | None:
    """Find index of a target label in label list.

    Args:
        labels: List of label strings
        target: Target label to find

    Returns:
        Index of target label, or None if not found
    """
    target_lower = target.lower()
    for i, label in enumerate(labels):
        if label.lower() == target_lower:
            return i
        # Also check for partial matches
        if target_lower in label.lower():
            return i
    return None


def format_gender_context(
    gender_result: GenderClassificationResult | None,
    detection_id: str | None = None,
) -> str:
    """Format gender classification for prompt context.

    Args:
        gender_result: GenderClassificationResult from classify_gender, or None
        detection_id: Optional detection identifier

    Returns:
        Formatted string for inclusion in risk analysis prompt
    """
    if gender_result is None:
        return "Gender estimation: Not available"

    prefix = f"Person {detection_id}: " if detection_id else ""
    line = f"{prefix}Gender: {gender_result.gender} ({gender_result.confidence:.0%})"

    # Add confidence qualifier
    if gender_result.confidence < 0.6:
        line += " [low confidence]"

    return line


def format_person_demographics_context(
    age_result: Any | None,
    gender_result: GenderClassificationResult | None,
    detection_id: str | None = None,
) -> str:
    """Format combined age and gender for prompt context.

    Args:
        age_result: AgeClassificationResult from age classifier, or None
        gender_result: GenderClassificationResult from gender classifier, or None
        detection_id: Optional detection identifier

    Returns:
        Formatted string combining age and gender for prompt context
    """
    prefix = f"Person {detection_id}:" if detection_id else "Person:"
    parts = [prefix]

    if gender_result is not None:
        parts.append(f" {gender_result.gender}")

    if age_result is not None:
        # Get age description
        if hasattr(age_result, "display_name"):
            parts.append(f", {age_result.display_name}")
        elif hasattr(age_result, "age_group"):
            parts.append(f", {age_result.age_group}")

    # Add confidence notes
    notes = []
    if gender_result is not None and gender_result.confidence < 0.6:
        notes.append("gender uncertain")
    if age_result is not None and hasattr(age_result, "confidence") and age_result.confidence < 0.6:
        notes.append("age uncertain")

    if notes:
        parts.append(f" [{', '.join(notes)}]")

    # Add minor note if applicable
    if age_result is not None and hasattr(age_result, "is_minor") and age_result.is_minor:
        parts.append(" [MINOR]")

    return "".join(parts)
