"""YOLO26 Object Detection Module for Enrichment Service.

This module provides the YOLO26Detector class for general object detection
using YOLO26 models from Ultralytics. YOLO26 is the latest generation of
YOLO models offering improved accuracy and speed.

This is an optional secondary detector that can complement YOLO26v2 for
specific use cases like:
- Fine-grained object detection
- Domain-specific detection tasks
- Validation of primary detections

Note: YOLO models are optimized via TensorRT/ONNX export rather than
torch.compile(). For maximum performance, export the model to TensorRT format.

Model Variants:
- yolo26n: Nano (~3.5MB, fastest)
- yolo26s: Small (~11MB)
- yolo26m: Medium (~25MB, recommended) - ~100MB VRAM
- yolo26l: Large (~45MB)
- yolo26x: Extra-large (~98MB, most accurate)

Default VRAM: ~100MB (yolo26m)
Priority: LOW (optional enrichment)

Reference: https://docs.ultralytics.com/models/
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
from PIL import Image

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Add parent directory to path for shared utilities
_ai_dir = Path(__file__).parent.parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from torch_optimizations import BatchConfig, BatchProcessor

logger = logging.getLogger(__name__)

# Default model path environment variable
YOLO26_MODEL_PATH_ENV = "YOLO26_ENRICHMENT_MODEL_PATH"
YOLO26_DEFAULT_MODEL = "yolo26m.pt"

# COCO class names for standard YOLO models (80 classes)
COCO_CLASSES: tuple[str, ...] = (
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
)


def validate_model_path(path: str) -> str:
    """Validate model path to prevent path traversal attacks.

    Args:
        path: The model path to validate

    Returns:
        The validated path (normalized if local)

    Raises:
        ValueError: If path contains traversal sequences
    """
    if ".." in path:
        logger.warning(f"Suspicious model path detected (traversal sequence): {path}")
        raise ValueError(f"Invalid model path: path traversal sequences not allowed: {path}")

    if path.startswith("/") or path.startswith("./"):
        abs_path = str(Path(path).resolve())
        logger.debug(f"Local model path validated: {path} -> {abs_path}")
        return abs_path

    return path


@dataclass
class Detection:
    """A single object detection result.

    Attributes:
        class_name: Name of the detected class (e.g., "person", "car")
        class_id: Numeric class ID
        confidence: Detection confidence score (0.0 to 1.0)
        bbox: Bounding box coordinates [x1, y1, x2, y2] in pixels
    """

    class_name: str
    class_id: int
    confidence: float
    bbox: list[float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "class_name": self.class_name,
            "class_id": self.class_id,
            "confidence": round(self.confidence, 4),
            "bbox": [round(c, 2) for c in self.bbox],
        }


@dataclass
class YOLO26Result:
    """Result from YOLO26 detection analysis.

    Attributes:
        detections: List of individual object detections
        detection_count: Total number of detections
        classes_detected: Set of unique class names detected
        inference_time_ms: Time taken for inference in milliseconds
    """

    detections: list[Detection] = field(default_factory=list)
    detection_count: int = 0
    classes_detected: set[str] = field(default_factory=set)
    inference_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "detections": [d.to_dict() for d in self.detections],
            "detection_count": self.detection_count,
            "classes_detected": sorted(self.classes_detected),
            "inference_time_ms": round(self.inference_time_ms, 2),
        }

    def to_context_string(self) -> str:
        """Generate human-readable context string for Nemotron."""
        if not self.detections:
            return "No objects detected by YOLO26."

        lines = [f"YOLO26 detected {self.detection_count} object(s):"]

        # Group detections by class
        class_counts: dict[str, int] = {}
        for det in self.detections:
            class_counts[det.class_name] = class_counts.get(det.class_name, 0) + 1

        for class_name, count in sorted(class_counts.items()):
            lines.append(f"  - {class_name}: {count}")

        return "\n".join(lines)

    def filter_by_class(self, class_names: set[str]) -> list[Detection]:
        """Filter detections to only include specific classes.

        Args:
            class_names: Set of class names to include

        Returns:
            List of detections matching the specified classes
        """
        return [d for d in self.detections if d.class_name in class_names]

    def filter_by_confidence(self, min_confidence: float) -> list[Detection]:
        """Filter detections by minimum confidence threshold.

        Args:
            min_confidence: Minimum confidence score (0.0 to 1.0)

        Returns:
            List of detections above the threshold
        """
        return [d for d in self.detections if d.confidence >= min_confidence]


class YOLO26Detector:
    """YOLO26 object detection model wrapper for enrichment service.

    This class wraps a YOLO26 model from Ultralytics for general object
    detection in the enrichment pipeline. It can be used as a secondary
    detector to complement YOLO26v2 or for domain-specific detection tasks.

    Supports:
    - True batch inference with optimal batching (NEM-3377)
    - Multiple model variants (nano, small, medium, large, extra-large)
    - Custom-trained YOLO26 models

    Note: YOLO models are optimized via TensorRT/ONNX export rather than
    torch.compile(). For maximum performance, export the model to TensorRT format.

    Attributes:
        model_path: Path to the YOLO26 model weights
        device: Device to run inference on (e.g., "cuda:0", "cpu")
        confidence_threshold: Minimum confidence for detection (default: 0.25)
        model: The loaded YOLO model instance

    Example:
        >>> detector = YOLO26Detector("/models/yolo26m.pt")
        >>> detector.load_model()
        >>> result = detector.detect(image)
        >>> print(f"Found {result.detection_count} objects")
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        confidence_threshold: float = 0.25,
        max_batch_size: int = 8,
    ) -> None:
        """Initialize the YOLO26 detector.

        Args:
            model_path: Path to YOLO26 model file or model name
            device: Device to run inference on
            confidence_threshold: Minimum confidence for detections
            max_batch_size: Maximum batch size for batch inference (NEM-3377)

        Raises:
            ValueError: If model_path contains path traversal sequences
        """
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.model: Any = None
        self._class_names: dict[int, str] = {}

        # Batch processing configuration (NEM-3377)
        self.batch_processor = BatchProcessor(BatchConfig(max_batch_size=max_batch_size))

        logger.info(f"Initializing YOLO26Detector from {self.model_path}")

    def load_model(self) -> YOLO26Detector:
        """Load the YOLO26 model into memory.

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If ultralytics is not installed
            FileNotFoundError: If model weights are not found
            RuntimeError: If model loading fails
        """
        try:
            from ultralytics import YOLO
        except ImportError as e:
            logger.error("ultralytics package not installed. Install with: pip install ultralytics")
            raise ImportError(
                "ultralytics package required for YOLO26Detector. "
                "Install with: pip install ultralytics"
            ) from e

        logger.info(f"Loading YOLO26 model from {self.model_path}...")

        try:
            self.model = YOLO(self.model_path)

            # Move to appropriate device
            if "cuda" in self.device and torch.cuda.is_available():
                self.model.to(self.device)
                logger.info(f"YOLO26Detector loaded on {self.device}")
            else:
                self.device = "cpu"
                logger.info("YOLO26Detector using CPU (CUDA not available)")

            # Cache class names from model
            if hasattr(self.model, "names"):
                self._class_names = self.model.names
                logger.debug(f"Model classes: {len(self._class_names)} classes available")

            logger.info("YOLO26Detector loaded successfully")
            return self

        except Exception as e:
            logger.error(f"Failed to load YOLO26 model: {e}")
            raise RuntimeError(f"Failed to load YOLO26 model: {e}") from e

    def unload(self) -> None:
        """Unload the model from memory and free VRAM."""
        if self.model is not None:
            del self.model
            self.model = None

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("YOLO26Detector model unloaded")

    def detect(
        self,
        image: Image.Image | NDArray[np.uint8],
        classes: list[int] | None = None,
    ) -> YOLO26Result:
        """Detect objects in an image.

        Args:
            image: PIL Image or numpy array to analyze
            classes: Optional list of class IDs to filter (None = all classes)

        Returns:
            YOLO26Result containing all detected objects and metadata

        Raises:
            RuntimeError: If model is not loaded
        """
        if self.model is None:
            raise RuntimeError("YOLO26 model not loaded. Call load_model() first.")

        start_time = time.perf_counter()

        # Convert PIL to numpy if needed
        if isinstance(image, Image.Image):
            image_array = np.array(image.convert("RGB"))
        else:
            image_array = image

        # Run inference
        results = self.model(
            image_array,
            verbose=False,
            device=self.device,
            classes=classes,
        )

        detections: list[Detection] = []
        classes_detected: set[str] = set()

        # Process results
        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for box in boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])

                # Skip low-confidence detections
                if conf < self.confidence_threshold:
                    continue

                # Determine class name
                if cls_id in self._class_names:
                    class_name = self._class_names[cls_id]
                elif cls_id < len(COCO_CLASSES):
                    class_name = COCO_CLASSES[cls_id]
                else:
                    class_name = f"class_{cls_id}"

                # Extract bounding box
                bbox = box.xyxy[0].tolist()

                # Create detection
                detection = Detection(
                    class_name=class_name,
                    class_id=cls_id,
                    confidence=conf,
                    bbox=bbox,
                )
                detections.append(detection)
                classes_detected.add(class_name)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return YOLO26Result(
            detections=detections,
            detection_count=len(detections),
            classes_detected=classes_detected,
            inference_time_ms=inference_time_ms,
        )

    def detect_batch(
        self,
        images: list[Image.Image | NDArray[np.uint8]],
        classes: list[int] | None = None,
    ) -> list[YOLO26Result]:
        """Detect objects in multiple images using batch inference.

        Args:
            images: List of PIL Images or numpy arrays
            classes: Optional list of class IDs to filter (None = all classes)

        Returns:
            List of YOLO26Result, one per image

        Raises:
            RuntimeError: If model is not loaded
        """
        if self.model is None:
            raise RuntimeError("YOLO26 model not loaded. Call load_model() first.")

        start_time = time.perf_counter()

        # Convert all images to numpy arrays
        image_arrays = []
        for img in images:
            if isinstance(img, Image.Image):
                image_arrays.append(np.array(img.convert("RGB")))
            else:
                image_arrays.append(img)

        # Run batch inference
        results = self.model(
            image_arrays,
            verbose=False,
            device=self.device,
            classes=classes,
        )

        total_inference_time_ms = (time.perf_counter() - start_time) * 1000
        per_image_time = total_inference_time_ms / len(images) if images else 0

        yolo26_results = []
        for result in results:
            detections: list[Detection] = []
            classes_detected: set[str] = set()

            if result.boxes is not None:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])

                    if conf < self.confidence_threshold:
                        continue

                    if cls_id in self._class_names:
                        class_name = self._class_names[cls_id]
                    elif cls_id < len(COCO_CLASSES):
                        class_name = COCO_CLASSES[cls_id]
                    else:
                        class_name = f"class_{cls_id}"

                    bbox = box.xyxy[0].tolist()

                    detection = Detection(
                        class_name=class_name,
                        class_id=cls_id,
                        confidence=conf,
                        bbox=bbox,
                    )
                    detections.append(detection)
                    classes_detected.add(class_name)

            yolo26_results.append(
                YOLO26Result(
                    detections=detections,
                    detection_count=len(detections),
                    classes_detected=classes_detected,
                    inference_time_ms=per_image_time,
                )
            )

        return yolo26_results

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold for detections.

        Args:
            threshold: New confidence threshold (0.0 to 1.0)

        Raises:
            ValueError: If threshold is not in valid range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")

        self.confidence_threshold = threshold
        logger.info(f"YOLO26Detector confidence threshold set to {threshold}")

    def get_class_names(self) -> list[str]:
        """Get list of class names the model can detect.

        Returns:
            List of class names
        """
        if self._class_names:
            return list(self._class_names.values())
        return list(COCO_CLASSES)

    def get_class_id(self, class_name: str) -> int | None:
        """Get the class ID for a given class name.

        Args:
            class_name: The class name to look up

        Returns:
            The class ID or None if not found
        """
        for cls_id, name in self._class_names.items():
            if name.lower() == class_name.lower():
                return cls_id

        # Fallback to COCO classes
        try:
            return COCO_CLASSES.index(class_name.lower())
        except ValueError:
            return None


def load_yolo26_detector(
    model_path: str | None = None,
    device: str = "cuda:0",
    confidence_threshold: float = 0.25,
) -> YOLO26Detector:
    """Factory function for creating and loading a YOLO26Detector.

    This function is designed for use with the model registry's on-demand
    loading system. It creates a YOLO26Detector instance and loads the model
    in a single call.

    Args:
        model_path: Path to the YOLO26 model weights. Defaults to environment
                   variable YOLO26_ENRICHMENT_MODEL_PATH or "yolo26m.pt"
        device: Device to run inference on
        confidence_threshold: Minimum confidence for detections

    Returns:
        Loaded YOLO26Detector instance ready for inference
    """
    if model_path is None:
        model_path = os.environ.get(YOLO26_MODEL_PATH_ENV, YOLO26_DEFAULT_MODEL)

    detector = YOLO26Detector(
        model_path=model_path,
        device=device,
        confidence_threshold=confidence_threshold,
    )
    return detector.load_model()
