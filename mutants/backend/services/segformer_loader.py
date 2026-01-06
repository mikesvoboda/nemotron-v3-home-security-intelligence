"""SegFormer B2 Clothes model loader for clothing segmentation.

This module provides async loading of the SegFormer B2 Clothes model for detecting
clothing categories on person detections in security camera feeds.

The SegFormer B2 Clothes model segments 18 clothing categories:
    0: Background, 1: Hat, 2: Hair, 3: Sunglasses, 4: Upper-clothes,
    5: Skirt, 6: Pants, 7: Dress, 8: Belt, 9: Left-shoe, 10: Right-shoe,
    11: Face, 12: Left-leg, 13: Right-leg, 14: Left-arm, 15: Right-arm,
    16: Bag, 17: Scarf

Model Details:
    - HuggingFace: mattmdjaga/segformer_b2_clothes
    - Parameters: 25M
    - VRAM: ~1.5GB (float16)
    - License: MIT

Use Cases:
    - Clothing-based person identification
    - Suspicious attire detection (covered face, all black, etc.)
    - Re-identification attribute extraction
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# SegFormer B2 Clothes label mapping (from model config)
CLOTHING_LABELS = {
    0: "background",
    1: "hat",
    2: "hair",
    3: "sunglasses",
    4: "upper_clothes",
    5: "skirt",
    6: "pants",
    7: "dress",
    8: "belt",
    9: "left_shoe",
    10: "right_shoe",
    11: "face",
    12: "left_leg",
    13: "right_leg",
    14: "left_arm",
    15: "right_arm",
    16: "bag",
    17: "scarf",
}

# Clothing categories of security interest (subset of all labels)
SECURITY_CLOTHING_LABELS = frozenset(
    {
        "hat",
        "sunglasses",
        "upper_clothes",
        "skirt",
        "pants",
        "dress",
        "belt",
        "bag",
        "scarf",
    }
)

# Consolidated shoe category
SHOE_LABELS = frozenset({"left_shoe", "right_shoe"})


@dataclass
class ClothingSegmentationResult:
    """Result from clothing segmentation for a single person.

    Attributes:
        clothing_items: Set of detected clothing categories
        has_face_covered: Whether face appears covered (sunglasses + hat/scarf)
        has_bag: Whether person is carrying a bag
        coverage_percentages: Dictionary mapping clothing type to pixel coverage percentage
        raw_mask: Raw segmentation mask (optional, for visualization)
    """

    clothing_items: set[str] = field(default_factory=set)
    has_face_covered: bool = False
    has_bag: bool = False
    coverage_percentages: dict[str, float] = field(default_factory=dict)
    raw_mask: Any = None  # numpy array if available

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "clothing_items": sorted(self.clothing_items),
            "has_face_covered": self.has_face_covered,
            "has_bag": self.has_bag,
            "coverage_percentages": self.coverage_percentages,
        }


async def load_segformer_model(model_path: str) -> Any:
    """Load SegFormer B2 Clothes model from local path.

    This function loads the SegFormer B2 Clothes model for clothing segmentation.
    The model segments 18 clothing/body part categories.

    Args:
        model_path: Local path to the model directory

    Returns:
        Tuple of (model, processor) for inference

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import AutoModelForSemanticSegmentation, SegformerImageProcessor

        logger.info(f"Loading SegFormer B2 Clothes model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load_model() -> tuple[Any, Any]:
            """Load model and processor synchronously."""
            # Load processor (image preprocessor)
            processor = SegformerImageProcessor.from_pretrained(model_path)

            # Determine device and dtype
            if torch.cuda.is_available():
                device = "cuda"
                dtype = torch.float16
            else:
                device = "cpu"
                dtype = torch.float32

            # Load model
            model = AutoModelForSemanticSegmentation.from_pretrained(
                model_path,
                torch_dtype=dtype,
            )

            # Move to device and set eval mode
            model = model.to(device)
            model.eval()

            return model, processor

        model, processor = await loop.run_in_executor(None, _load_model)

        logger.info(f"Successfully loaded SegFormer B2 Clothes model from {model_path}")
        return (model, processor)

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "SegFormer requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load SegFormer model from {model_path}: {e}")
        raise RuntimeError(f"Failed to load SegFormer model: {e}") from e


async def segment_clothing(
    model: Any,
    processor: Any,
    person_crop: Image.Image,
    min_coverage: float = 0.01,
) -> ClothingSegmentationResult:
    """Segment clothing in a person crop image.

    Runs the SegFormer model on a cropped person image and extracts
    detected clothing categories with coverage percentages.

    Args:
        model: Loaded SegFormer model
        processor: SegFormer processor
        person_crop: PIL Image of cropped person region
        min_coverage: Minimum pixel coverage ratio to consider a category detected (0-1)

    Returns:
        ClothingSegmentationResult with detected clothing items
    """
    try:
        import numpy as np
        import torch

        loop = asyncio.get_event_loop()

        def _segment() -> ClothingSegmentationResult:
            """Run segmentation synchronously."""
            # Prepare image for model
            inputs = processor(images=person_crop, return_tensors="pt")

            # Move to same device as model
            device = next(model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)

            # Get segmentation logits and upsample to original image size
            logits = outputs.logits
            upsampled_logits = torch.nn.functional.interpolate(
                logits,
                size=person_crop.size[::-1],  # (height, width)
                mode="bilinear",
                align_corners=False,
            )

            # Get predicted class for each pixel
            predicted_mask = upsampled_logits.argmax(dim=1).squeeze().cpu().numpy()

            # Calculate coverage for each class
            total_pixels = predicted_mask.size
            unique_classes, counts = np.unique(predicted_mask, return_counts=True)

            coverage_percentages: dict[str, float] = {}
            clothing_items: set[str] = set()

            for class_id, count in zip(unique_classes, counts, strict=True):
                label = CLOTHING_LABELS.get(int(class_id), "unknown")
                coverage = count / total_pixels

                if label != "background" and coverage >= min_coverage:
                    coverage_percentages[label] = round(coverage * 100, 2)

                    # Add to clothing items if it's a security-relevant category
                    if label in SECURITY_CLOTHING_LABELS:
                        clothing_items.add(label)
                    # Consolidate shoes
                    elif label in SHOE_LABELS:
                        clothing_items.add("shoes")
                        # Sum shoe coverage
                        current = coverage_percentages.get("shoes", 0.0)
                        coverage_percentages["shoes"] = round(current + coverage * 100, 2)
                        # Remove individual shoe entries
                        coverage_percentages.pop(label, None)

            # Determine if face is covered (sunglasses + hat or scarf covering face area)
            has_sunglasses = "sunglasses" in clothing_items
            has_head_covering = "hat" in clothing_items or "scarf" in clothing_items
            face_coverage = coverage_percentages.get("face", 0.0)
            # Face covered if sunglasses present and either hat/scarf or very low face visibility
            has_face_covered = has_sunglasses and (has_head_covering or face_coverage < 5.0)

            # Determine if carrying bag
            has_bag = "bag" in clothing_items

            return ClothingSegmentationResult(
                clothing_items=clothing_items,
                has_face_covered=has_face_covered,
                has_bag=has_bag,
                coverage_percentages=coverage_percentages,
                raw_mask=predicted_mask,
            )

        return await loop.run_in_executor(None, _segment)

    except Exception as e:
        logger.error(f"Failed to segment clothing: {e}")
        return ClothingSegmentationResult()


async def segment_clothing_batch(
    model: Any,
    processor: Any,
    person_crops: list[Image.Image],
    min_coverage: float = 0.01,
) -> list[ClothingSegmentationResult]:
    """Segment clothing in multiple person crops.

    Processes person crops individually (batch processing not supported by model)
    and returns results for each.

    Args:
        model: Loaded SegFormer model
        processor: SegFormer processor
        person_crops: List of PIL Images of cropped person regions
        min_coverage: Minimum pixel coverage ratio to consider a category detected

    Returns:
        List of ClothingSegmentationResult for each input crop
    """
    if not person_crops:
        return []

    results: list[ClothingSegmentationResult] = []

    for crop in person_crops:
        result = await segment_clothing(model, processor, crop, min_coverage)
        results.append(result)

    return results


def format_clothing_context(result: ClothingSegmentationResult) -> str:
    """Format clothing segmentation result for LLM context.

    Args:
        result: ClothingSegmentationResult to format

    Returns:
        Human-readable string describing detected clothing
    """
    if not result.clothing_items:
        return "No clothing detected"

    items = sorted(result.clothing_items)
    items_str = ", ".join(items)

    parts = [f"Clothing: {items_str}"]

    if result.has_face_covered:
        parts.append("(face appears covered)")

    if result.has_bag:
        parts.append("(carrying bag)")

    return " ".join(parts)


def format_batch_clothing_context(
    results: list[ClothingSegmentationResult], detection_ids: list[str] | None = None
) -> str:
    """Format multiple clothing results for LLM context.

    Args:
        results: List of ClothingSegmentationResult
        detection_ids: Optional list of detection IDs for labeling

    Returns:
        Human-readable string describing all detected clothing
    """
    if not results:
        return "No clothing analysis available"

    lines = []
    for i, result in enumerate(results):
        if not result.clothing_items:
            continue

        label = (
            f"Person {detection_ids[i]}"
            if detection_ids and i < len(detection_ids)
            else f"Person {i + 1}"
        )
        context = format_clothing_context(result)
        lines.append(f"  - {label}: {context}")

    if not lines:
        return "No clothing detected on persons"

    return "\n".join(lines)
