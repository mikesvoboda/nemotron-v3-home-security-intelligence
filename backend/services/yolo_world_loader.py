"""YOLO-World model loader for open-vocabulary object detection.

This module provides async loading and detection functions for YOLO-World-S,
which enables zero-shot object detection via text prompts without fine-tuning.

YOLO-World-S is ideal for security scenarios where we need to detect
security-relevant objects that may not be in standard COCO classes
(knives, crowbars, packages, etc.).

Model:
    - Source: AILab-CVC/YOLO-World (via ultralytics integration)
    - VRAM: ~1.5GB
    - License: Apache 2.0

Usage:
    manager = get_model_manager()
    async with manager.load("yolo-world-s") as model:
        # Set custom prompts
        model.set_classes(["package", "knife", "person with backpack"])
        results = model.predict(image)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Security-relevant default prompts for home security monitoring
# These prompts are optimized for detecting objects of interest in security footage
SECURITY_PROMPTS: list[str] = [
    # Packages and deliveries
    "package",
    "cardboard box",
    "Amazon box",
    "delivery box",
    # Potential threats/tools
    "knife",
    "crowbar",
    "bolt cutters",
    "hammer",
    "baseball bat",
    "flashlight",
    # Items of interest
    "ladder",
    "backpack",
    "duffel bag",
    "suitcase",
    "shopping bag",
    # People and accessories
    "person",
    "face mask",
    "hoodie",
    "gloves",
]

# Extended prompts for vehicle-related security
VEHICLE_SECURITY_PROMPTS: list[str] = [
    "car",
    "truck",
    "van",
    "motorcycle",
    "bicycle",
    "license plate",
    "wheel",
    "door handle",
]

# Prompts for animal detection (common false alarm sources)
ANIMAL_PROMPTS: list[str] = [
    "dog",
    "cat",
    "bird",
    "squirrel",
    "deer",
    "raccoon",
]


async def load_yolo_world_model(model_path: str) -> Any:
    """Load YOLO-World model from ultralytics.

    This function loads the YOLO-World-S model which supports open-vocabulary
    detection - the ability to detect objects specified via text prompts
    without any fine-tuning.

    Args:
        model_path: Model identifier (e.g., "yolov8s-worldv2.pt" or custom path)

    Returns:
        YOLOWorld model instance ready for inference

    Raises:
        ImportError: If ultralytics is not installed
        RuntimeError: If model loading fails

    Example:
        model = await load_yolo_world_model("yolov8s-worldv2.pt")
        model.set_classes(["knife", "package"])
        results = model.predict(image)
    """
    try:
        from ultralytics import YOLOWorld

        logger.info(f"Loading YOLO-World model from {model_path}")

        # Run model loading in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def _load_model() -> Any:
            """Load YOLO-World model synchronously."""
            model = YOLOWorld(model_path)

            # Set default security prompts
            model.set_classes(SECURITY_PROMPTS)

            logger.info(f"YOLO-World model loaded with {len(SECURITY_PROMPTS)} default prompts")
            return model

        model = await loop.run_in_executor(None, _load_model)

        logger.info(f"Successfully loaded YOLO-World model from {model_path}")
        return model

    except ImportError as e:
        logger.warning("ultralytics package not installed. Install with: pip install ultralytics")
        raise ImportError(
            "YOLO-World requires ultralytics. Install with: pip install ultralytics"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load YOLO-World model from {model_path}: {e}")
        raise RuntimeError(f"Failed to load YOLO-World model: {e}") from e


async def detect_with_prompts(
    model: Any,
    image: Image.Image | str,
    prompts: list[str] | None = None,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> list[dict[str, Any]]:
    """Run YOLO-World detection with custom prompts.

    This helper function handles the complete detection workflow:
    1. Sets the detection prompts (classes to detect)
    2. Runs inference on the image
    3. Parses and returns structured results

    Args:
        model: Loaded YOLOWorld model instance
        image: PIL Image or path to image file
        prompts: List of text prompts for detection (uses SECURITY_PROMPTS if None)
        confidence_threshold: Minimum confidence score for detections (0.0-1.0)
        iou_threshold: IoU threshold for NMS (Non-Maximum Suppression)

    Returns:
        List of detection dictionaries, each containing:
            - class_name: The detected object class (from prompts)
            - confidence: Detection confidence score
            - bbox: Dictionary with x1, y1, x2, y2 coordinates
            - class_id: Integer class index

    Example:
        detections = await detect_with_prompts(
            model,
            image,
            prompts=["package", "person with backpack"],
            confidence_threshold=0.3
        )
        for det in detections:
            print(f"Found {det['class_name']} at {det['bbox']} (conf: {det['confidence']:.2f})")
    """
    loop = asyncio.get_event_loop()

    # Use security prompts by default
    detection_prompts = prompts if prompts is not None else SECURITY_PROMPTS

    def _run_detection() -> list[dict[str, Any]]:
        """Run detection synchronously."""
        # Set the classes/prompts for detection
        model.set_classes(detection_prompts)

        # Run inference
        results = model.predict(
            source=image,
            conf=confidence_threshold,
            iou=iou_threshold,
            verbose=False,
        )

        # Parse results
        detections: list[dict[str, Any]] = []

        for result in results:
            if result.boxes is None:
                continue

            boxes = result.boxes
            for i in range(len(boxes)):
                # Get bounding box coordinates
                xyxy = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())

                # Get class name from model
                class_name = result.names.get(cls_id, f"class_{cls_id}")

                detections.append(
                    {
                        "class_name": class_name,
                        "confidence": conf,
                        "bbox": {
                            "x1": float(xyxy[0]),
                            "y1": float(xyxy[1]),
                            "x2": float(xyxy[2]),
                            "y2": float(xyxy[3]),
                        },
                        "class_id": cls_id,
                    }
                )

        return detections

    detections = await loop.run_in_executor(None, _run_detection)

    logger.debug(
        f"YOLO-World detected {len(detections)} objects using {len(detection_prompts)} prompts"
    )

    return detections


def get_all_security_prompts() -> list[str]:
    """Get combined list of all security-related prompts.

    Returns:
        Combined list of security, vehicle, and animal prompts
    """
    return SECURITY_PROMPTS + VEHICLE_SECURITY_PROMPTS + ANIMAL_PROMPTS


def get_threat_prompts() -> list[str]:
    """Get prompts focused on potential security threats.

    Returns:
        List of prompts for objects that may indicate threats
    """
    return [
        "knife",
        "crowbar",
        "bolt cutters",
        "hammer",
        "baseball bat",
        "face mask",
        "hoodie",
        "gloves",
        "ladder",
    ]


def get_delivery_prompts() -> list[str]:
    """Get prompts focused on package/delivery detection.

    Returns:
        List of prompts for package and delivery items
    """
    return [
        "package",
        "cardboard box",
        "Amazon box",
        "delivery box",
        "shopping bag",
    ]
