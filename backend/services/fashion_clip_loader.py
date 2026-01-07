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


@dataclass(slots=True)
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

    This function loads the FashionCLIP model using open_clip library directly.
    The model is optimized for fashion/clothing recognition and uses CLIP
    architecture for zero-shot classification.

    Note: We use open_clip directly instead of transformers.AutoModel because
    the Marqo-FashionCLIP custom model wrapper has meta tensor issues when
    loaded via transformers that cause "Cannot copy out of meta tensor" errors.

    Args:
        model_path: Path to local model directory or HuggingFace model path.
                   For local paths (e.g., "/export/ai_models/model-zoo/fashion-clip"),
                   the model files should be in open_clip format.
                   For HuggingFace paths (e.g., "Marqo/marqo-fashionCLIP"),
                   use "hf-hub:" prefix.

    Returns:
        Dictionary containing:
            - model: The FashionCLIP model instance
            - preprocess: The image preprocessing transform
            - tokenizer: The text tokenizer

    Raises:
        ImportError: If open_clip_torch or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from open_clip import create_model_from_pretrained, get_tokenizer

        logger.info(f"Loading FashionCLIP model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            """Load model, preprocess, and tokenizer synchronously."""
            # Convert path to HuggingFace hub format if needed
            # Local paths should be converted to hf-hub format for open_clip
            if model_path.startswith("/") or model_path.startswith("./"):
                # Local path - use hf-hub format with Marqo model
                # This assumes the local path contains a copy of the model,
                # but open_clip needs the hf-hub format for Marqo models
                hub_path = "hf-hub:Marqo/marqo-fashionCLIP"
                logger.info(f"Local path {model_path} detected, using HuggingFace hub: {hub_path}")
            elif "/" in model_path and not model_path.startswith("hf-hub:"):
                # HuggingFace model ID without prefix
                hub_path = f"hf-hub:{model_path}"
            else:
                hub_path = model_path

            # Load model and preprocess using open_clip
            model, preprocess = create_model_from_pretrained(hub_path)
            tokenizer = get_tokenizer(hub_path)

            # Determine target device and move model
            target_device = "cuda" if torch.cuda.is_available() else "cpu"
            if target_device == "cuda":
                model = model.cuda()
            logger.info(f"FashionCLIP model loaded on {target_device}")

            model.eval()

            return {"model": model, "preprocess": preprocess, "tokenizer": tokenizer}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded FashionCLIP model from {model_path}")
        return result

    except ImportError as e:
        logger.warning(
            "open_clip_torch or torch package not installed. "
            "Install with: pip install open_clip_torch torch"
        )
        raise ImportError(
            "FashionCLIP requires open_clip_torch and torch. "
            "Install with: pip install open_clip_torch torch"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load FashionCLIP model", exc_info=True, extra={"model_path": model_path}
        )
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
        model_dict: Dictionary containing model, preprocess, and tokenizer
                   from load_fashion_clip_model
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
        preprocess = model_dict["preprocess"]
        tokenizer = model_dict["tokenizer"]

        loop = asyncio.get_event_loop()

        def _classify() -> ClothingClassification:
            """Run classification synchronously."""
            # Get device from model
            device = next(model.parameters()).device

            # Process image using open_clip preprocess
            image_tensor = preprocess(image).unsqueeze(0).to(device)

            # Tokenize text prompts
            text_tokens = tokenizer(prompts).to(device)

            # Get image and text features
            with torch.no_grad():
                image_features = model.encode_image(image_tensor)
                text_features = model.encode_text(text_tokens)

                # Normalize features
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

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
        logger.error("Clothing classification failed", exc_info=True)
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
        model_dict: Dictionary containing model, preprocess, and tokenizer
                   from load_fashion_clip_model
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
        preprocess = model_dict["preprocess"]
        tokenizer = model_dict["tokenizer"]

        loop = asyncio.get_event_loop()

        def _classify_batch() -> list[ClothingClassification]:
            """Run batch classification synchronously."""
            # Get device from model
            device = next(model.parameters()).device

            # Process all images using open_clip preprocess and stack into batch
            image_tensors = torch.stack([preprocess(img) for img in images]).to(device)

            # Tokenize text prompts (same for all images)
            text_tokens = tokenizer(prompts).to(device)

            # Get text and image features
            with torch.no_grad():
                text_features = model.encode_text(text_tokens)
                image_features = model.encode_image(image_tensors)

                # Normalize features
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)

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
        logger.error("Batch clothing classification failed", exc_info=True)
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
