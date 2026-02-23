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
import threading
from typing import TYPE_CHECKING, Any, TypedDict

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Per-model lock: set_classes() mutates model state and is NOT thread-safe.
# predict() must run with the same class list that was set — no interleaving allowed.
# Using a threading.Lock (not asyncio.Lock) because the actual work runs in
# run_in_executor (a thread pool), so asyncio primitives don't protect us there.
_yolo_world_lock = threading.Lock()

# ==============================================================================
# Hierarchical Security Object Categories (NEM-3913)
# ==============================================================================
# Object prompts organized by priority/risk level with category-specific thresholds.
# This hierarchical structure enables better risk assessment by the LLM.


class ObjectCategoryConfig(TypedDict):
    """Configuration for an object detection category."""

    prompts: list[str]
    threshold: float
    priority: str


YOLO_WORLD_PROMPTS_V2: dict[str, ObjectCategoryConfig] = {
    "weapons": {
        "prompts": [
            # Weapon-specific prompts tuned for home-security footage.
            # Keep both object-only and person+weapon phrasing to improve recall
            # on occluded porch/driveway views.
            "handgun",
            "pistol",
            "revolver",
            "rifle",
            "shotgun",
            "long gun",
            "knife blade",
            "kitchen knife",
            "combat knife",
            "machete",
            "crowbar tool",
            "pry bar",
            "baseball bat",
            "hammer",
            "metal pipe weapon",
            "person holding handgun",
            "person holding pistol",
            "person holding rifle",
            "person holding knife",
            "person carrying crowbar",
            # Legacy prompts for compatibility
            "knife",
            "gun",
            "firearm",
            "crowbar",
            "bolt cutters",
        ],
        "threshold": 0.22,
        "priority": "critical",
    },
    "suspicious_items": {
        "prompts": [
            "ladder against wall",
            "lock picks",
            "spray paint can",
            "broken glass",
            "pry bar",
            "wire cutters",
            # Legacy prompts for compatibility
            "ladder",
            "flashlight",
        ],
        "threshold": 0.25,
        "priority": "high",
    },
    "packages": {
        "prompts": [
            "cardboard delivery package",
            "Amazon shipping box",
            "FedEx package",
            "UPS package",
            "mail envelope",
            "food delivery bag",
            "pizza box",
            # Legacy prompts for compatibility
            "package",
            "cardboard box",
            "Amazon box",
            "delivery box",
        ],
        "threshold": 0.35,
        "priority": "medium",
    },
    "people": {
        "prompts": [
            "person standing",
            "person walking",
            "delivery driver with package",
            "mail carrier",
            "person at door",
            "person in driveway",
            # Legacy prompts for compatibility
            "person",
            "face mask",
            "hoodie",
            "gloves",
        ],
        "threshold": 0.35,
        "priority": "medium",
    },
    "bags": {
        "prompts": [
            "backpack",
            "duffel bag",
            "suitcase",
            "shopping bag",
            "messenger bag",
            "large bag",
            "gym bag",
        ],
        "threshold": 0.35,
        "priority": "medium",
    },
    "vehicles": {
        "prompts": [
            "car",
            "pickup truck",
            "delivery van",
            "SUV",
            "motorcycle",
            "bicycle",
            "scooter",
            # Legacy prompts for compatibility
            "truck",
            "van",
        ],
        "threshold": 0.40,
        "priority": "low",
    },
    "vehicle_parts": {
        "prompts": [
            "license plate",
            "wheel",
            "door handle",
            "car window",
            "side mirror",
        ],
        "threshold": 0.35,
        "priority": "low",
    },
    "animals": {
        "prompts": [
            "dog",
            "cat",
            "raccoon",
            "deer",
            "squirrel",
            "bird",
            "rabbit",
            "coyote",
            "fox",
        ],
        "threshold": 0.45,
        "priority": "low",
    },
}


def get_all_yolo_world_prompts() -> list[str]:
    """Get flattened list of all YOLO-World prompts from hierarchical categories.

    Returns:
        List of all prompts across all categories.
    """
    return [p for cat in YOLO_WORLD_PROMPTS_V2.values() for p in cat["prompts"]]


def get_object_priority(matched_object: str) -> str:
    """Get priority level for a detected object.

    Args:
        matched_object: The object class that was detected.

    Returns:
        Priority string: "critical", "high", "medium", or "low".
    """
    for config in YOLO_WORLD_PROMPTS_V2.values():
        if matched_object in config["prompts"]:
            return config["priority"]
    return "low"


def get_object_threshold(category: str) -> float:
    """Get confidence threshold for an object category.

    Args:
        category: Category name (e.g., "weapons", "packages").

    Returns:
        Confidence threshold for the category, or 0.35 as default.
    """
    config = YOLO_WORLD_PROMPTS_V2.get(category)
    if config is None:
        return 0.35
    return config["threshold"]


def get_object_category(matched_object: str) -> str | None:
    """Get category name for a detected object.

    Args:
        matched_object: The object class that was detected.

    Returns:
        Category name or None if not found.
    """
    for category, config in YOLO_WORLD_PROMPTS_V2.items():
        if matched_object in config["prompts"]:
            return category
    return None


def get_prompts_by_priority(priority: str) -> list[str]:
    """Get all prompts for a given priority level.

    Args:
        priority: Priority level ("critical", "high", "medium", "low").

    Returns:
        List of prompts matching the priority level.
    """
    prompts = []
    for config in YOLO_WORLD_PROMPTS_V2.values():
        if config["priority"] == priority:
            prompts.extend(config["prompts"])
    return prompts


# ==============================================================================
# Backward Compatibility - Legacy Constants (NEM-3913)
# ==============================================================================
# These constants are maintained for backward compatibility with existing code.
# New code should use the hierarchical YOLO_WORLD_PROMPTS_V2 structure.

# Security-relevant default prompts for home security monitoring
# These prompts are optimized for detecting objects of interest in security footage
SECURITY_PROMPTS: list[str] = (
    YOLO_WORLD_PROMPTS_V2["weapons"]["prompts"]
    + YOLO_WORLD_PROMPTS_V2["suspicious_items"]["prompts"]
    + YOLO_WORLD_PROMPTS_V2["packages"]["prompts"]
    + YOLO_WORLD_PROMPTS_V2["people"]["prompts"]
    + YOLO_WORLD_PROMPTS_V2["bags"]["prompts"]
)

# Extended prompts for vehicle-related security
VEHICLE_SECURITY_PROMPTS: list[str] = (
    YOLO_WORLD_PROMPTS_V2["vehicles"]["prompts"] + YOLO_WORLD_PROMPTS_V2["vehicle_parts"]["prompts"]
)

# Prompts for animal detection (common false alarm sources)
ANIMAL_PROMPTS: list[str] = YOLO_WORLD_PROMPTS_V2["animals"]["prompts"]


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
        loop = asyncio.get_running_loop()

        def _load_model() -> Any:
            """Load YOLO-World model synchronously."""
            model = YOLOWorld(model_path)

            # Acquire lock before first set_classes so any concurrent detect
            # calls that arrive before loading completes don't race us.
            with _yolo_world_lock:
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
        logger.error(
            "Failed to load YOLO-World model", exc_info=True, extra={"model_path": model_path}
        )
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
    loop = asyncio.get_running_loop()

    # Use security prompts by default
    detection_prompts = prompts if prompts is not None else SECURITY_PROMPTS

    def _run_detection() -> list[dict[str, Any]]:
        """Run detection synchronously.

        set_classes() + predict() must be atomic: another thread calling
        set_classes() between our set and predict would corrupt the class
        mapping, causing 'str object has no attribute names' on result.names.
        The threading.Lock serialises all YOLO-World inference calls.
        """
        with _yolo_world_lock:
            model.set_classes(detection_prompts)

            results = model.predict(
                source=image,
                conf=confidence_threshold,
                iou=iou_threshold,
                verbose=False,
            )

            # Snapshot names immediately while still holding the lock so the
            # mapping can't be overwritten before we finish parsing boxes.
            names_snapshot: dict[int, str] = dict(results[0].names) if results else {}

        # Parse results outside the lock — box data is already copied to CPU
        detections: list[dict[str, Any]] = []

        for result in results:
            if result.boxes is None:
                continue

            boxes = result.boxes
            for i in range(len(boxes)):
                xyxy = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())

                class_name = names_snapshot.get(cls_id, f"class_{cls_id}")

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
