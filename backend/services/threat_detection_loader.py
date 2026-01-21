"""Threat/weapon detection model loader.

This module provides async loading and inference for the YOLOv8n threat detection
model, trained to detect weapons and threatening objects.

The model performs object detection focused on security-relevant threats like
knives, guns, bats, and other dangerous objects.

Model details:
- Architecture: YOLOv8n (nano variant for fast inference)
- Input: Images of any size (resized internally)
- Output: Bounding boxes with class labels and confidence scores
- VRAM: ~300MB
- Classes: knife, gun, bat, etc. (threat-related objects)

Usage in security context:
- Run on full frame when suspicious activity detected
- Run on person crops to detect held/carried weapons
- Provides high-priority alerts for weapon detection
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

# Known threat classes that this model may detect
# The actual classes depend on the specific model training
THREAT_CLASSES: frozenset[str] = frozenset(
    {
        "knife",
        "gun",
        "pistol",
        "rifle",
        "bat",
        "baseball_bat",
        "crowbar",
        "machete",
        "sword",
        "hammer",
        "axe",
        "weapon",
        "firearm",
        "handgun",
    }
)

# High-priority threat classes that should trigger immediate alerts
HIGH_PRIORITY_THREATS: frozenset[str] = frozenset(
    {
        "gun",
        "pistol",
        "rifle",
        "firearm",
        "handgun",
        "knife",
        "machete",
        "sword",
    }
)


@dataclass(slots=True)
class ThreatDetection:
    """Single threat detection result.

    Attributes:
        class_name: Detected threat class (e.g., "knife", "gun")
        confidence: Detection confidence (0-1)
        bbox: Bounding box as (x1, y1, x2, y2)
        is_high_priority: Whether this is a high-priority threat
    """

    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    is_high_priority: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "class_name": self.class_name,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
            "is_high_priority": self.is_high_priority,
        }


@dataclass(slots=True)
class ThreatDetectionResult:
    """Result from threat/weapon detection.

    Attributes:
        threats: List of detected threats
        has_threats: Whether any threats were detected
        has_high_priority: Whether any high-priority threats were detected
        highest_confidence: Highest confidence among detections
        threat_summary: Brief summary of detected threats
    """

    threats: list[ThreatDetection] = field(default_factory=list)
    has_threats: bool = False
    has_high_priority: bool = False
    highest_confidence: float = 0.0
    threat_summary: str = ""

    def __post_init__(self) -> None:
        """Compute derived fields after initialization."""
        if self.threats:
            self.has_threats = True
            self.has_high_priority = any(t.is_high_priority for t in self.threats)
            self.highest_confidence = max(t.confidence for t in self.threats)
            self._compute_summary()

    def _compute_summary(self) -> None:
        """Compute threat summary string."""
        if not self.threats:
            self.threat_summary = "No threats detected"
            return

        threat_counts: dict[str, int] = {}
        for threat in self.threats:
            threat_counts[threat.class_name] = threat_counts.get(threat.class_name, 0) + 1

        parts = [f"{count}x {name}" for name, count in sorted(threat_counts.items())]
        self.threat_summary = ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "threats": [t.to_dict() for t in self.threats],
            "has_threats": self.has_threats,
            "has_high_priority": self.has_high_priority,
            "highest_confidence": self.highest_confidence,
            "threat_summary": self.threat_summary,
            "threat_count": len(self.threats),
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable threat detection summary for Nemotron context
        """
        if not self.has_threats:
            return "Threat scan: No weapons or threatening objects detected"

        lines = ["**THREAT DETECTION ALERT**"]

        if self.has_high_priority:
            lines.append("  CRITICAL: High-priority threat(s) detected!")

        for threat in sorted(self.threats, key=lambda t: t.confidence, reverse=True):
            priority_marker = " [HIGH PRIORITY]" if threat.is_high_priority else ""
            lines.append(
                f"  - {threat.class_name}: {threat.confidence:.0%} confidence{priority_marker}"
            )

        return "\n".join(lines)


async def load_threat_detection_model(model_path: str) -> Any:
    """Load YOLOv8n threat detection model from local path.

    This function loads the YOLO-based threat detection model for
    identifying weapons and threatening objects.

    Args:
        model_path: Local path to the model directory
                   (e.g., "/models/model-zoo/threat-detection-yolov8n")
                   Should contain the model weights file (.pt)

    Returns:
        Loaded YOLO model instance (ready for inference)

    Raises:
        ImportError: If ultralytics is not installed
        RuntimeError: If model loading fails
    """
    try:
        from ultralytics import YOLO

        logger.info(f"Loading threat detection model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load_and_fuse() -> Any:
            """Load YOLO model and pre-fuse for thread-safe concurrent use.

            YOLO models automatically fuse batch normalization into Conv layers
            on first predict() call. This fusion is NOT thread-safe and causes
            errors when multiple threads call predict() concurrently.

            By calling fuse() immediately after loading, we ensure the model
            is ready for concurrent use without race conditions.
            """
            model_dir = Path(model_path)

            # Find the model weights file
            weights_file = model_dir / "model.pt"
            if not weights_file.exists():
                weights_file = model_dir / "best.pt"
            if not weights_file.exists():
                weights_file = model_dir / "threat-detection-yolov8n.pt"
            if not weights_file.exists():
                # Try any .pt file
                pt_files = list(model_dir.glob("*.pt"))
                if pt_files:
                    weights_file = pt_files[0]
                else:
                    raise FileNotFoundError(f"No model weights (.pt) found in {model_dir}")

            model = YOLO(str(weights_file))

            # Pre-fuse to avoid race condition
            if hasattr(model, "fuse"):
                inner_model = getattr(model, "model", None)
                if inner_model is not None and hasattr(inner_model, "is_fused"):
                    if not inner_model.is_fused():
                        model.fuse()
                else:
                    model.fuse()

            logger.info(f"Loaded threat detection model from {weights_file}")
            return model

        model = await loop.run_in_executor(None, _load_and_fuse)

        logger.info(f"Successfully loaded threat detection model from {model_path}")
        return model

    except ImportError as e:
        logger.warning("ultralytics package not installed. Install with: pip install ultralytics")
        raise ImportError(
            "Threat detection requires ultralytics. Install with: pip install ultralytics"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load threat detection model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load threat detection model: {e}") from e


async def detect_threats(
    model: Any,
    image: Image.Image,
    confidence_threshold: float = 0.25,
) -> ThreatDetectionResult:
    """Detect threats/weapons in an image.

    Args:
        model: YOLO model instance from load_threat_detection_model
        image: PIL Image to analyze (full frame or person crop)
        confidence_threshold: Minimum confidence for detections (default 0.25)

    Returns:
        ThreatDetectionResult with detected threats

    Raises:
        RuntimeError: If detection fails
    """
    try:
        loop = asyncio.get_event_loop()

        def _detect() -> ThreatDetectionResult:
            """Run detection synchronously."""
            # Run inference
            results = model.predict(
                source=image,
                conf=confidence_threshold,
                verbose=False,
            )

            if not results or len(results) == 0:
                return ThreatDetectionResult()

            result = results[0]

            # Extract detections
            threats: list[ThreatDetection] = []

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

                    # Determine if high priority
                    is_high_priority = class_name in HIGH_PRIORITY_THREATS

                    threats.append(
                        ThreatDetection(
                            class_name=class_name,
                            confidence=conf,
                            bbox=bbox,
                            is_high_priority=is_high_priority,
                        )
                    )

            return ThreatDetectionResult(threats=threats)

        return await loop.run_in_executor(None, _detect)

    except Exception as e:
        logger.error("Threat detection failed", exc_info=True)
        raise RuntimeError(f"Threat detection failed: {e}") from e


async def detect_threats_batch(
    model: Any,
    images: list[Image.Image],
    confidence_threshold: float = 0.25,
) -> list[ThreatDetectionResult]:
    """Detect threats in multiple images.

    Batch processes multiple images for efficiency.

    Args:
        model: YOLO model instance from load_threat_detection_model
        images: List of PIL Images to analyze
        confidence_threshold: Minimum confidence for detections

    Returns:
        List of ThreatDetectionResult, one per input image
    """
    if not images:
        return []

    try:
        loop = asyncio.get_event_loop()

        def _detect_batch() -> list[ThreatDetectionResult]:
            """Run batch detection synchronously."""
            # Run inference on all images
            results = model.predict(
                source=images,
                conf=confidence_threshold,
                verbose=False,
            )

            detection_results: list[ThreatDetectionResult] = []

            for result in results:
                threats: list[ThreatDetection] = []

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
                        is_high_priority = class_name in HIGH_PRIORITY_THREATS

                        threats.append(
                            ThreatDetection(
                                class_name=class_name,
                                confidence=conf,
                                bbox=bbox,
                                is_high_priority=is_high_priority,
                            )
                        )

                detection_results.append(ThreatDetectionResult(threats=threats))

            return detection_results

        return await loop.run_in_executor(None, _detect_batch)

    except Exception as e:
        logger.error("Batch threat detection failed", exc_info=True)
        raise RuntimeError(f"Batch threat detection failed: {e}") from e


def format_threat_context(
    threat_result: ThreatDetectionResult | None,
    time_of_day: str | None = None,
) -> str:
    """Format threat detection results for prompt context.

    Args:
        threat_result: ThreatDetectionResult from detect_threats, or None
        time_of_day: Optional time context for risk assessment

    Returns:
        Formatted string for inclusion in risk analysis prompt
    """
    if threat_result is None:
        return "Threat detection: Not performed"

    if not threat_result.has_threats:
        return "Threat detection: No weapons or threatening objects detected"

    lines = ["**WEAPON/THREAT DETECTION**"]

    if threat_result.has_high_priority:
        lines.append("  CRITICAL ALERT: High-priority weapon detected!")
        lines.append("  Immediate review recommended.")

    lines.append(f"  Threats found: {threat_result.threat_summary}")
    lines.append(f"  Highest confidence: {threat_result.highest_confidence:.0%}")

    for threat in sorted(threat_result.threats, key=lambda t: t.confidence, reverse=True)[:5]:
        priority = " **HIGH PRIORITY**" if threat.is_high_priority else ""
        lines.append(f"    - {threat.class_name} ({threat.confidence:.0%}){priority}")

    # Time-based escalation
    if time_of_day and time_of_day.lower() in ("night", "late_night", "early_morning"):
        lines.append(f"  TIME CONTEXT: Detection during {time_of_day}")
        lines.append("  Elevated concern: Armed threat at unusual hour")

    return "\n".join(lines)
