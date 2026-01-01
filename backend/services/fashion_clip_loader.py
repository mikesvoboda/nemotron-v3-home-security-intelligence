"""FashionCLIP model loader for zero-shot clothing classification.

This module provides async loading and classification functions for the
Marqo-FashionCLIP model, which is optimized for fashion/clothing recognition.

The model uses CLIP-style zero-shot classification with text prompts to
identify clothing attributes relevant to security surveillance:
- Suspicious attire (dark hoodie, face mask, gloves)
- Service uniforms (delivery, utility, high-visibility)
- General clothing categories (casual, business attire)

VRAM Budget: ~500MB
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL.Image import Image

logger = get_logger(__name__)

# Security-focused clothing classification prompts
# Higher confidence matches provide context for risk assessment
SECURITY_CLOTHING_PROMPTS: list[str] = [
    # Potentially suspicious attire
    "person wearing dark hoodie",
    "person wearing face mask",
    "person wearing ski mask or balaclava",
    "person wearing gloves",
    "person wearing all black clothing",
    "person with obscured face",
    # Delivery and service uniforms
    "delivery uniform",
    "Amazon delivery vest",
    "FedEx uniform",
    "UPS uniform",
    "USPS postal worker uniform",
    "high-visibility vest or safety vest",
    "utility worker uniform",
    "maintenance worker clothing",
    # General clothing categories
    "casual clothing",
    "business attire or suit",
    "athletic wear or sportswear",
    "outdoor or hiking clothing",
    "winter coat or jacket",
    "rain jacket or raincoat",
]

# Suspicious clothing categories that may warrant higher attention
SUSPICIOUS_CATEGORIES: frozenset[str] = frozenset(
    {
        "person wearing dark hoodie",
        "person wearing face mask",
        "person wearing ski mask or balaclava",
        "person wearing gloves",
        "person wearing all black clothing",
        "person with obscured face",
    }
)

# Service/uniform categories that typically reduce risk
SERVICE_CATEGORIES: frozenset[str] = frozenset(
    {
        "delivery uniform",
        "Amazon delivery vest",
        "FedEx uniform",
        "UPS uniform",
        "USPS postal worker uniform",
        "high-visibility vest or safety vest",
        "utility worker uniform",
        "maintenance worker clothing",
    }
)


@dataclass
class ClothingClassification:
    """Result from clothing classification.

    Attributes:
        top_category: Most likely clothing category
        confidence: Confidence score (0-1) for top category
        all_scores: Dictionary of all category scores
        is_suspicious: Whether top category is potentially suspicious
        is_service_uniform: Whether top category indicates service/delivery worker
        raw_description: Human-readable description of detected clothing
    """

    top_category: str
    confidence: float
    all_scores: dict[str, float] = field(default_factory=dict)
    is_suspicious: bool = False
    is_service_uniform: bool = False
    raw_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "top_category": self.top_category,
            "confidence": self.confidence,
            "is_suspicious": self.is_suspicious,
            "is_service_uniform": self.is_service_uniform,
            "description": self.raw_description,
            "all_scores": self.all_scores,
        }


async def load_fashion_clip_model(model_path: str) -> Any:
    """Load Marqo-FashionCLIP model from local path or HuggingFace.

    This function loads the FashionCLIP model using the transformers library.
    The model is optimized for fashion/clothing recognition and uses CLIP
    architecture for zero-shot classification.

    Args:
        model_path: Path to local model directory or HuggingFace model path
                   (e.g., "/export/ai_models/model-zoo/fashion-clip" or
                    "Marqo/marqo-fashionCLIP")

    Returns:
        Dictionary containing:
            - model: The FashionCLIP model instance
            - processor: The processor for image/text preprocessing

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import AutoModel, AutoProcessor

        logger.info(f"Loading FashionCLIP model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            """Load model and processor synchronously."""
            processor = AutoProcessor.from_pretrained(
                model_path,
                trust_remote_code=True,
            )
            model = AutoModel.from_pretrained(
                model_path,
                trust_remote_code=True,
            )

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.cuda()
                logger.info("FashionCLIP model moved to CUDA")

            model.eval()

            return {"model": model, "processor": processor}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded FashionCLIP model from {model_path}")
        return result

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "FashionCLIP requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load FashionCLIP model from {model_path}: {e}")
        raise RuntimeError(f"Failed to load FashionCLIP model: {e}") from e


async def classify_clothing(
    model_dict: dict[str, Any],
    image: Image,
    prompts: list[str] | None = None,
    top_k: int = 3,
) -> ClothingClassification:
    """Classify clothing in a person crop using zero-shot classification.

    Uses CLIP-style text-image similarity to classify clothing from a set
    of predefined security-relevant prompts.

    Args:
        model_dict: Dictionary containing model and processor from load_fashion_clip_model
        image: PIL Image of person crop (should be cropped to person bounding box)
        prompts: List of text prompts for classification. Defaults to SECURITY_CLOTHING_PROMPTS
        top_k: Number of top categories to include in all_scores

    Returns:
        ClothingClassification with top category, confidence, and metadata

    Raises:
        RuntimeError: If classification fails
    """
    if prompts is None:
        prompts = SECURITY_CLOTHING_PROMPTS

    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]

        loop = asyncio.get_event_loop()

        def _classify() -> ClothingClassification:
            """Run classification synchronously."""
            # Process image and text prompts
            processed = processor(
                text=prompts,
                images=[image],
                padding="max_length",
                return_tensors="pt",
            )

            # Move to same device as model
            device = next(model.parameters()).device
            processed = {k: v.to(device) for k, v in processed.items()}

            # Get image and text features
            with torch.no_grad():
                image_features = model.get_image_features(processed["pixel_values"], normalize=True)
                text_features = model.get_text_features(processed["input_ids"], normalize=True)

                # Compute similarity scores
                similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                scores = similarity[0].cpu().numpy()

            # Create score dictionary
            all_scores = {
                prompt: float(score) for prompt, score in zip(prompts, scores, strict=True)
            }

            # Sort by score and get top result
            sorted_items = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
            top_category = sorted_items[0][0]
            top_confidence = sorted_items[0][1]

            # Keep only top_k scores
            top_k_scores = dict(sorted_items[:top_k])

            # Determine classification flags
            is_suspicious = top_category in SUSPICIOUS_CATEGORIES
            is_service = top_category in SERVICE_CATEGORIES

            # Generate human-readable description
            if is_service:
                description = f"Service worker: {top_category.replace('person wearing ', '')}"
            elif is_suspicious:
                description = f"Alert: {top_category.replace('person wearing ', '')}"
            else:
                description = top_category.replace("person wearing ", "").capitalize()

            return ClothingClassification(
                top_category=top_category,
                confidence=top_confidence,
                all_scores=top_k_scores,
                is_suspicious=is_suspicious,
                is_service_uniform=is_service,
                raw_description=description,
            )

        return await loop.run_in_executor(None, _classify)

    except Exception as e:
        logger.error(f"Clothing classification failed: {e}")
        raise RuntimeError(f"Clothing classification failed: {e}") from e


async def classify_clothing_batch(
    model_dict: dict[str, Any],
    images: list[Image],
    prompts: list[str] | None = None,
    top_k: int = 3,
) -> list[ClothingClassification]:
    """Classify clothing in multiple person crops.

    Batch processes multiple person crops for efficiency.

    Args:
        model_dict: Dictionary containing model and processor from load_fashion_clip_model
        images: List of PIL Images (person crops)
        prompts: List of text prompts for classification. Defaults to SECURITY_CLOTHING_PROMPTS
        top_k: Number of top categories to include in all_scores

    Returns:
        List of ClothingClassification results, one per input image
    """
    if not images:
        return []

    if prompts is None:
        prompts = SECURITY_CLOTHING_PROMPTS

    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]

        loop = asyncio.get_event_loop()

        def _classify_batch() -> list[ClothingClassification]:
            """Run batch classification synchronously."""
            # Process all images and text prompts
            processed = processor(
                text=prompts,
                images=images,
                padding="max_length",
                return_tensors="pt",
            )

            # Move to same device as model
            device = next(model.parameters()).device
            processed = {k: v.to(device) for k, v in processed.items()}

            # Get text features (same for all images)
            with torch.no_grad():
                text_features = model.get_text_features(processed["input_ids"], normalize=True)

                # Get image features for all images
                image_features = model.get_image_features(processed["pixel_values"], normalize=True)

                # Compute similarity scores for all images: [num_images, num_prompts]
                similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                all_batch_scores = similarity.cpu().numpy()

            results = []
            for _i, scores in enumerate(all_batch_scores):
                # Create score dictionary for this image
                all_scores = {
                    prompt: float(score) for prompt, score in zip(prompts, scores, strict=True)
                }

                # Sort by score and get top result
                sorted_items = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
                top_category = sorted_items[0][0]
                top_confidence = sorted_items[0][1]

                # Keep only top_k scores
                top_k_scores = dict(sorted_items[:top_k])

                # Determine classification flags
                is_suspicious = top_category in SUSPICIOUS_CATEGORIES
                is_service = top_category in SERVICE_CATEGORIES

                # Generate human-readable description
                if is_service:
                    description = f"Service worker: {top_category.replace('person wearing ', '')}"
                elif is_suspicious:
                    description = f"Alert: {top_category.replace('person wearing ', '')}"
                else:
                    description = top_category.replace("person wearing ", "").capitalize()

                results.append(
                    ClothingClassification(
                        top_category=top_category,
                        confidence=top_confidence,
                        all_scores=top_k_scores,
                        is_suspicious=is_suspicious,
                        is_service_uniform=is_service,
                        raw_description=description,
                    )
                )

            return results

        return await loop.run_in_executor(None, _classify_batch)

    except Exception as e:
        logger.error(f"Batch clothing classification failed: {e}")
        raise RuntimeError(f"Batch clothing classification failed: {e}") from e


def format_clothing_context(classification: ClothingClassification) -> str:
    """Format clothing classification as context string for LLM prompt.

    Args:
        classification: ClothingClassification result

    Returns:
        Formatted string for inclusion in risk analysis prompt
    """
    lines = [f"Clothing: {classification.raw_description}"]

    if classification.is_suspicious:
        lines.append("  [ALERT: Potentially suspicious attire detected]")
    elif classification.is_service_uniform:
        lines.append("  [Service/delivery worker uniform detected]")

    lines.append(f"  Confidence: {classification.confidence:.1%}")

    # Add top alternative if confidence is low
    if classification.confidence < 0.5 and len(classification.all_scores) > 1:
        sorted_scores = sorted(classification.all_scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) > 1:
            alt_cat, alt_score = sorted_scores[1]
            lines.append(f"  Alternative: {alt_cat} ({alt_score:.1%})")

    return "\n".join(lines)
