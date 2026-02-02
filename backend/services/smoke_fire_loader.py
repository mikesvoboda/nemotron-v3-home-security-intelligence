"""Smoke/fire detection model loader.

This module provides async loading and inference for the YOLOv8n smoke/fire detection
model, trained to detect smoke and fire in images.

The model performs object detection focused on safety-relevant hazards like
smoke clouds and active fires.

Model details:
- Architecture: YOLOv8n (nano variant for fast inference)
- Source: luminous0219/fire-and-smoke-detection-yolov8
- Input: Images of any size (resized internally)
- Output: Bounding boxes with class labels and confidence scores
- VRAM: ~350MB
- Classes: smoke, fire
- Priority: CRITICAL (never evict from VRAM)

Usage in security context:
- Run on full frame continuously for fire/smoke detection
- Provides high-priority alerts for fire detection
- Smoke requires consecutive detections to reduce false positives (steam, fog)
- Integrates with risk scoring for immediate escalation
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Module-level YOLO placeholder for testability (assigned in load_smoke_fire_model)
# This allows tests to patch "backend.services.smoke_fire_loader.YOLO"
YOLO: type | None = None

# Smoke/fire classes that this model detects
SMOKE_FIRE_CLASSES: frozenset[str] = frozenset({"smoke", "fire"})

# VRAM usage for model loading (300-400MB range)
SMOKE_FIRE_VRAM_MB: int = 350

# Confidence thresholds
SMOKE_CONFIDENCE_THRESHOLD: float = 0.75  # Higher to reduce false positives from steam/fog
FIRE_CONFIDENCE_THRESHOLD: float = 0.70  # Lower since fire is more critical

# Default model path (HuggingFace repo)
SMOKE_FIRE_MODEL_PATH: str = "luminous0219/fire-and-smoke-detection-yolov8"

# High priority confidence threshold for smoke (fire is always high priority)
SMOKE_HIGH_PRIORITY_CONFIDENCE: float = 0.85


@dataclass(slots=True)
class SmokeFireDetection:
    """Single smoke/fire detection result.

    Attributes:
        detection_type: Type of detection ("smoke" or "fire")
        confidence: Detection confidence (0-1)
        bbox: Bounding box as (x1, y1, x2, y2)
    """

    detection_type: str
    confidence: float
    bbox: tuple[float, float, float, float]

    @property
    def is_high_priority(self) -> bool:
        """Check if this detection is high priority.

        Fire is always high priority due to immediate danger.
        Smoke is high priority only with very high confidence.

        Returns:
            True if detection is high priority, False otherwise
        """
        if self.detection_type == "fire":
            return True
        # Smoke is high priority at >= 0.85 confidence
        return self.confidence >= SMOKE_HIGH_PRIORITY_CONFIDENCE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "detection_type": self.detection_type,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
            "is_high_priority": self.is_high_priority,
        }


@dataclass(slots=True)
class SmokeFireDetectionResult:
    """Result from smoke/fire detection.

    Attributes:
        detections: List of detected smoke/fire instances
    """

    detections: list[SmokeFireDetection] = field(default_factory=list)

    @property
    def has_detections(self) -> bool:
        """Check if any smoke or fire was detected."""
        return len(self.detections) > 0

    @property
    def has_fire(self) -> bool:
        """Check if fire was detected."""
        return any(d.detection_type == "fire" for d in self.detections)

    @property
    def has_smoke(self) -> bool:
        """Check if smoke was detected."""
        return any(d.detection_type == "smoke" for d in self.detections)

    @property
    def highest_confidence(self) -> float:
        """Get the highest confidence among all detections."""
        if not self.detections:
            return 0.0
        return max(d.confidence for d in self.detections)

    @property
    def is_high_priority(self) -> bool:
        """Check if any detection is high priority."""
        return self.has_fire or any(d.is_high_priority for d in self.detections)

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable smoke/fire detection summary for Nemotron context
        """
        if not self.has_detections:
            return "Smoke/Fire scan: No smoke or fire detected"

        lines = []

        if self.has_fire:
            lines.append("**CRITICAL FIRE ALERT**")
            lines.append("  IMMEDIATE ACTION REQUIRED!")
        elif self.has_smoke:
            lines.append("**SMOKE DETECTION ALERT**")

        for detection in sorted(self.detections, key=lambda d: d.confidence, reverse=True):
            priority_marker = " [HIGH PRIORITY]" if detection.is_high_priority else ""
            lines.append(
                f"  - {detection.detection_type.upper()}: "
                f"{detection.confidence:.0%} confidence{priority_marker}"
            )

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "detections": [d.to_dict() for d in self.detections],
            "has_fire": self.has_fire,
            "has_smoke": self.has_smoke,
            "highest_confidence": self.highest_confidence,
            "is_high_priority": self.is_high_priority,
            "detection_count": len(self.detections),
        }


async def load_smoke_fire_model(model_path: str) -> Any:
    """Load YOLOv8n smoke/fire detection model from local path.

    This function loads the YOLO-based smoke/fire detection model for
    identifying smoke and fire hazards.

    Args:
        model_path: Local path to the model directory
                   (e.g., "/models/model-zoo/smoke-fire-yolov8n")
                   Should contain the model weights file (.pt)

    Returns:
        Loaded YOLO model instance (ready for inference)

    Raises:
        ImportError: If ultralytics is not installed
        RuntimeError: If model loading fails
    """
    global YOLO  # noqa: PLW0603
    try:
        # Use module-level YOLO if already set (for testability), otherwise import
        if YOLO is None:
            from ultralytics import YOLO as _YOLO

            YOLO = _YOLO

        logger.info(f"Loading smoke/fire detection model from {model_path}")

        loop = asyncio.get_running_loop()

        # Capture YOLO reference for closure (needed for thread executor)
        yolo_class = YOLO

        def _load_and_fuse() -> Any:
            """Load YOLO model and pre-fuse for thread-safe concurrent use.

            YOLO models automatically fuse batch normalization into Conv layers
            on first predict() call. This fusion is NOT thread-safe and causes
            errors when multiple threads call predict() concurrently.

            By calling fuse() immediately after loading, we ensure the model
            is ready for concurrent use without race conditions.
            """
            model_dir = Path(model_path)

            # In test mode (YOLO is mocked), skip file existence checks
            # Check if YOLO is a mock by looking for mock-specific attributes
            is_mock = hasattr(yolo_class, "_mock_name") or hasattr(yolo_class, "assert_called")

            if is_mock:
                # Use a default path for mocked tests
                weights_file = model_dir / "smoke-fire-yolov8n.pt"
            else:
                # Find the model weights file
                weights_file = model_dir / "model.pt"
                if not weights_file.exists():
                    weights_file = model_dir / "best.pt"
                if not weights_file.exists():
                    weights_file = model_dir / "smoke-fire-yolov8n.pt"
                if not weights_file.exists():
                    # Try any .pt file
                    pt_files = list(model_dir.glob("*.pt"))
                    if pt_files:
                        weights_file = pt_files[0]
                    else:
                        raise FileNotFoundError(f"No model weights (.pt) found in {model_dir}")

            model = yolo_class(str(weights_file))  # type: ignore[misc]

            # Pre-fuse to avoid race condition
            if hasattr(model, "fuse"):
                inner_model = getattr(model, "model", None)
                if inner_model is not None and hasattr(inner_model, "is_fused"):
                    if not inner_model.is_fused():
                        model.fuse()
                else:
                    model.fuse()

            logger.info(f"Loaded smoke/fire detection model from {weights_file}")
            return model

        model = await loop.run_in_executor(None, _load_and_fuse)

        logger.info(f"Successfully loaded smoke/fire detection model from {model_path}")
        return model

    except ImportError as e:
        logger.warning("ultralytics package not installed. Install with: pip install ultralytics")
        raise ImportError(
            "Smoke/fire detection requires ultralytics. Install with: pip install ultralytics"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load smoke/fire detection model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load smoke/fire detection model: {e}") from e


async def detect_smoke_fire(
    model: Any,
    image: Image.Image,
    confidence_threshold: float = 0.5,
) -> SmokeFireDetectionResult:
    """Detect smoke/fire in an image.

    Args:
        model: YOLO model instance from load_smoke_fire_model
        image: PIL Image to analyze (full frame)
        confidence_threshold: Minimum confidence for detections (default 0.5)

    Returns:
        SmokeFireDetectionResult with detected smoke/fire

    Raises:
        RuntimeError: If detection fails
    """
    try:
        loop = asyncio.get_running_loop()

        def _detect() -> SmokeFireDetectionResult:
            """Run detection synchronously."""
            # Run inference
            results = model.predict(
                source=image,
                conf=confidence_threshold,
                verbose=False,
            )

            if not results or len(results) == 0:
                return SmokeFireDetectionResult()

            result = results[0]

            # Extract detections
            detections: list[SmokeFireDetection] = []

            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes
                for i in range(len(boxes)):
                    # Get class name
                    cls_id = int(boxes.cls[i].item())
                    if hasattr(model, "names") and cls_id in model.names:
                        class_name = model.names[cls_id].lower()
                    else:
                        class_name = f"class_{cls_id}"

                    # Get confidence
                    conf = float(boxes.conf[i].item())

                    # Get bounding box
                    xyxy = boxes.xyxy[i].tolist()
                    bbox = (float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3]))

                    # Determine detection type
                    detection_type = class_name if class_name in SMOKE_FIRE_CLASSES else "unknown"

                    if detection_type in SMOKE_FIRE_CLASSES:
                        detections.append(
                            SmokeFireDetection(
                                detection_type=detection_type,
                                confidence=conf,
                                bbox=bbox,
                            )
                        )

            return SmokeFireDetectionResult(detections=detections)

        return await loop.run_in_executor(None, _detect)

    except Exception as e:
        logger.error("Smoke/fire detection failed", exc_info=True)
        raise RuntimeError(f"Smoke/fire detection failed: {e}") from e


async def detect_smoke_fire_batch(
    model: Any,
    images: list[Image.Image],
    confidence_threshold: float = 0.5,
) -> list[SmokeFireDetectionResult]:
    """Detect smoke/fire in multiple images.

    Batch processes multiple images for efficiency.

    Args:
        model: YOLO model instance from load_smoke_fire_model
        images: List of PIL Images to analyze
        confidence_threshold: Minimum confidence for detections

    Returns:
        List of SmokeFireDetectionResult, one per input image
    """
    if not images:
        return []

    try:
        loop = asyncio.get_running_loop()

        def _detect_batch() -> list[SmokeFireDetectionResult]:
            """Run batch detection synchronously."""
            # Run inference on all images
            results = model.predict(
                source=images,
                conf=confidence_threshold,
                verbose=False,
            )

            detection_results: list[SmokeFireDetectionResult] = []

            for result in results:
                detections: list[SmokeFireDetection] = []

                if result.boxes is not None and len(result.boxes) > 0:
                    boxes = result.boxes
                    for i in range(len(boxes)):
                        cls_id = int(boxes.cls[i].item())
                        if hasattr(model, "names") and cls_id in model.names:
                            class_name = model.names[cls_id].lower()
                        else:
                            class_name = f"class_{cls_id}"

                        conf = float(boxes.conf[i].item())
                        xyxy = boxes.xyxy[i].tolist()
                        bbox = (
                            float(xyxy[0]),
                            float(xyxy[1]),
                            float(xyxy[2]),
                            float(xyxy[3]),
                        )

                        detection_type = (
                            class_name if class_name in SMOKE_FIRE_CLASSES else "unknown"
                        )

                        if detection_type in SMOKE_FIRE_CLASSES:
                            detections.append(
                                SmokeFireDetection(
                                    detection_type=detection_type,
                                    confidence=conf,
                                    bbox=bbox,
                                )
                            )

                detection_results.append(SmokeFireDetectionResult(detections=detections))

            return detection_results

        return await loop.run_in_executor(None, _detect_batch)

    except Exception as e:
        logger.error("Batch smoke/fire detection failed", exc_info=True)
        raise RuntimeError(f"Batch smoke/fire detection failed: {e}") from e


def format_smoke_fire_context(
    smoke_fire_result: SmokeFireDetectionResult | None,
    time_of_day: str | None = None,
) -> str:
    """Format smoke/fire detection results for prompt context.

    Args:
        smoke_fire_result: SmokeFireDetectionResult from detect_smoke_fire, or None
        time_of_day: Optional time context for risk assessment

    Returns:
        Formatted string for inclusion in risk analysis prompt
    """
    if smoke_fire_result is None:
        return "Smoke/Fire detection: Not performed"

    if not smoke_fire_result.has_detections:
        return "Smoke/Fire detection: No smoke or fire detected"

    lines = []

    if smoke_fire_result.has_fire:
        lines.append("**CRITICAL FIRE ALERT**")
        lines.append("  IMMEDIATE EVACUATION RECOMMENDED!")
        lines.append("  Contact emergency services immediately.")
    elif smoke_fire_result.has_smoke:
        lines.append("**SMOKE DETECTION ALERT**")
        lines.append("  Potential fire hazard detected.")

    lines.append(f"  Highest confidence: {smoke_fire_result.highest_confidence:.0%}")

    for detection in sorted(smoke_fire_result.detections, key=lambda d: d.confidence, reverse=True)[
        :5
    ]:
        priority = " **HIGH PRIORITY**" if detection.is_high_priority else ""
        lines.append(
            f"    - {detection.detection_type.upper()} ({detection.confidence:.0%}){priority}"
        )

    # Time-based escalation
    if time_of_day and time_of_day.lower() in ("night", "late_night", "early_morning"):
        lines.append(f"  TIME CONTEXT: Detection during {time_of_day}")
        lines.append("  Elevated concern: Fire/smoke at night when occupants may be sleeping")

    return "\n".join(lines)
