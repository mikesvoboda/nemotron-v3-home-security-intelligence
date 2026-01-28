"""FashionSigLIP model loader for zero-shot clothing classification.

This module provides async loading and classification functions for the
Marqo-FashionSigLIP model, which is optimized for fashion/clothing recognition.

FashionSigLIP provides 57% improvement in accuracy over FashionCLIP:
- Text-to-Image MRR: 0.239 vs 0.165 (FashionCLIP2.0)
- Text-to-Image Recall@1: 0.121 vs 0.077 (FashionCLIP2.0)
- Text-to-Image Recall@10: 0.340 vs 0.249 (FashionCLIP2.0)

The model uses SigLIP-style zero-shot classification with text prompts to
identify clothing attributes relevant to security surveillance:
- Suspicious attire (dark hoodie, face mask, gloves)
- Service uniforms (delivery, utility, high-visibility)
- General clothing categories (casual, business attire)

Model architecture:
- Base: ViT-B-16-SigLIP (webli)
- Training: Generalised Contrastive Learning (GCL)
- Parameters: 0.2B

VRAM Budget: ~500MB (unchanged from FashionCLIP)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL.Image import Image

logger = get_logger(__name__)

# ==============================================================================
# Hierarchical Security Clothing Categories (NEM-3913)
# ==============================================================================
# Clothing prompts organized by risk level with category-specific thresholds.
# This hierarchical structure enables better risk assessment by the LLM.


class ClothingCategoryConfig(TypedDict):
    """Configuration for a clothing category."""

    prompts: list[str]
    threshold: float
    risk_level: str


CLOTHING_PROMPTS_V2: dict[str, ClothingCategoryConfig] = {
    "suspicious": {
        "prompts": [
            # Face/Head Covering
            "person with face completely obscured by hood",
            "person wearing ski mask or balaclava",
            "person wearing dark hood pulled over head",
            "person wearing surgical mask at unusual time",
            "person wearing sunglasses at night",
            # Body Concealment
            "person in all black clothing head to toe",
            "person wearing oversized loose clothing",
            "person wearing long coat or trench coat",
            "person wearing dark gloves",
            "person with hoodie and backpack combination",
            # Legacy prompts for compatibility
            "person wearing dark hoodie",
            "person wearing face mask",
            "person wearing gloves",
            "person wearing all black clothing",
            "person with obscured face",
        ],
        "threshold": 0.25,
        "risk_level": "high",
    },
    "delivery_branded": {
        "prompts": [
            "Amazon delivery driver in blue vest",
            "FedEx worker in purple and orange uniform",
            "UPS driver in brown uniform",
            "USPS mail carrier in blue uniform",
            "DHL courier in yellow and red uniform",
        ],
        "threshold": 0.35,
        "risk_level": "low",
    },
    "delivery_generic": {
        "prompts": [
            "delivery person in high-visibility vest",
            "courier with package and uniform",
            "food delivery worker with insulated bag",
            "pizza delivery person",
            "grocery delivery worker",
            # Legacy prompts for compatibility
            "delivery uniform",
            "Amazon delivery vest",
            "FedEx uniform",
            "UPS uniform",
            "USPS postal worker uniform",
        ],
        "threshold": 0.30,
        "risk_level": "low",
    },
    "utility_service": {
        "prompts": [
            "utility worker in hard hat and safety vest",
            "construction worker in safety gear",
            "maintenance worker in uniform",
            "security guard in uniform",
            "landscaper in work clothes",
            "electrician in work gear",
            "plumber in work clothes",
            "cable technician in uniform",
            # Legacy prompts for compatibility
            "high-visibility vest or safety vest",
            "utility worker uniform",
            "maintenance worker clothing",
        ],
        "threshold": 0.35,
        "risk_level": "low",
    },
    "casual_civilian": {
        "prompts": [
            "person in casual everyday clothing",
            "person in business casual attire",
            "person in athletic or gym wear",
            "person in formal business suit",
            "person wearing jeans and t-shirt",
            "person in shorts and casual shirt",
            # Legacy prompts for compatibility
            "casual clothing",
            "business attire or suit",
            "athletic wear or sportswear",
            "outdoor or hiking clothing",
            "winter coat or jacket",
            "rain jacket or raincoat",
        ],
        "threshold": 0.40,
        "risk_level": "normal",
    },
    "colors": {
        "prompts": [
            "person wearing predominantly red clothing",
            "person wearing predominantly blue clothing",
            "person wearing predominantly black clothing",
            "person wearing predominantly white clothing",
            "person wearing predominantly green clothing",
            "person wearing predominantly gray clothing",
            "person wearing predominantly brown clothing",
            "person wearing predominantly yellow clothing",
            "person wearing predominantly orange clothing",
        ],
        "threshold": 0.35,
        "risk_level": "info",  # Just for identification
    },
}


def get_all_clothing_prompts() -> list[str]:
    """Get flattened list of all clothing prompts from hierarchical categories.

    Returns:
        List of all prompts across all categories.
    """
    return [p for cat in CLOTHING_PROMPTS_V2.values() for p in cat["prompts"]]


def get_clothing_risk_level(matched_prompt: str) -> str:
    """Get risk level for a matched clothing prompt.

    Args:
        matched_prompt: The prompt that was matched.

    Returns:
        Risk level string: "high", "low", "normal", or "info".
    """
    for config in CLOTHING_PROMPTS_V2.values():
        if matched_prompt in config["prompts"]:
            return config["risk_level"]
    return "normal"


def get_clothing_threshold(category: str) -> float:
    """Get confidence threshold for a clothing category.

    Args:
        category: Category name (e.g., "suspicious", "delivery_branded").

    Returns:
        Confidence threshold for the category, or 0.35 as default.
    """
    config = CLOTHING_PROMPTS_V2.get(category)
    if config is None:
        return 0.35
    return config["threshold"]


def get_clothing_category(matched_prompt: str) -> str | None:
    """Get category name for a matched clothing prompt.

    Args:
        matched_prompt: The prompt that was matched.

    Returns:
        Category name or None if not found.
    """
    for category, config in CLOTHING_PROMPTS_V2.items():
        if matched_prompt in config["prompts"]:
            return category
    return None


# ==============================================================================
# Backward Compatibility - Legacy Constants (NEM-3913)
# ==============================================================================
# These constants are maintained for backward compatibility with existing code.
# New code should use the hierarchical CLOTHING_PROMPTS_V2 structure.

# Security-focused clothing classification prompts
# Higher confidence matches provide context for risk assessment
SECURITY_CLOTHING_PROMPTS: list[str] = get_all_clothing_prompts()

# Suspicious clothing categories that may warrant higher attention
SUSPICIOUS_CATEGORIES: frozenset[str] = frozenset(CLOTHING_PROMPTS_V2["suspicious"]["prompts"])

# Service/uniform categories that typically reduce risk
SERVICE_CATEGORIES: frozenset[str] = frozenset(
    CLOTHING_PROMPTS_V2["delivery_branded"]["prompts"]
    + CLOTHING_PROMPTS_V2["delivery_generic"]["prompts"]
    + CLOTHING_PROMPTS_V2["utility_service"]["prompts"]
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
    """Load Marqo-FashionSigLIP model from local path or HuggingFace.

    This function loads the FashionSigLIP model using open_clip library directly.
    FashionSigLIP provides 57% improved accuracy over FashionCLIP while using
    the same SigLIP architecture for zero-shot classification.

    Note: We use open_clip directly instead of transformers.AutoModel because
    the Marqo model custom wrapper has meta tensor issues when loaded via
    transformers that cause "Cannot copy out of meta tensor" errors.

    Args:
        model_path: Path to local model directory or HuggingFace model path.
                   For local paths (e.g., "/export/ai_models/model-zoo/fashion-siglip"),
                   the model files should be in open_clip format.
                   For HuggingFace paths (e.g., "Marqo/marqo-fashionSigLIP"),
                   use "hf-hub:" prefix.

    Returns:
        Dictionary containing:
            - model: The FashionSigLIP model instance
            - preprocess: The image preprocessing transform
            - tokenizer: The text tokenizer

    Raises:
        ImportError: If open_clip_torch or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from open_clip import create_model_from_pretrained, get_tokenizer

        logger.info(f"Loading FashionSigLIP model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            """Load model, preprocess, and tokenizer synchronously."""
            # Convert path to HuggingFace hub format if needed
            # Local paths should be converted to hf-hub format for open_clip
            if model_path.startswith("/") or model_path.startswith("./"):
                # Local path - use hf-hub format with Marqo FashionSigLIP model
                # This assumes the local path contains a copy of the model,
                # but open_clip needs the hf-hub format for Marqo models
                hub_path = "hf-hub:Marqo/marqo-fashionSigLIP"
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
            logger.info(f"FashionSigLIP model loaded on {target_device}")

            model.eval()

            return {"model": model, "preprocess": preprocess, "tokenizer": tokenizer}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded FashionSigLIP model from {model_path}")
        return result

    except ImportError as e:
        logger.warning(
            "open_clip_torch or torch package not installed. "
            "Install with: pip install open_clip_torch torch"
        )
        raise ImportError(
            "FashionSigLIP requires open_clip_torch and torch. "
            "Install with: pip install open_clip_torch torch"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load FashionSigLIP model", exc_info=True, extra={"model_path": model_path}
        )
        raise RuntimeError(f"Failed to load FashionSigLIP model: {e}") from e


async def classify_clothing(
    model_dict: dict[str, Any],
    image: Image,
    prompts: list[str] | None = None,
    top_k: int = 3,
) -> ClothingClassification:
    """Classify clothing in a person crop using zero-shot classification.

    Uses SigLIP-style text-image similarity to classify clothing from a set
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
            with torch.inference_mode():
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
            with torch.inference_mode():
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
