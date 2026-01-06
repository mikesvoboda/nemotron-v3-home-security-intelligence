"""Vehicle segment classification model loader.

This module provides async loading and classification functions for the
ResNet-50-Vehicle-Segment-Classification model from AventIQ-AI.

The model classifies vehicles into 11 categories:
- car
- pickup_truck
- single_unit_truck
- articulated_truck
- bus
- motorcycle
- bicycle
- work_van
- non_motorized_vehicle
- pedestrian (included in dataset but filtered in vehicle context)
- background

Model details:
- HuggingFace: AventIQ-AI/ResNet-50-Vehicle-Segment-classification
- Architecture: ResNet-50 (fine-tuned on MIO-TCD Traffic Dataset)
- VRAM: ~1.5GB (conservative estimate with batch processing)
- Input: 224x224 images (auto-resized)
- Output: Vehicle type with confidence score

Usage in security context:
- Provides specific vehicle type beyond RT-DETRv2's generic "car/truck/bus"
- Distinguishes pickup trucks from sedans, work vans from cars
- Helps identify delivery vehicles (work_van) vs personal vehicles
- Articulated trucks may indicate commercial/industrial activity
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


# Vehicle class labels (from classes.txt)
# Order matches the model's output indices
VEHICLE_SEGMENT_CLASSES: list[str] = [
    "articulated_truck",
    "background",
    "bicycle",
    "bus",
    "car",
    "motorcycle",
    "non_motorized_vehicle",
    "pedestrian",
    "pickup_truck",
    "single_unit_truck",
    "work_van",
]

# Map from RT-DETRv2 classes to expected vehicle segment classes
# Used to validate that we're running on appropriate detections
RTDETR_VEHICLE_CLASSES: frozenset[str] = frozenset(
    {
        "car",
        "truck",
        "bus",
        "motorcycle",
        "bicycle",
    }
)

# Classes that are not vehicles (filter these from results)
NON_VEHICLE_CLASSES: frozenset[str] = frozenset(
    {
        "background",
        "pedestrian",
    }
)

# Commercial/delivery vehicle classes
COMMERCIAL_VEHICLE_CLASSES: frozenset[str] = frozenset(
    {
        "articulated_truck",
        "single_unit_truck",
        "work_van",
    }
)

# Simplified display names for context strings
VEHICLE_DISPLAY_NAMES: dict[str, str] = {
    "articulated_truck": "articulated truck (semi/18-wheeler)",
    "bicycle": "bicycle",
    "bus": "bus",
    "car": "car/sedan",
    "motorcycle": "motorcycle",
    "non_motorized_vehicle": "non-motorized vehicle",
    "pickup_truck": "pickup truck",
    "single_unit_truck": "single-unit truck (box truck/delivery)",
    "work_van": "work van/delivery van",
}


@dataclass
class VehicleClassificationResult:
    """Result from vehicle segment classification.

    Attributes:
        vehicle_type: Classified vehicle type (e.g., "pickup_truck")
        confidence: Classification confidence (0-1)
        display_name: Human-readable vehicle type description
        is_commercial: Whether the vehicle is a commercial/delivery type
        all_scores: Dictionary of all class scores (top 3)
    """

    vehicle_type: str
    confidence: float
    display_name: str
    is_commercial: bool
    all_scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "vehicle_type": self.vehicle_type,
            "confidence": self.confidence,
            "display_name": self.display_name,
            "is_commercial": self.is_commercial,
            "all_scores": self.all_scores,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable vehicle type description for Nemotron context
        """
        conf_str = f"{self.confidence:.0%}"
        base = f"Vehicle type: {self.display_name} ({conf_str} confidence)"
        if self.is_commercial:
            base += " [Commercial/delivery vehicle]"
        return base


async def load_vehicle_classifier(model_path: str) -> dict[str, Any]:
    """Load ResNet-50 Vehicle Segment Classification model from local path.

    This function loads the fine-tuned ResNet-50 model for vehicle type
    classification. The model was trained on the MIO-TCD Traffic Dataset.

    Args:
        model_path: Local path to the downloaded model directory
                   (should contain pytorch_model.bin and classes.txt)

    Returns:
        Dictionary containing:
            - model: The ResNet-50 model instance
            - transform: Image transforms for preprocessing
            - classes: List of class names

    Raises:
        ImportError: If torch or torchvision is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from torchvision import models, transforms

        logger.info(f"Loading Vehicle Segment Classification model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            """Load model and transforms synchronously."""
            model_dir = Path(model_path)

            # Load class names
            classes_file = model_dir / "classes.txt"
            if classes_file.exists():
                with open(classes_file) as f:
                    classes = f.read().splitlines()
            else:
                # Fall back to default classes
                classes = VEHICLE_SEGMENT_CLASSES
                logger.warning("classes.txt not found, using default classes")

            # Create ResNet-50 model architecture
            model = models.resnet50(weights=None)

            # Modify final layer to match number of classes (11)
            num_ftrs = model.fc.in_features
            model.fc = torch.nn.Linear(num_ftrs, len(classes))

            # Load trained weights
            weights_file = model_dir / "pytorch_model.bin"
            if not weights_file.exists():
                raise FileNotFoundError(f"Model weights not found: {weights_file}")

            state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)
            model.load_state_dict(state_dict)

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.cuda()
                logger.info("Vehicle classifier moved to CUDA")
            else:
                logger.info("Vehicle classifier using CPU")

            # Set to eval mode
            model.eval()

            # Define image transforms (same as training)
            transform = transforms.Compose(
                [
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                ]
            )

            return {
                "model": model,
                "transform": transform,
                "classes": classes,
            }

        result = await loop.run_in_executor(None, _load)

        logger.info(
            f"Successfully loaded Vehicle Segment Classification model "
            f"({len(result['classes'])} classes)"
        )
        return result

    except ImportError as e:
        logger.warning(
            "torch or torchvision package not installed. "
            "Install with: pip install torch torchvision"
        )
        raise ImportError(
            "Vehicle classifier requires torch and torchvision. "
            "Install with: pip install torch torchvision"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load Vehicle Segment Classification model: {e}")
        raise RuntimeError(f"Failed to load Vehicle Segment Classification model: {e}") from e


async def classify_vehicle(
    model_dict: dict[str, Any],
    image: Image.Image,
    top_k: int = 3,
) -> VehicleClassificationResult:
    """Classify vehicle type from an image crop.

    Args:
        model_dict: Dictionary containing model, transform, and classes
                   from load_vehicle_classifier
        image: PIL Image of vehicle crop (should be cropped to vehicle bbox)
        top_k: Number of top classes to include in all_scores

    Returns:
        VehicleClassificationResult with vehicle type and confidence

    Raises:
        RuntimeError: If classification fails
    """
    try:
        import torch

        model = model_dict["model"]
        transform = model_dict["transform"]
        classes = model_dict["classes"]

        loop = asyncio.get_event_loop()

        def _classify() -> VehicleClassificationResult:
            """Run classification synchronously."""
            # Ensure RGB mode
            rgb_image = image.convert("RGB") if image.mode != "RGB" else image

            # Preprocess image
            input_tensor = transform(rgb_image).unsqueeze(0)  # Add batch dimension

            # Move to same device as model
            device = next(model.parameters()).device
            input_tensor = input_tensor.to(device)

            # Run inference
            with torch.no_grad():
                outputs = model(input_tensor)
                probs = torch.nn.functional.softmax(outputs, dim=-1)[0]

            # Get scores for all classes
            all_class_scores = {cls: float(probs[i].item()) for i, cls in enumerate(classes)}

            # Filter out non-vehicle classes for ranking
            vehicle_scores = {
                cls: score
                for cls, score in all_class_scores.items()
                if cls not in NON_VEHICLE_CLASSES
            }

            # Sort by score
            sorted_scores = sorted(vehicle_scores.items(), key=lambda x: x[1], reverse=True)

            # Get top prediction
            top_class = sorted_scores[0][0]
            top_confidence = sorted_scores[0][1]

            # Get top_k scores
            top_k_scores = dict(sorted_scores[:top_k])

            # Get display name and commercial status
            display_name = VEHICLE_DISPLAY_NAMES.get(top_class, top_class)
            is_commercial = top_class in COMMERCIAL_VEHICLE_CLASSES

            return VehicleClassificationResult(
                vehicle_type=top_class,
                confidence=top_confidence,
                display_name=display_name,
                is_commercial=is_commercial,
                all_scores=top_k_scores,
            )

        return await loop.run_in_executor(None, _classify)

    except Exception as e:
        logger.error(f"Vehicle classification failed: {e}")
        raise RuntimeError(f"Vehicle classification failed: {e}") from e


async def classify_vehicles_batch(
    model_dict: dict[str, Any],
    images: list[Image.Image],
    top_k: int = 3,
) -> list[VehicleClassificationResult]:
    """Classify vehicle types for multiple image crops.

    Batch processes multiple vehicle crops for efficiency.

    Args:
        model_dict: Dictionary containing model, transform, and classes
        images: List of PIL Images (vehicle crops)
        top_k: Number of top classes to include in all_scores

    Returns:
        List of VehicleClassificationResult, one per input image
    """
    if not images:
        return []

    try:
        import torch

        model = model_dict["model"]
        transform = model_dict["transform"]
        classes = model_dict["classes"]

        loop = asyncio.get_event_loop()

        def _classify_batch() -> list[VehicleClassificationResult]:
            """Run batch classification synchronously."""
            # Preprocess all images
            tensors = []
            for img in images:
                # Ensure RGB mode
                rgb_img = img.convert("RGB") if img.mode != "RGB" else img
                tensors.append(transform(rgb_img))

            # Stack into batch
            batch_tensor = torch.stack(tensors)

            # Move to same device as model
            device = next(model.parameters()).device
            batch_tensor = batch_tensor.to(device)

            # Run inference
            with torch.no_grad():
                outputs = model(batch_tensor)
                all_probs = torch.nn.functional.softmax(outputs, dim=-1)

            results = []
            for probs in all_probs:
                # Get scores for all classes
                all_class_scores = {cls: float(probs[i].item()) for i, cls in enumerate(classes)}

                # Filter out non-vehicle classes
                vehicle_scores = {
                    cls: score
                    for cls, score in all_class_scores.items()
                    if cls not in NON_VEHICLE_CLASSES
                }

                # Sort by score
                sorted_scores = sorted(vehicle_scores.items(), key=lambda x: x[1], reverse=True)

                # Get top prediction
                top_class = sorted_scores[0][0]
                top_confidence = sorted_scores[0][1]

                # Get top_k scores
                top_k_scores = dict(sorted_scores[:top_k])

                # Get display name and commercial status
                display_name = VEHICLE_DISPLAY_NAMES.get(top_class, top_class)
                is_commercial = top_class in COMMERCIAL_VEHICLE_CLASSES

                results.append(
                    VehicleClassificationResult(
                        vehicle_type=top_class,
                        confidence=top_confidence,
                        display_name=display_name,
                        is_commercial=is_commercial,
                        all_scores=top_k_scores,
                    )
                )

            return results

        return await loop.run_in_executor(None, _classify_batch)

    except Exception as e:
        logger.error(f"Batch vehicle classification failed: {e}")
        raise RuntimeError(f"Batch vehicle classification failed: {e}") from e


def format_vehicle_classification_context(
    classification: VehicleClassificationResult,
) -> str:
    """Format vehicle classification as context string for LLM prompt.

    Args:
        classification: VehicleClassificationResult from classify_vehicle

    Returns:
        Formatted string for inclusion in risk analysis prompt
    """
    lines = [f"Vehicle: {classification.display_name}"]

    if classification.is_commercial:
        lines.append("  [Commercial/delivery vehicle]")

    lines.append(f"  Confidence: {classification.confidence:.1%}")

    # Add top alternative if confidence is low
    if classification.confidence < 0.6 and len(classification.all_scores) > 1:
        sorted_scores = sorted(classification.all_scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) > 1:
            alt_type, alt_score = sorted_scores[1]
            alt_display = VEHICLE_DISPLAY_NAMES.get(alt_type, alt_type)
            lines.append(f"  Alternative: {alt_display} ({alt_score:.1%})")

    return "\n".join(lines)
