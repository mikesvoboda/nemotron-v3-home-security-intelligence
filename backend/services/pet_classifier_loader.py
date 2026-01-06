"""Pet classifier model loader for false positive reduction.

This module provides async loading and inference for the ResNet-18 Cat/Dog classifier
(hilmansw/resnet18-catdog-classifier from HuggingFace).

The model performs binary classification to distinguish between cats and dogs,
enabling false positive reduction for pet-only security events.

VRAM Usage: ~200MB
Model: ResNet-18 fine-tuned on cat/dog classification
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)


# Pet type labels (from model config)
PET_LABELS = ["cat", "dog"]


@dataclass(slots=True)
class PetClassificationResult:
    """Result from pet classification.

    Attributes:
        animal_type: Classified animal type ("cat" or "dog")
        confidence: Classification confidence (0-1)
        cat_score: Raw score for cat class (0-1)
        dog_score: Raw score for dog class (0-1)
        is_household_pet: Always True for this classifier (useful for false positive logic)
    """

    animal_type: str
    confidence: float
    cat_score: float
    dog_score: float
    is_household_pet: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "animal_type": self.animal_type,
            "confidence": self.confidence,
            "cat_score": self.cat_score,
            "dog_score": self.dog_score,
            "is_household_pet": self.is_household_pet,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable pet classification for Nemotron context
        """
        conf_str = f"{self.confidence:.0%}"
        return f"Household pet detected: {self.animal_type} ({conf_str} confidence)"


async def load_pet_classifier_model(model_path: str) -> Any:
    """Load the ResNet-18 pet classifier model from local path.

    This function loads the pet classifier model for cat/dog binary
    classification using transformers AutoModelForImageClassification.

    Args:
        model_path: Local path to model directory
                   (e.g., "/export/ai_models/model-zoo/pet-classifier")

    Returns:
        Dictionary containing:
            - model: The ResNet-18 model instance
            - processor: The image processor for preprocessing

    Raises:
        ImportError: If transformers is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info(f"Loading pet classifier model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            processor = AutoImageProcessor.from_pretrained(model_path)
            model = AutoModelForImageClassification.from_pretrained(model_path)

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.cuda().half()  # Use fp16 for efficiency
                logger.info("Pet classifier model moved to CUDA with fp16")
            else:
                logger.info("Pet classifier model using CPU")

            # Set to eval mode
            model.eval()

            return {"model": model, "processor": processor}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded pet classifier model from {model_path}")
        return result

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "Pet classifier requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load pet classifier model", exc_info=True, extra={"model_path": model_path}
        )
        raise RuntimeError(f"Failed to load pet classifier model: {e}") from e


async def classify_pet(
    model_dict: dict[str, Any],
    image: Image.Image,
) -> PetClassificationResult:
    """Classify whether an image contains a cat or dog.

    Args:
        model_dict: Dictionary with 'model' and 'processor' keys from load_pet_classifier_model
        image: PIL Image (typically a cropped animal detection from RT-DETRv2)

    Returns:
        PetClassificationResult with animal type and confidence

    Raises:
        RuntimeError: If classification fails
    """
    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]

        loop = asyncio.get_event_loop()

        def _classify() -> PetClassificationResult:
            """Run classification synchronously."""
            # Preprocess image
            inputs = processor(images=image, return_tensors="pt")

            # Move to same device and dtype as model
            if next(model.parameters()).is_cuda:
                model_dtype = next(model.parameters()).dtype
                inputs = {k: v.cuda().to(model_dtype) for k, v in inputs.items()}

            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits

            # Get probabilities via softmax
            probs = torch.nn.functional.softmax(logits, dim=-1)[0]

            # Get predicted class
            pred_idx = int(probs.argmax().item())
            confidence = probs[pred_idx].item()

            # Map to labels based on model's id2label config
            if hasattr(model.config, "id2label") and model.config.id2label:
                raw_label = model.config.id2label.get(str(pred_idx), PET_LABELS[pred_idx])
                # Normalize "cats" -> "cat", "dogs" -> "dog"
                if raw_label.endswith("s"):
                    raw_label = raw_label[:-1]
            else:
                raw_label = PET_LABELS[pred_idx]

            # Extract scores
            cat_score = probs[0].item()  # Index 0 = cats
            dog_score = probs[1].item()  # Index 1 = dogs

            return PetClassificationResult(
                animal_type=raw_label,
                confidence=confidence,
                cat_score=cat_score,
                dog_score=dog_score,
                is_household_pet=True,
            )

        return await loop.run_in_executor(None, _classify)

    except Exception as e:
        logger.error("Pet classification failed", exc_info=True)
        raise RuntimeError(f"Pet classification failed: {e}") from e


def is_likely_pet_false_positive(
    pet_result: PetClassificationResult | None,
    confidence_threshold: float = 0.85,
) -> bool:
    """Check if detection is likely a pet false positive.

    This function helps reduce false positives by determining if an
    animal detection is confidently classified as a household pet.

    High-confidence pet classifications can skip Nemotron risk analysis
    since pets rarely pose security threats.

    Args:
        pet_result: PetClassificationResult from classify_pet, or None
        confidence_threshold: Minimum confidence to consider as definite pet
                             (default 0.85 = 85%)

    Returns:
        True if detection is a high-confidence household pet (likely false positive)
        False if classification is uncertain or result is None
    """
    if pet_result is None:
        return False

    return pet_result.is_household_pet and pet_result.confidence >= confidence_threshold


def format_pet_for_nemotron(pet_result: PetClassificationResult | None) -> str:
    """Format pet classification for Nemotron context.

    Creates a human-readable description of pet classification that can be
    appended to Nemotron's input context for risk analysis.

    Args:
        pet_result: PetClassificationResult from classify_pet, or None

    Returns:
        Formatted string describing pet classification

    Example output:
        "Pet classification: dog (92% confidence) - household pet, low security risk"
    """
    if pet_result is None:
        return "Pet classification: unknown (classification unavailable)"

    animal = pet_result.animal_type
    confidence = pet_result.confidence

    if pet_result.is_household_pet and confidence >= 0.85:
        risk_note = "household pet, low security risk"
    elif pet_result.is_household_pet and confidence >= 0.70:
        risk_note = "likely household pet, minimal security concern"
    else:
        risk_note = "uncertain classification, evaluate as potential wildlife"

    return f"Pet classification: {animal} ({confidence:.0%} confidence) - {risk_note}"
